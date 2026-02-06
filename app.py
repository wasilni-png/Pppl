import asyncio
import threading
import sys
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client
from telegram import Bot
from telegram.constants import ParseMode
import google.generativeai as genai

# --- محاولة استيراد الإعدادات من ملف config.py ---
try:
    from config import normalize_text, CITIES_DISTRICTS, BOT_TOKEN, get_db_connection
    print("✅ تم تحميل ملف config.py بنجاح")
except Exception as e:
    print(f"❌ خطأ في تحميل ملف config.py: {e}")
    sys.exit(1)

# --- إعدادات الحساب (API & Session) ---
API_ID = "36360458"
API_HASH = "daae4628b4b4aac1f0ebfce23c4fa272"
SESSION_STRING = "BAIq0QoApqDmvNIHZnbO2VxSWBdRlJ5SP7S19VeM7rV0Umjc1mO70IQx-Un7FdoYE27YpogRdiB-KXmzvk1zZl_u_CZSC7mQ7M7XdGrpIDvhhAhxVacbpIPary3Zh9J36X1hCZgBhpX9qneOiGxzQcGBdF7XMfsFdYI6_Be2hiPoKUFMtLflsrnWmLCNkKJFhylzubFLMX9KMzn7VnUG5rI9xCfDEae0emFjPA1FqysJV3P2ehe-HanA6GpaIxGOoDGOv_IyyySHFb0UAP4i19Xm5-i5SHUZNiT8e72DX1SLZn40Z5XRgEIdTrfoHDyyOfqvT676UlOLJHiHzQ0c06u6RvPMvAAAAAH-ZrzOAA"

# --- إعداد الذكاء الاصطناعي (Gemini) ---
# ملاحظة: يفضل استخدام gemini-2.0-flash لسرعة أكبر ودقة أعلى في عام 2026
genai.configure(api_key="AIzaSyDvEF8WDhGt6nDWjqxgix0Rb8qaAmtEPbk")
ai_model = genai.GenerativeModel('gemini-1.5-flash')

# --- الكلمات المستبعدة فوراً ---
DRIVER_KEYWORDS = ["متواجد", "متاح", "شغال", "جاهز", "أسعارنا", "يوجد لدينا", "سيارة نظيفة", "نقل عفش", "دربك سمح"]

user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# --- وظيفة الذكاء الاصطناعي المتطورة ---
async def ai_analyze_message(text):
    if not text or len(text.strip()) < 5: return False
    
    if any(word in text for word in DRIVER_KEYWORDS):
        return False

    prompt = f"""
أنت خبير في تحليل المحادثات بلهجة أهل مكة وجدة (الحجازية). مهمتك هي تصنيف نية مرسل الرسالة التالية في مجموعات التوصيل:

الرسالة: "{text}"

القواعد الصارمة للتصنيف:
1. رد بـ YES فقط إذا كان المرسل "زبون" (Customer) يبحث عن خدمة:
   - يطلب مشواراً (مثلاً: "أبي مشوار"، "مين يوصلني"، "رايح للحرم").
   - يستفسر عن سعر (مثلاً: "بكم التوصيل لـ..."، "كم السعر من...").
   - يطلب توصيل غرض أو طلب (مثلاً: "عندي طلب من مطعم"، "مين يوصل لي غرض").
   - يسأل عن توفر سائق (مثلاً: "في كابتن قريب؟"، "مطلوب سواق الحين").

2. رد بـ NO فقط إذا كان المرسل "سائق" (Driver) أو محتوى غير مفيد:
   - يعلن عن خدمته (مثلاً: "متواجد الحين"، "سيارة نظيفة"، "أسعارنا مناسبة").
   - يضع رقم جواله أو يطلب الخاص (مثلاً: "تواصل معي واتساب"، "أنا جاهز").
   - يعرض رحلات مجدولة (مثلاً: "رحلة يومية مكة-جدة").
   - رسائل شكر، سوالف، أو أخبار (مثلاً: "تم التوصيل"، "شكراً كابتن").

الناتج المطلوب: كلمة واحدة فقط (YES) أو (NO).
"""

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: ai_model.generate_content(prompt))
        answer = response.text.strip().upper()
        return "YES" in answer
    except Exception as e:
        print(f"⚠️ خطأ في تحليل AI: {e}")
        return "مشوار" in text or "توصيل" in text

