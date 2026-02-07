import asyncio
import threading
import sys
import os
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
import google.generativeai as genai
from datetime import datetime
# --- كتم سجلات HTTP المزعجة لحماية التوكن ---
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

# --- استيراد الإعدادات الخارجية ---
try:
    from config import normalize_text, CITIES_DISTRICTS, BOT_TOKEN, get_db_connection, release_db_connection
    print("✅ تم تحميل الإعدادات بنجاح")
except Exception as e:
    print(f"❌ خطأ في تحميل ملف config.py: {e}")
    sys.exit(1)

# --- إعدادات الحساب (يفضل وضعها في Environment Variables في Render) ---
API_ID = os.environ.get("API_ID", "36360458")
API_HASH = os.environ.get("API_HASH", "daae4628b4b4aac1f0ebfce23c4fa272")
SESSION_STRING = os.environ.get("SESSION_STRING", "BAIq0QoApqDmvNIHZnbO2VxSWBdRlJ5SP7S19VeM7rV0Umjc1mO70IQx-Un7FdoYE27YpogRdiB-KXmzvk1zZl_u_CZSC7mQ7M7XdGrpIDvhhAhxVacbpIPary3Zh9J36X1hCZgBhpX9qneOiGxzQcGBdF7XMfsFdYI6_Be2hiPoKUFMtLflsrnWmLCNkKJFhylzubFLMX9KMzn7VnUG5rI9xCfDEae0emFjPA1FqysJV3P2ehe-HanA6GpaIxGOoDGOv_IyyySHFb0UAP4i19Xm5-i5SHUZNiT8e72DX1SLZn40Z5XRgEIdTrfoHDyyOfqvT676UlOLJHiHzQ0c06u6RvPMvAAAAAH-ZrzOAA")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDvEF8WDhGt6nDWjqxgix0Rb8qaAmtEPbk")

# إعداد الذكاء الاصطناعي
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

# --- قوائم الكلمات (صمام الأمان) ---
# كلمات تدل على أن المرسل سائق (للاستبعاد)
DRIVER_KEYWORDS = [
    "متواجد", "متاح", "شغال", "جاهز", "أسعارنا", "سيارة نظيفة", "نقل عفش", 
    "دربك سمح", "توصيل مشاوير", "أوصل", "اوصل", "اتصال", "واتساب"
]

# قائمة الكلمات الموسعة (للتأكيد في حال فشل AI)
SAFE_KEYWORDS = [
    "مشوار", "توصيل", "يوصلني", "سواق", "كابتن", "كبتن", "سيارة", "سياره", "رايح", "روحه", "نقل",
    "طلب", "طلبات", "غرض", "اغراض", "أغراض", "طرد", "شحنة", "شحنه", "كرتون", "مطعم", "من مطعم",
    "بكم", "كم", "سعر", "السعر", "بكم يوصل", "تكلفة", "بكم توديني", "مطلوب", "محتاج",
    "المطار", "الحرم", "البلد", "القطار", "جامعة", "مشاوير"
]

# إعداد العملاء
user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# --- دالة تحليل نية الرسالة ---
async def ai_analyze_message(text):
    if not text or len(text.strip()) < 5: return False
    
    # تحويل النص للصيغة المبسطة للفحص السريع
    clean_text = normalize_text(text)
    
    # استبعاد إعلانات السائقين فوراً
    if any(word in clean_text for word in DRIVER_KEYWORDS):
        return False

    prompt = f"""
    أنت محقق خبير في طلبات المشاوير. حلل الرسالة: "{text}"
    هل المرسل زبون يطلب خدمة (توصيل ركاب، أغراض، أو استفسار عن سعر)؟
    رد بـ YES فقط إذا كان طلباً حقيقياً.
    رد بـ NO إذا كان عرض خدمة من سائق أو كلاماً غير مفيد.
    الرد بكلمة واحدة: YES أو NO.
    """
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: ai_model.generate_content(prompt))
        answer = response.text.strip().upper()
        if "YES" in answer: return True
    except Exception as e:
        print(f"⚠️ خطأ AI: {e}")
    
    # خطة البديل: الاعتماد على الكلمات المفتاحية في حال تعطل AI
    return any(word in clean_text for word in SAFE_KEYWORDS)

# --- دالة بث الطلب لجميع السائقين ---


