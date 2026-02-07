import asyncio
import threading
import sys
import os
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from datetime import datetime

# --- إعدادات السجلات (Logging) ---
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

# --- إعدادات الحساب ---
API_ID = os.environ.get("API_ID", "36360458")
API_HASH = os.environ.get("API_HASH", "daae4628b4b4aac1f0ebfce23c4fa272")
SESSION_STRING = os.environ.get("SESSION_STRING", "BAIq0QoApqDmvNIHZnbO2VxSWBdRlJ5SP7S19VeM7rV0Umjc1mO70IQx-Un7FdoYE27YpogRdiB-KXmzvk1zZl_u_CZSC7mQ7M7XdGrpIDvhhAhxVacbpIPary3Zh9J36X1hCZgBhpX9qneOiGxzQcGBdF7XMfsFdYI6_Be2hiPoKUFMtLflsrnWmLCNkKJFhylzubFLMX9KMzn7VnUG5rI9xCfDEae0emFjPA1FqysJV3P2ehe-HanA6GpaIxGOoDGOv_IyyySHFb0UAP4i19Xm5-i5SHUZNiT8e72DX1SLZn40Z5XRgEIdTrfoHDyyOfqvT676UlOLJHiHzQ0c06u6RvPMvAAAAAH-ZrzOAA")

# --- قوائم الكلمات المفتاحية (صمام الأمان البديل للـ AI) ---
# كلمات السائقين (إذا وُجدت تُرفض الرسالة فوراً)
DRIVER_KEYWORDS = [
    "متواجد", "متاح", "شغال", "جاهز", "أسعارنا", "سيارة نظيفة", "نقل عفش", 
    "دربك سمح", "توصيل مشاوير", "أوصل", "اوصل", "اتصال", "واتساب", "للتواصل"
]

# كلمات العملاء (إذا وُجدت تُقبل الرسالة كطلب)
SAFE_KEYWORDS = [
    "مشوار", "توصيل", "يوصلني", "سواق", "كابتن", "كبتن", "سيارة", "سياره", "رايح", "روحه", "نقل",
    "طلب", "طلبات", "غرض", "اغراض", "أغراض", "طرد", "شحنة", "شحنه", "كرتون", "مطعم", "من مطعم",
    "بكم", "كم", "سعر", "السعر", "بكم يوصل", "تكلفة", "بكم توديني", "مطلوب", "محتاج",
    "المطار", "الحرم", "البلد", "القطار", "جامعة", "مشاوير"
]

# إعداد العملاء (Client & Bot)
user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# --- دالة تحليل الرسالة (Keyword Engine) ---
async def is_valid_request(text):
    if not text or len(text.strip()) < 5: 
        return False
    
    # تنظيف النص (إزالة الهمزات والتشكيل لتوحيد البحث)
    clean_text = normalize_text(text)
    
    # 1. استبعاد إعلانات السائقين
    if any(word in clean_text for word in DRIVER_KEYWORDS):
        return False

    # 2. تأكيد طلبات الزبائن
    if any(word in clean_text for word in SAFE_KEYWORDS):
        return True
    
    return False