# --- إرسال الإشعار للسائقين ---
# --- إرسال الإشعار للسائقين ---
async def notify_drivers(district, original_msg):
    content = original_msg.text or original_msg.caption
    if not content: return

    conn = get_db_connection()
    if not conn: return
    
    try:
        search_term = normalize_text(district)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id FROM users 
                WHERE role = 'driver' 
                AND is_blocked = FALSE 
                AND subscription_expiry > NOW()
                AND (REPLACE(REPLACE(districts, 'ة', 'ه'), 'ال', '') ILIKE %s)
                """,
                (f"%{search_term}%",)
            )
            drivers = [row[0] for row in cur.fetchall()]

        if not drivers: 
            return

        customer = original_msg.from_user
        customer_name = customer.first_name if customer.first_name else "عميل"
        customer_link = f"tg://user?id={customer.id}" if not customer.username else f"https://t.me/{customer.username}"
        
        # 🛠️ الإصلاح هنا: استخدام .id بدلاً من .message_id لأن الرسالة قادمة من Pyrogram
        msg_id = getattr(original_msg, "id", getattr(original_msg, "message_id", None))
        chat_id_str = str(original_msg.chat.id).replace("-100", "")
        msg_url = f"https://t.me/c/{chat_id_str}/{msg_id}"

        safe_text = content.replace("<", "&lt;").replace(">", "&gt;")
        alert_text = (
            f"🤖 <b>طلب مشوار ذكي (للمشتركين)</b>\n\n"
            f"📍 <b>الحي:</b> {district}\n"
            f"👤 <b>العميل:</b> {customer_name}\n"
            f"📝 <b>الطلب:</b>\n<i>{safe_text}</i>"
        )

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [
            [InlineKeyboardButton("🔗 عرض نص الطلب (بالجروب)", url=msg_url)],
            [InlineKeyboardButton("💬 مراسلة العميل (خاص)", url=customer_link)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        sent_count = 0
        for d_id in drivers:
            try:
                await bot_sender.send_message(
                    chat_id=d_id,
                    text=alert_text,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                sent_count += 1
            except Exception as e:
                continue
                
        print(f"✅ تم تحويل طلب في {district} لـ {sent_count} سائق مشترك.")

    except Exception as e:
        print(f"❌ خطأ في notify_drivers: {e}")
    finally:
        from config import release_db_connection
        release_db_connection(conn)


# --- المحرك الرئيسي للرادار ---
async def start_radar():
    await user_app.start()
    me = await user_app.get_me()
    print(f"✅ تم تسجيل الدخول باسم: {me.first_name}")

    monitored_chats = []
    async for dialog in user_app.get_dialogs(limit=50):
        if "GROUP" in str(dialog.chat.type).upper():
            monitored_chats.append({"id": dialog.chat.id, "title": dialog.chat.title})

    print(f"📡 مراقبة نشطة لـ ({len(monitored_chats)}) مجموعة.")

    last_id = {}
    for chat in monitored_chats:
        try:
            async for msg in user_app.get_chat_history(chat["id"], limit=1):
                last_id[chat["id"]] = msg.id
        except:
            last_id[chat["id"]] = 0

    while True:
        for chat in monitored_chats:
            try:
                async for msg in user_app.get_chat_history(chat["id"], limit=1):
                    if msg.id > last_id.get(chat["id"], 0):
                        last_id[chat["id"]] = msg.id

                        # فحص النص والوسائط بشكل آمن
                        text_to_analyze = msg.text or msg.caption
                        if not text_to_analyze or (msg.from_user and msg.from_user.id == me.id):
                            continue

                        if await ai_analyze_message(text_to_analyze):
                            print(f"🧠 AI: تأكيد طلب حقيقي في [{chat['title']}]")
                            text_c = normalize_text(text_to_analyze)
                            for city, districts in CITIES_DISTRICTS.items():
                                for d in districts:
                                    if normalize_text(d) in text_c:
                                        await notify_drivers(d, msg)
                                        break

                await asyncio.sleep(0.5)
            except Exception as e:
                if "420" in str(e): await asyncio.sleep(15)
                continue
        await asyncio.sleep(2)

# --- خادم الويب ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"AI Radar is Live")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', port), HealthCheckHandler).serve_forever(), daemon=True).start()
    asyncio.run(start_radar())
