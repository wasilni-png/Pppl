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
from datetime import datetime, timezone

# --- إعداد السجلات (Logging) ---
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

# --- استيراد الإعدادات الخارجية ---
try:
    # تم إبقاء الضروريات فقط وحذف دوال قاعدة البيانات
    from config import normalize_text, CITIES_DISTRICTS, BOT_TOKEN

    print("✅ تم تحميل الإعدادات بنجاح")
except Exception as e:
    print(f"❌ خطأ في تحميل ملف config.py: {e}")
    sys.exit(1)

# --- إعدادات الحساب والقناة ---
API_ID = os.environ.get("API_ID", "36360458")
API_HASH = os.environ.get("API_HASH", "daae4628b4b4aac1f0ebfce23c4fa272")
SESSION_STRING = os.environ.get("SESSION_STRING", "BAIq0QoAOD9QpM8asjl1fICVx0vTRH7QjtgTNCEF692Ihz9Xkj_HWnZ6hnl3pv8gN6yFWqMEBhFl7A40uQWQWIsU8KM9or6K-_HsGbe8SP_4AhbIIFU7vrqyo_tuU0SydmvpT8sbSs-RC-yl89Gm5t4EXag2g9Wxr_MQaWIYtJZGWWkVisaDjM8AnUbfD9BDzolvp06qEz-mnsrKZCQKmrPmA_LNhxpqBBcdEJ9EVs4Lwvsh0B7u_ZyOtLhetuwb1YAd1pYNYd00OGwlLuH-8tJc5v5cFbeX6bxT89JMEZVELD2aKhU1XeljAxSieD0F3yL9TsLFglGwu-qsSs7b_073w9e9ZAAAAAH-ZrzOAA")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDvEF8WDhGt6nDWjqxgix0Rb8qaAmtEPbk")
CHANNEL_ID = -1003763324430  # معرف قناتك

# إعداد الذكاء الاصطناعي
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# إعداد عملاء تليجرام
user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# --- قوائم الكلمات (صمام الأمان) ---
DRIVER_KEYWORDS = [
    "متواجد", "متاح", "شغال", "جاهز", "أسعارنا", "سيارة نظيفة", "نقل عفش", 
    "دربك سمح", "توصيل مشاوير", "أوصل", "اوصل", "اتصال", "واتساب", "للتواصل",
    "خاص", "الخاص", "بخدمتكم", "خدمتكم", "أستقبل", "استقبل", "نقل بضائع",
    "مشاويركم", "سياره نظيفه", "فان", "دباب", "سطحه", "سطحة", "كابتن", 
    "مندوب", "مناديب", "توصيل طلبات", "ارخص الأسعار", "أرخص الأسعار", "بأسعار",
    "عقار", "عقارات", "للبيع", "للإيجار", "للايجار", "دور", "شقة", "شقه",
    "رخصة فال", "رخصة", "رخصه", "مخطط", "أرض", "ارض", "فلة", "فله", 
    "عماره", "عمارة", "استثمار", "صك", "إفراغ", "الوساطة العقارية", "تجاري", "سكني",
    "اشتراك", "باقات", "تسجيل", "تأمين", "تفويض", "تجديد", "قرض", "تمويل", 
    "بنك", "تسديد", "مخالفات", "اعلان", "إعلان", "قروب", "مجموعة", "انضم", 
    "رابط", "نشر", "قوانين", "احترام", "الذوق العام", "استقدام", "خادمات",
    "تعقيب", "معقب", "انجاز", "إنجاز", "كفيل", "نقل كفالة", "اسقاط", "تعديل مهنة",
    "حياك الله", "نورتنا", "انضمامك", "أهلاً بك", "اهلا بك", "قواعد المجموعة",
    "مرحباً بك", "مرحبا بك", "تنبيه", "محظور", "يُمنع", "يمنع", "بالتوفيق للجميع"
]

