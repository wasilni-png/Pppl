import asyncio
import threading
import sys
import os
import logging
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
import google.generativeai as genai
from datetime import datetime

# --- إعداد السجلات ---
logging.basicConfig(level=logging.INFO)
# كتم السجلات المزعجة
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# --- استيراد الإعدادات ---
try:
    from config import normalize_text, CITIES_DISTRICTS, BOT_TOKEN
    print("✅ تم تحميل الإعدادات بنجاح")
except Exception as e:
    print(f"❌ خطأ في تحميل ملف config.py: {e}")
    sys.exit(1)

# --- متغيرات البيئة ---
API_ID = os.environ.get("API_ID", "36360458")
API_HASH = os.environ.get("API_HASH", "daae4628b4b4aac1f0ebfce23c4fa272")
SESSION_STRING = os.environ.get("SESSION_STRING", "BAIq0QoAOD9QpM8asjl1fICVx0vTRH7QjtgTNCEF692Ihz9Xkj_HWnZ6hnl3pv8gN6yFWqMEBhFl7A40uQWQWIsU8KM9or6K-_HsGbe8SP_4AhbIIFU7vrqyo_tuU0SydmvpT8sbSs-RC-yl89Gm5t4EXag2g9Wxr_MQaWIYtJZGWWkVisaDjM8AnUbfD9BDzolvp06qEz-mnsrKZCQKmrPmA_LNhxpqBBcdEJ9EVs4Lwvsh0B7u_ZyOtLhetuwb1YAd1pYNYd00OGwlLuH-8tJc5v5cFbeX6bxT89JMEZVELD2aKhU1XeljAxSieD0F3yL9TsLFglGwu-qsSs7b_073w9e9ZAAAAAH-ZrzOAA")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDvEF8WDhGt6nDWjqxgix0Rb8qaAmtEPbk")
CHANNEL_ID = -1003763324430 

# --- إعداد Gemini 1.5 Flash (السريع) ---
genai.configure(api_key=GEMINI_API_KEY)

# إعدادات لزيادة السرعة وتقليل الإبداع (نريد دقة فقط)
generation_config = {
  "temperature": 0.1,
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 5, # رد بكلمة واحدة فقط
}

ai_model = genai.GenerativeModel(
  model_name="gemini-1.5-flash",
  generation_config=generation_config,
)

# --- عملاء تليجرام ---
user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# ---------------------------------------------------------
# 1. قوائم الفلترة المحلية (للحماية والسرعة)
# ---------------------------------------------------------

# قائمة 1: كلمات تدل أن المرسل سائق أو إعلان (حظر فوري)
BLOCK_KEYWORDS = [
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
    "مرحباً بك", "مرحبا بك", "تنبيه", "محظور", "يُمنع", "يمنع", "بالتوفيق للجميع",
    "http", "t.me", ".com", "رابط القناة", "اخلاء مسؤولية", "ذمة"
]

# قائمة 2: كلمات خارج السياق (مثل المستشفيات والعيادات) - حظر فوري
IRRELEVANT_TOPICS = [
    "عيادة", "عياده", "اسنان", "أسنان", "دكتور", "طبيب", "مستشفى", "مستوصف",
    "علاج", "تركيب", "تقويم", "خلع", "حشو", "تنظيف", "استفسار", "افضل", "أفضل",
    "تجربة", "مين جرب", "رأيكم", "تنصحون", "ورشة", "سمكري", "قطع غيار"
]

# ---------------------------------------------------------
# 2. المحرك الهجين (Hybrid Engine)
# ---------------------------------------------------------