async def notify_all_drivers(detected_district, original_msg):
    content = original_msg.text or original_msg.caption
    if not content: return

    conn = get_db_connection()
    if not conn: return

    try:
        with conn.cursor() as cur:
            # جلب السائقين مع حالة اشتراكهم
            cur.execute("""
                SELECT user_id, subscription_expiry 
                FROM users 
                WHERE role = 'driver' AND is_blocked = FALSE
            """)
            drivers_data = cur.fetchall()

        if not drivers_data: return

        customer = original_msg.from_user
        customer_name = (customer.first_name or "عميل") if customer else "عميل"
        
        # رابط الراكب المباشر للمشتركين
        customer_link = f"tg://user?id={customer.id}" if customer and not customer.username else f"https://t.me/{customer.username}" if customer else "#"
        
        # رابط الرسالة في الجروب للمشتركين
        msg_id = getattr(original_msg, "id", getattr(original_msg, "message_id", 0))
        chat_id_str = str(original_msg.chat.id).replace("-100", "")
        msg_url = f"https://t.me/c/{chat_id_str}/{msg_id}"

        # رابط الإدارة لغير المشتركين
        admin_contact_link = "https://t.me/x3FreTx"

        now = datetime.now()

        for d_id, expiry in drivers_data:
            try:
                # فحص هل السائق مشترك (تاريخ الانتهاء أكبر من الوقت الحالي)
                is_active = expiry and expiry > now
                
                if is_active:
                    # ✅ رسالة المشترك: تظهر فيها الروابط المباشرة
                    alert_text = (
                        f"🌟 <b>طلب مشوار جديد (خاص بالمشتركين)</b>\n\n"
                        f"📍 <b>المنطقة:</b> {detected_district}\n"
                        f"📝 <b>الطلب:</b>\n<i>{content}</i>"
                    )
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔗 عرض الطلب في الجروب", url=msg_url)],
                        [InlineKeyboardButton("💬 مراسلة الراكب مباشرة", url=customer_link)]
                    ])
                else:
                    # ❌ رسالة غير المشترك: تنبيه مع رابط الإدارة
                    alert_text = (
                        f"🆕 <b>طلب مشوار جديد مكتشف</b>\n\n"
                        f"📍 <b>المنطقة:</b> {detected_district}\n"
                        f"📝 <b>نص الطلب:</b>\n<i>{content}</i>\n\n"
                        f"⚠️ <b>هذا الطلب متاح للمشتركين فقط.</b>\n"
                        f"تواصل مع الإدارة لتفعيل حسابك والوصول للروابط."
                    )
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("💳 تواصل معنا للاشتراك في البوت", url=admin_contact_link)]
                    ])

                await bot_sender.send_message(
                    chat_id=d_id,
                    text=alert_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                await asyncio.sleep(0.05) # حماية من الحظر عند الإرسال الجماعي
            except: continue

        print(f"🚀 تم البث لـ {len(drivers_data)} سائق. (المشتركين حصلوا على الروابط، وغير المشتركين وجهوا للإدارة).")
    finally:
        from config import release_db_connection
        release_db_connection(conn)

# --- المحرك الرئيسي للرادار ---


async def start_radar():
    await user_app.start()
    print("📡 الرادار يعمل الآن ويبحث عن طلبات لجميع السائقين...")

    last_id = {}
    
    # 1. تهيئة أولية لجلب آخر ID لكل مجموعة لمنع سحب الرسائل القديمة عند التشغيل
    try:
        async for dialog in user_app.get_dialogs(limit=40):
            if "GROUP" in str(dialog.chat.type).upper():
                async for msg in user_app.get_chat_history(dialog.chat.id, limit=1):
                    last_id[dialog.chat.id] = msg.id
        print("✅ تم تحديد نقطة البداية للمجموعات.")
    except Exception as e:
        print(f"⚠️ تنبيه أثناء التهيئة: {e}")

    while True:
        try:
            # 2. زيادة وقت الانتظار بين الدورات لتقليل الضغط الإجمالي
            await asyncio.sleep(10) 
            
            async for dialog in user_app.get_dialogs(limit=40):
                if "GROUP" not in str(dialog.chat.type).upper(): 
                    continue
                
                chat_id = dialog.chat.id
                try:
                    # 3. فحص الرسالة الأخيرة فقط
                    async for msg in user_app.get_chat_history(chat_id, limit=1):
                        if msg.id > last_id.get(chat_id, 0):
                            last_id[chat_id] = msg.id
                            
                            text = msg.text or msg.caption
                            # تجاهل الرسائل الفارغة أو رسائل البوت نفسه
                            if not text or (msg.from_user and msg.from_user.is_self): 
                                continue

                            # 4. إرسال للتحليل (تم إصلاح الموديل في الدالة المرافقة)
                            if await ai_analyze_message(text):
                                found_d = "غير محدد"
                                text_c = normalize_text(text)
                                for city, districts in CITIES_DISTRICTS.items():
                                    for d in districts:
                                        if normalize_text(d) in text_c:
                                            found_d = d
                                            break
                                
                                print(f"🎯 طلب حقيقي في [{dialog.chat.title}]")
                                await notify_all_drivers(found_d, msg)
                    
                    # 💡 أهم إضافة: تأخير بسيط (Throttle) بين كل مجموعة وأخرى لمنع الـ Flood
                    await asyncio.sleep(0.5)

                except Exception as e:
                    if "420" in str(e): # استلام تنبيه FloodWait
                        wait_seconds = int(''.join(filter(str.isdigit, str(e))) or 20)
                        print(f"😴 تليجرام طلب الهدوء.. سأنام لـ {wait_seconds} ثانية")
                        await asyncio.sleep(wait_seconds)
                    continue

        except Exception as e:
            print(f"⚠️ خطأ في الدورة الرئيسية: {e}")
            await asyncio.sleep(15) # انتظار أطول عند حدوث خطأ عام



# --- خادم الويب (Health Check) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Radar Active")

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    httpd = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    httpd.serve_forever()

if __name__ == "__main__":
    # تشغيل خادم الويب في خيط منفصل
    threading.Thread(target=run_health_server, daemon=True).start()
    # تشغيل الرادار
    asyncio.run(start_radar())
