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
SESSION_STRING = os.environ.get("SESSION_STRING", "BAIq0QoAOD9QpM8asjl1fICVx0vTRH7QjtgTNCEF692Ihz9Xkj_HWnZ6hnl3pv8gN6yFWqMEBhFl7A40uQWQWIsU8KM9or6K-_HsGbe8SP_4AhbIIFU7vrqyo_tuU0SydmvpT8sbSs-RC-yl89Gm5t4EXag2g9Wxr_MQaWIYtJZGWWkVisaDjM8AnUbfD9BDzolvp06qEz-mnsrKZCQKmrPmA_LNhxpqBBcdEJ9EVs4Lwvsh0B7u_ZyOtLhetuwb1YAd1pYNYd00OGwlLuH-8tJc5v5cFbeX6bxT89JMEZVELD2aKhU1XeljAxSieD0F3yL9TsLFglGwu-qsSs7b_073w9e9ZAAAAAH-ZrzOAA")

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
# تعريف الموديل مرة واحدة خارج الدالة لتوفير الموارد
model = genai.GenerativeModel('gemini-1.5-flash')

async def ai_analyze_message(text):
    if not text or len(text.strip()) < 5: return False

    # 1. الفحص الأولي السريع (توفير الكوتا)
    clean_text = normalize_text(text)
    if any(word in clean_text for word in DRIVER_KEYWORDS):
        return False

    # 2. تجهيز "البرومبت" الموجه للهجة السعودية/العربية
    # لاحظ: نطلب منه الرد بكلمة واحدة لتقليل التوكنز المستهلكة
    prompt = f"""
    تصرف كمشرف في قروب تليجرام لسيارات الأجرة في المدينة المنورة.
    حلل الرسالة التالية: "{text}"
    
    الهدف: معرفة هل المرسل "زبون يريد مشوار" أم لا.
    
    القواعد:
    - إذا كان زبون يطلب توصيل، أو يسأل عن سعر، أو يحدد وجهة (مثال: "بكم للمطار"، "ابغى مشوار"، "توصيل للقطار") -> رد بكلمة YES.
    - إذا كان سائق يعرض خدماته (مثال: "موجود"، "جاهز"، "سيارة حديثة") -> رد بكلمة NO.
    - إذا كانت سوالف جانبية أو غير مفهومة -> رد بكلمة NO.
    
    الرد المطلوب: كلمة واحدة فقط (YES أو NO).
    """

    try:
        # استخدام مهلة زمنية (Timeout) قدرها 4 ثوانٍ فقط
        # إذا تأخر الذكاء الاصطناعي، نلغي العملية ونستخدم الكلمات المفتاحية فوراً
        response = await asyncio.wait_for(
            asyncio.to_thread(
                model.generate_content,
                prompt  # 👈 هنا التعديل: استخدامنا البرومبت العربي الدقيق
            ),
            timeout=4.0 
        )

        # تنظيف الرد للتأكد من خلوه من المسافات أو النقاط
        result = response.text.strip().upper().replace(".", "")
        return "YES" in result

    except asyncio.TimeoutError:
        print(f"⚠️ تجاوز AI المهلة الزمنية: نعود للنظام اليدوي.")
        return any(word in clean_text for word in SAFE_KEYWORDS)

    except Exception as e:
        print(f"⚠️ خطأ فني في AI: {e}")
        # البديل التلقائي بالكلمات المفتاحية
        return any(word in clean_text for word in SAFE_KEYWORDS)

# --- دالة بث الطلب لجميع السائقين ---


async def notify_all_drivers(detected_district, original_msg):
    content = original_msg.text or original_msg.caption
    if not content: return

    conn = get_db_connection()
    if not conn: return

    try:
        with conn.cursor() as cur:
            query = """
                SELECT user_id, subscription_expiry 
                FROM users 
                WHERE role = 'driver' 
                AND is_blocked = FALSE 
                AND (districts ILIKE %s OR districts = 'الكل' OR districts IS NULL)
            """
            cur.execute(query, (f"%{detected_district}%",))
            drivers_data = cur.fetchall()

        if not drivers_data: return

        customer = original_msg.from_user
        # ✅ إصلاح رابط الراكب: التعامل مع عدم وجود يوزر نيم بشكل آمن
        if customer:
            if customer.username:
                customer_link = f"https://t.me/{customer.username}"
            else:
                customer_link = f"tg://user?id={customer.id}"
        else:
            customer_link = "#"

        # تجهيز روابط الرسالة
        msg_id = getattr(original_msg, "id", 0)
        chat_id_str = str(original_msg.chat.id).replace("-100", "")
        msg_url = f"https://t.me/c/{chat_id_str}/{msg_id}"
        admin_contact_link = "https://t.me/x3FreTx"

        now = datetime.now()

        for d_id, expiry in drivers_data:
            try:
                # التحقق من حالة الاشتراك
                is_active = expiry and expiry > now

                if is_active:
                    # ✅ رسالة المشترك
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
                    # ❌ رسالة غير المشترك
                    alert_text = (
                        f"🆕 <b>طلب مشوار جديد مكتشف</b>\n\n"
                        f"📍 <b>المنطقة:</b> {detected_district}\n"
                        f"📝 <b>نص الطلب:</b>\n<i>{content}</i>\n\n"
                        f"⚠️ <b>هذا الطلب متاح للمشتركين فقط.</b>"
                    )
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("💳 تفعيل الحساب", url=admin_contact_link)]
                    ])

                await bot_sender.send_message(
                    chat_id=d_id,
                    text=alert_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                await asyncio.sleep(0.05) 

            except Exception as send_error:
                # طباعة الخطأ لمعرفة لماذا لا تصل الرسالة للمشتركين
                print(f"⚠️ خطأ أثناء الإرسال للسائق {d_id}: {send_error}")
                continue

    except Exception as e:
        print(f"❌ خطأ عام في البث: {e}")
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
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"AI Radar is Live and Running")

    def do_HEAD(self):
        # Render يرسل هذا الطلب للتأكد من أن السيرفر يعمل
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        # كتم السجلات المزعجة في لوحة تحكم Render
        return

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    httpd = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    httpd.serve_forever()

if __name__ == "__main__":
    # تشغيل خادم الويب في خيط منفصل
    threading.Thread(target=run_health_server, daemon=True).start()
    # تشغيل الرادار
    asyncio.run(start_radar())