# --- دالة بث الطلب للسائقين ---
async def notify_all_drivers(detected_district, original_msg):
    content = original_msg.text or original_msg.caption
    if not content: return

    conn = get_db_connection()
    if not conn: return

    try:
        with conn.cursor() as cur:
            # جلب السائقين مع حالة اشتراكهم (تاريخ الانتهاء)
            cur.execute("""
                SELECT user_id, subscription_expiry 
                FROM users 
                WHERE role = 'driver' AND is_blocked = FALSE
            """)
            drivers_data = cur.fetchall()

        if not drivers_data: return

        customer = original_msg.from_user
        customer_name = (customer.first_name or "عميل") if customer else "عميل"
        
        # روابط التواصل والرسالة
        customer_link = f"tg://user?id={customer.id}" if customer and not customer.username else f"https://t.me/{customer.username}" if customer else "#"
        msg_id = getattr(original_msg, "id", getattr(original_msg, "message_id", 0))
        chat_id_str = str(original_msg.chat.id).replace("-100", "")
        msg_url = f"https://t.me/c/{chat_id_str}/{msg_id}"
        admin_contact_link = "https://t.me/x3FreTx"

        now = datetime.now()

        for d_id, expiry in drivers_data:
            try:
                # التحقق من صلاحية الاشتراك
                is_active = expiry and expiry > now
                
                if is_active:
                    # لوحة المشترك (روابط مباشرة)
                    alert_text = (
                        f"🌟 <b>طلب مشوار جديد (للمشتركين)</b>\n\n"
                        f"📍 <b>المنطقة:</b> {detected_district}\n"
                        f"📝 <b>الطلب:</b>\n<i>{content}</i>"
                    )
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔗 عرض الطلب في الجروب", url=msg_url)],
                        [InlineKeyboardButton("💬 مراسلة الراكب مباشرة", url=customer_link)]
                    ])
                else:
                    # لوحة غير المشترك (رابط الإدارة)
                    alert_text = (
                        f"🆕 <b>طلب مشوار جديد مكتشف</b>\n\n"
                        f"📍 <b>المنطقة:</b> {detected_district}\n"
                        f"📝 <b>نص الطلب:</b>\n<i>{content}</i>\n\n"
                        f"⚠️ <b>الروابط مخفية للمشتركين فقط.</b>"
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
                await asyncio.sleep(0.05) 
            except Exception: continue

        print(f"🚀 تم البث لـ {len(drivers_data)} سائق.")
    finally:
        release_db_connection(conn)

# --- المحرك الرئيسي للرادار ---
async def start_radar():
    await user_app.start()
    print("📡 الرادار يعمل الآن بالاعتماد على الكلمات المفتاحية...")

    last_id = {}
    
    # تهيئة أولية لتجنب الرسائل القديمة
    async for dialog in user_app.get_dialogs(limit=30):
        if "GROUP" in str(dialog.chat.type).upper():
            async for msg in user_app.get_chat_history(dialog.chat.id, limit=1):
                last_id[dialog.chat.id] = msg.id

    while True:
        try:
            await asyncio.sleep(15) # دورة هادئة لتجنب الـ Flood
            
            async for dialog in user_app.get_dialogs(limit=40):
                if "GROUP" not in str(dialog.chat.type).upper(): 
                    continue
                
                chat_id = dialog.chat.id
                try:
                    async for msg in user_app.get_chat_history(chat_id, limit=1):
                        if msg.id > last_id.get(chat_id, 0):
                            last_id[chat_id] = msg.id
                            
                            text = msg.text or msg.caption
                            if not text or (msg.from_user and msg.from_user.is_self): 
                                continue

                            # الفحص بواسطة محرك الكلمات
                            if await is_valid_request(text):
                                found_d = "غير محدد"
                                text_c = normalize_text(text)
                                for city, districts in CITIES_DISTRICTS.items():
                                    for d in districts:
                                        if normalize_text(d) in text_c:
                                            found_d = d
                                            break
                                
                                print(f"🎯 طلب مكتشف في [{dialog.chat.title}]")
                                await notify_all_drivers(found_d, msg)
                    
                    await asyncio.sleep(0.6) # تأخير بين كل مجموعة وأخرى

                except Exception as e:
                    if "420" in str(e): # FloodWait
                        wait_sec = int(''.join(filter(str.isdigit, str(e))) or 30)
                        await asyncio.sleep(wait_sec)
                    continue
        except Exception as e:
            print(f"⚠️ خطأ في المحرك: {e}")
            await asyncio.sleep(20)

# --- خادم الويب (Health Check) لـ Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Radar is Active")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
        
    def log_message(self, format, *args):
        return

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), HealthCheckHandler).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    asyncio.run(start_radar())
