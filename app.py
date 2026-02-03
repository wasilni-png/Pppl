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
genai.configure(api_key="AIzaSyADYritHhOSTJNN1wxQiRH0Rwoo1ycL_HI")
ai_model = genai.GenerativeModel('gemini-1.5-flash')

# --- الكلمات المستبعدة فوراً (لمنع إعلانات السائقين قبل وصولها للذكاء الاصطناعي) ---
DRIVER_KEYWORDS = ["متواجد", "متاح", "شغال", "جاهز", "أسعارنا", "يوجد لدينا", "سيارة نظيفة", "نقل عفش"]

user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# --- وظيفة الذكاء الاصطناعي المتطورة ---
async def ai_analyze_message(text):
    # 1. قائمة الكلمات الإخبارية (تُرفض فوراً لأنها ليست طلباً)
    # تمنع رسائل مثل: "رحت"، "وصلت"، "جاني مشوار"، "كنت في"
    STORY_KEYWORDS = ["جاني مشوار", "رحت", "وصلت", "كنت في", "خلصت مشوار", "كنت بـ"]
    if any(word in text for word in STORY_KEYWORDS):
        return False

    # 2. استبعاد إعلانات السائقين التقليدية
    if any(word in text for word in DRIVER_KEYWORDS):
        return False

    # 3. تعديل الـ Prompt ليكون "محققاً" وليس مجرد "مصنفاً"
    prompt = f"""
    حلل الرسالة التالية: "{text}"
    هل المرسل "زبون" يحتاج سواق "الآن"؟
    - أجب بـ YES فقط إذا كان يطلب (مثل: ابي مشوار، مين يوصلني، في أحد يوصلني من..إلى).
    - أجب بـ NO إذا كان المرسل (سائق) يسولف أو يخبر عن مشوار أخذه (مثل: رحت لـ، جاني مشوار، أنا وصلت).
    - أجب بـ NO إذا كان المرسل يعرض خدمته (مثل: أنا أوصل، متواجد، متاح).
    الرد بكلمة واحدة فقط: YES أو NO.
    """
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: ai_model.generate_content(prompt))
        answer = response.text.strip().upper()
        
        # طباعة قرار الذكاء الاصطناعي في السجلات للمراقبة
        print(f"🧠 تحليل AI للنص [{text[:20]}...]: القرار هو {answer}")
        
        return "YES" in answer
    except Exception as e:
        print(f"⚠️ خطأ AI: {e}")
        return False


# --- إرسال الإشعار للسائقين ---
async def notify_drivers(district, original_msg):
    conn = get_db_connection()
    if not conn: return
    try:
        search_term = normalize_text(district)
        with conn.cursor() as cur:
            # استعلام ذكي يتجاهل "ال" التعريف ويبحث في الأحياء
            cur.execute(
                "SELECT user_id FROM users WHERE role = 'driver' AND (REPLACE(REPLACE(districts, 'ة', 'ه'), 'ال', '') ILIKE %s)",
                (f"%{search_term}%",)
            )
            drivers = [row[0] for row in cur.fetchall()]

        if not drivers: return

        customer = original_msg.from_user
        customer_name = customer.first_name if customer.first_name else "عميل"
        customer_link = f"tg://user?id={customer.id}" if not customer.username else f"https://t.me/{customer.username}"

        alert_text = (
            f"🤖 **طلب مشوار ذكي (مفحوص)**\n\n"
            f"📍 **الحي:** {district}\n"
            f"👤 **العميل:** {customer_name}\n"
            f"📝 **الطلب:**\n_{original_msg.text}_\n\n"
            f"📥 [اضغط هنا لمراسلة العميل خاص]({customer_link})"
        )

        for d_id in drivers:
            try:
                await bot_sender.send_message(chat_id=d_id, text=alert_text, parse_mode=ParseMode.MARKDOWN)
            except:
                continue
        print(f"✅ تم تحويل طلب في {district} لـ {len(drivers)} سائق.")
    finally:
        conn.close()

# --- المحرك الرئيسي للرادار ---
async def start_radar():
    await user_app.start()
    me = await user_app.get_me()
    print(f"✅ تم تسجيل الدخول باسم: {me.first_name}")

    # 1. تحديث قائمة المجموعات وإجبار الحساب على رؤية الرسائل الجديدة
    monitored_chats = []
    print("⏳ جاري تنشيط المجموعات...")
    async for dialog in user_app.get_dialogs(limit=50):
        if "GROUP" in str(dialog.chat.type).upper():
            monitored_chats.append({"id": dialog.chat.id, "title": dialog.chat.title})
    
    print(f"📡 مراقبة نشطة لـ ({len(monitored_chats)}) مجموعة.")

    # 2. تخزين آخر ID موجود حالياً لتجنب سحب الرسائل القديمة (البدء من الآن)
    last_id = {}
    for chat in monitored_chats:
        try:
            async for msg in user_app.get_chat_history(chat["id"], limit=1):
                last_id[chat["id"]] = msg.id
        except:
            last_id[chat["id"]] = 0

    print("🚀 الرادار بدأ الصيد الفعلي للرسائل الجديدة...")

    while True:
        for chat in monitored_chats:
            try:
                # فحص آخر رسالة وصلت "الآن"
                async for msg in user_app.get_chat_history(chat["id"], limit=1):
                    if msg.id > last_id.get(chat["id"], 0):
                        last_id[chat["id"]] = msg.id
                        
                        # تجاهل رسائل البوت نفسه والرسائل الفارغة
                        if (msg.from_user and msg.from_user.id == me.id) or not msg.text:
                            continue

                        print(f"📩 رسالة جديدة مكتشفة في [{chat['title']}]")
                        
                        # تحليل الذكاء الاصطناعي
                        if await ai_analyze_message(msg.text):
                            print(f"🧠 AI: تأكيد طلب حقيقي!")
                            text_c = normalize_text(msg.text)
                            for city, districts in CITIES_DISTRICTS.items():
                                for d in districts:
                                    if normalize_text(d) in text_c:
                                        print(f"🎯 تطابق مع حي: {d}")
                                        await notify_drivers(d, msg)
                                        break
                
                await asyncio.sleep(0.5) # تأخير بسيط لتجنب الـ Flood
            except Exception as e:
                if "420" in str(e):
                    await asyncio.sleep(15)
                continue
        await asyncio.sleep(2)

# --- خادم الويب (Health Check لـ Render) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"AI Radar is Live and Running")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', port), HealthCheckHandler).serve_forever(), daemon=True).start()
    asyncio.run(start_radar())