async def analyze_message_hybrid(text):
    if not text or len(text) < 5: return False
    
    clean_text = normalize_text(text)

    # --- الحل هنا: كشف المسار المباشر (Regex) ---
    # هذا النمط يبحث عن كلمة (من) متبوعة بكلام ثم (الى/إلى/لـ)
    route_pattern = r"(^|\s)من\s+.*?\s+(إلى|الى|لـ|للحرم|للمطار)(\s|$)"
    if re.search(route_pattern, clean_text):
        # إذا وجدنا حي "الحزام" وحي "الحمراء" في نفس النص، فهذا طلب مؤكد
        return True 

    # المرحلة 1: فلتر الحظر (سائق أو إعلان)
        
    # ... باقي الكود (الذكاء الاصطناعي)
    """
    يفحص الرسالة على 3 مراحل:
    1. فلتر الإعلانات والسائقين (محلي).
    2. فلتر المواضيع الجانبية مثل الأسنان (محلي).
    3. التحقق من نية الطلب عبر Gemini Flash (سحابي سريع).
    """
    if not text or len(text) < 5 or len(text) > 400: return False
    
    clean_text = normalize_text(text)

    # المرحلة 1: هل المرسل سائق أو إعلان؟
    if any(k in clean_text for k in BLOCK_KEYWORDS):
        return False

    # المرحلة 2: هل الموضوع طبي أو استفسار عام؟
    if any(k in clean_text for k in IRRELEVANT_TOPICS):
        return False

    # المرحلة 3: Gemini Flash للفصل النهائي
    # هذا الموديل سريع جداً ويفهم السياق
    prompt = f"""
    Context: You are an elite AI Traffic Controller for a specialized Madinah Taxi & Delivery Telegram group. 
    Your sole purpose is to filter messages to find REAL CUSTOMERS who need a ride or delivery service.

    Task: Categorize the message and reply ONLY with 'YES' or 'NO'.

    [STRICT YES - CUSTOMER REQUEST CRITERIA]
    1. Direct Ride Needs: (e.g., "مطلوب سواق", "كابتن متاح؟", "توصيل للمطار").
    2. Route Identification: Mentioning a path or destination even without a verb (e.g., "من العزيزية إلى الحرم", "باقدو للمطار", "مستشفى الولادة").
    3. Availability Inquiries: Asking for drivers in a specific spot (e.g., "مين قريب من قطار الحرمين؟", "في أحد في شوران؟").
    4. Delivery & Logistics: Moving items (e.g., "توصيل طلبية", "أغراض من ممشى الهجرة", "توصيل طرد من زاجل").
    5. Pricing by Customer: (e.g., "من الحزام بـ 20", "يوديني الجامعة بـ 30").

    [STRICT NO - REJECTION CRITERIA]
    1. Religious & Social Wisdom: DO NOT accept quotes, Islamic texts, or morning/evening greetings (e.g., ابن القيم، ابن تيمية، أذكار، "الكلمة الطيبة"، "صباح الخير"). These are SPAM for this bot.
    2. Driver Promotions: Reject drivers offering their services (e.g., "سواق موجود", "سيارة نظيفة", "موجود توصيل مشاوير"، "للتواصل خاص").
    3. Employment Seeking: People looking for work as drivers.
    4. General Questions: Asking about weather, bus times, or hospital opening hours (e.g., "متى يفتح المستشفى؟", "باصات المدينة وين؟").
    5. Admin & Safety: Group rules, link sharing, or warnings about scammers.

    [GOLDEN RULES FOR DECISION]
    - IF the text is a Wisdom/Quote or religious content: ALWAYS NO.
    - IF the sender is OFFERING a service (Driver): ALWAYS NO.
    - IF the sender is SEEKING a service (Passenger/Customer): ALWAYS YES.
    - Madinah Context: Recognize local neighborhoods (العزيزية، الهجرة، باقدو، الحزام، شوران، الدعيثة، سلطانة).
    - Format Neutrality: Ignore fancy formatting (emojis, lines, bold text). Focus ONLY on the "Intent".

    Text to analyze: "{text}"

    Final Output (Reply ONLY with 'YES' or 'NO'):
    """



    try:
        # استخدام asyncio.to_thread لمنع تعليق البوت أثناء انتظار جوجل
        response = await asyncio.to_thread(
            ai_model.generate_content, 
            prompt
        )
        result = response.text.strip().upper().replace(".", "")
        return "YES" in result
        
    except Exception as e:
        print(f"⚠️ تجاوز AI (فشل الاتصال): {e}")
        # في حال فشل النت، نستخدم الفلتر اليدوي للطوارئ
        return manual_fallback_check(clean_text)

def manual_fallback_check(clean_text):
    # خطة بديلة في حال تعطل الذكاء الاصطناعي
    order_words = ["ابي", "ابغي", "محتاج", "نبي", "مطلوب", "بكم"]
    service_words = ["سواق", "توصيل", "مشوار", "يوديني", "يوصلني"]
    has_order = any(w in clean_text for w in order_words)
    has_service = any(w in clean_text for w in service_words)
    has_route = "من " in clean_text and ("الى" in clean_text or "لي" in clean_text)
    
    return (has_order and has_service) or has_route