SAFE_KEYWORDS = [
    "مشوار", "توصيل", "يوصلني", "سواق", "كابتن", "كبتن", "سيارة", "سياره", "رايح", "روحه", "نقل",
    "طلب", "طلبات", "غرض", "اغراض", "أغراض", "طرد", "شحنة", "شحنه", "كرتون", "مطعم", "من مطعم",
    "بكم", "كم", "سعر", "السعر", "بكم يوصل", "تكلفة", "بكم توديني", "مطلوب", "محتاج",
    "المطار", "الحرم", "البلد", "القطار", "جامعة", "مشاوير"
]

# --- دالة تحليل نية الرسالة ---
async def ai_analyze_message(text):
    if not text or len(text.strip()) < 5: return False
    if len(text) > 450: return False

    clean_text = normalize_text(text)
    if any(word in clean_text for word in DRIVER_KEYWORDS):
        return False

    prompt = f"""
    تصرف كمشرف في قروب تليجرام لسيارات الأجرة في المدينة المنورة.
    حلل الرسالة التالية: "{text}"
    الهدف: معرفة هل المرسل "زبون يريد مشوار" أم لا.
    الرد المطلوب: كلمة واحدة فقط (YES أو NO).
    """

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, prompt),
            timeout=4.0 
        )
        result = response.text.strip().upper().replace(".", "")
        return "YES" in result
    except:
        return any(word in clean_text for word in SAFE_KEYWORDS)

# --- دالة إرسال الطلب للقناة ---
async def notify_all_drivers(detected_district, original_msg):
    content = original_msg.text or original_msg.caption
    if not content: return

    try:
        customer = original_msg.from_user
        c_link = f"tg://user?id={customer.id}" if customer else "#"
        if customer and customer.username:
            c_link = f"https://t.me/{customer.username}"

        msg_id = getattr(original_msg, "id", getattr(original_msg, "message_id", 0))
        c_id_str = str(original_msg.chat.id).replace("-100", "")
        m_url = f"https://t.me/c/{c_id_str}/{msg_id}"

        alert_text = (
            f"🎯 <b>طلب مشوار جديد</b>\n\n"
            f"📍 <b>المنطقة:</b> {detected_district}\n"
            f"📝 <b>التفاصيل:</b>\n<i>{content}</i>\n\n"
            f"⏰ <b>الوقت:</b> {datetime.now().strftime('%H:%M:%S')}\n"
            f"---"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 مراسلة العميل مباشر", url=c_link)],
            [InlineKeyboardButton("🔗 مصدر الطلب", url=m_url)]
        ])

        await bot_sender.send_message(
            chat_id=CHANNEL_ID,
            text=alert_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        print(f"✅ تم الإرسال للقناة: {detected_district}")
    except Exception as e:
        print(f"❌ خطأ إرسال للقناة: {e}")

# --- المحرك الرئيسي للرادار ---
async def start_radar():
    await user_app.start()
    print("📡 الرادار يعمل الآن (نظام القناة الموحدة)...")
    last_id = {}

    while True:
        try:
            await asyncio.sleep(8) 
            async for dialog in user_app.get_dialogs(limit=40):
                if "GROUP" not in str(dialog.chat.type).upper(): continue

                chat_id = dialog.chat.id
                async for msg in user_app.get_chat_history(chat_id, limit=1):
                    if msg.id > last_id.get(chat_id, 0):
                        last_id[chat_id] = msg.id
                        text = msg.text or msg.caption
                        if not text or (msg.from_user and msg.from_user.is_self): continue

                        if await ai_analyze_message(text):
                            found_d = "غير محدد"
                            text_c = normalize_text(text)
                            for city, districts in CITIES_DISTRICTS.items():
                                for d in districts:
                                    if normalize_text(d) in text_c:
                                        found_d = d
                                        break
                            await notify_all_drivers(found_d, msg)
                await asyncio.sleep(0.3)
        except Exception as e:
            print(f"⚠️ خطأ في الدورة الرئيسية: {e}")
            await asyncio.sleep(10)

# --- خادم الويب ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Radar Active")
    def log_message(self, format, *args): return

def run_health_server():
    httpd = HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), HealthCheckHandler)
    httpd.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    asyncio.run(start_radar())