# ---------------------------------------------------------
# 3. نظام الإرسال للقناة (الآمن)
# ---------------------------------------------------------

async def notify_channel(detected_district, original_msg):
    content = original_msg.text or original_msg.caption
    if not content: return

    try:
        customer = original_msg.from_user
        # استخراج المعرفات اللازمة
        customer_id = customer.id if customer else 0
        msg_id = getattr(original_msg, "id", getattr(original_msg, "message_id", 0))
        chat_id_str = str(original_msg.chat.id).replace("-100", "")
        
        # --- الإعدادات (تأكد من مطابقة يوزر البوت) ---
        # استبدل 'YourBotUsername' بيوزر بوتك بدون علامة @
        bot_username = "Mishwariibot" 

        # تجهيز الروابط العميقة (Deep Links)
        # الرابط الأول لمراسلة العميل
        gate_contact = f"https://t.me/{bot_username}?start=contact_{customer_id}"
        # الرابط الثاني لمصدر الطلب في الجروب
        gate_source = f"https://t.me/{bot_username}?start=source_{chat_id_str}_{msg_id}"

        buttons = [
            [InlineKeyboardButton("💬 مراسلة العميل (للمشتركين)", url=gate_contact)],
            [InlineKeyboardButton("🔗 مصدر الطلب (للمشتركين)", url=gate_source)],
            [InlineKeyboardButton("💳 للاشتراك وتفعيل الحساب", url="https://t.me/x3FreTx")]
        ]

        keyboard = InlineKeyboardMarkup(buttons)

        alert_text = (
            f"🎯 <b>طلب مشوار جديد</b>\n\n"
            f"📍 <b>المنطقة:</b> {detected_district}\n"
            f"📝 <b>التفاصيل:</b>\n<i>{content}</i>\n\n"
            f"⏰ <b>الوقت:</b> {datetime.now().strftime('%H:%M:%S')}\n"
            f"⚠️ <i>الروابط أعلاه تفتح للمشتركين فقط.</i>"
        )

        await bot_sender.send_message(
            chat_id=CHANNEL_ID,
            text=alert_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        print(f"✅ تم الإرسال للقناة بروابط مشفرة: {detected_district}")

    except Exception as e:
        print(f"❌ خطأ إرسال للقناة: {e}")

# ---------------------------------------------------------
# 4. الرادار الرئيسي
# ---------------------------------------------------------

async def start_radar():
    await user_app.start()
    print("🚀 الرادار الهجين يعمل الآن (Flash AI + Local Rules)...")
    last_id = {}

    while True:
        try:
            # انتظار متوازن (5 ثواني)
            await asyncio.sleep(5) 
            
            async for dialog in user_app.get_dialogs(limit=50):
                if "GROUP" not in str(dialog.chat.type).upper(): continue

                chat_id = dialog.chat.id
                async for msg in user_app.get_chat_history(chat_id, limit=1):
                    # التأكد أن الرسالة جديدة وليست من البوت نفسه
                    if msg.id > last_id.get(chat_id, 0):
                        last_id[chat_id] = msg.id
                        text = msg.text or msg.caption
                        
                        if not text or (msg.from_user and msg.from_user.is_self): continue

                        # التحليل الهجين
                        if await analyze_message_hybrid(text):
                            # استخراج الحي محلياً (سريع جداً)
                            found_d = "عام"
                            text_c = normalize_text(text)
                            for city, districts in CITIES_DISTRICTS.items():
                                for d in districts:
                                    # بحث دقيق عن اسم الحي
                                    if normalize_text(d) in text_c:
                                        found_d = d
                                        break
                            
                            await notify_channel(found_d, msg)
                            
                await asyncio.sleep(0.1) 
        except Exception as e:
            print(f"⚠️ خطأ في الدورة الرئيسية: {e}")
            await asyncio.sleep(5)

# --- خادم الويب (Health Check) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Hybrid Radar is Running")
    def log_message(self, format, *args): return

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    httpd = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    httpd.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    asyncio.run(start_radar())