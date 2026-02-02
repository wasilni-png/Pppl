import asyncio
import threading
import httpx  # تأكد من إضافتها في requirements.txt
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from telegram import Bot
from telegram.constants import ParseMode

# --- الإعدادات من ملف config الخاص بك ---
from config import get_db_connection, normalize_text, CITIES_DISTRICTS, BOT_TOKEN

# --- إعدادات الحساب (UserBot) ---
API_ID = "36360458"
API_HASH = "daae4628b4b4aac1f0ebfce23c4fa272"
SESSION_STRING = "BAIq0QoApqDmvNIHZnbO2VxSWBdRlJ5SP7S19VeM7rV0Umjc1mO70IQx-Un7FdoYE27YpogRdiB-KXmzvk1zZl_u_CZSC7mQ7M7XdGrpIDvhhAhxVacbpIPary3Zh9J36X1hCZgBhpX9qneOiGxzQcGBdF7XMfsFdYI6_Be2hiPoKUFMtLflsrnWmLCNkKJFhylzubFLMX9KMzn7VnUG5rI9xCfDEae0emFjPA1FqysJV3P2ehe-HanA6GpaIxGOoDGOv_IyyySHFb0UAP4i19Xm5-i5SHUZNiT8e72DX1SLZn40Z5XRgEIdTrfoHDyyOfqvT676UlOLJHiHzQ0c06u6RvPMvAAAAAH-ZrzOAA"

# الكلمات الدلالية ورابط موقعك في ريندر
KEYWORDS = ["مشوار", "توصيل", "تكسي", "تاكسي", "مطلوب", "محتاج", "سواق", "ابي يوصل"]
RENDER_URL = "https://pppl-odrd.onrender.com/"  # رابط موقعك للتنشيط الذاتي

# تعريف العملاء
user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# ---------------------------------------------------------
# 1. خادم ويب وهمي (Health Check)
# ---------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active and monitoring...")

def run_health_check():
    # Render يبحث عن المنفذ 10000
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()

# ---------------------------------------------------------
# 2. نظام التنشيط الذاتي (Keep Alive)
# ---------------------------------------------------------
async def keep_alive():
    print("⏳ بدء نظام التنشيط الذاتي...")
    await asyncio.sleep(30)  # انتظار بدء السيرفر
    async with httpx.AsyncClient() as client:
        while True:
            try:
                response = await client.get(RENDER_URL)
                print(f"🔄 Self-Ping: {response.status_code} - البوت مستيقظ", flush=True)
            except Exception as e:
                print(f"⚠️ فشل التنشيط الذاتي: {e}", flush=True)
            await asyncio.sleep(600)  # تكرار كل 10 دقائق

# ---------------------------------------------------------
# 3. دالة إرسال الإشعارات للسائقين
# ---------------------------------------------------------
async def notify_drivers(city, district, original_msg):
    conn = get_db_connection()
    if not conn: 
        print("❌ فشل الاتصال بقاعدة البيانات", flush=True)
        return
    
    drivers = []
    try:
        # إصلاح مشكلة البحث (التاء المربوطة والهاء + الألف)
        search_term = district.replace('ة', 'ه').replace('أ', 'ا')
        
        with conn.cursor() as cur:
            # استعلام ذكي يتجاهل الفروقات في الكتابة
            cur.execute(
                """SELECT user_id FROM users 
                   WHERE role = 'driver' 
                   AND (REPLACE(REPLACE(districts, 'ة', 'ه'), 'أ', 'ا') ILIKE %s)""",
                (f"%{search_term}%",)
            )
            drivers = [row[0] for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ خطأ في الاستعلام (DB Error): {e}", flush=True)
        return
    finally: conn.close()

    print(f"🔎 الحي: {district} | السائقين المطابقين: {len(drivers)}", flush=True)

    if not drivers: return

    # تجهيز بيانات العميل والرابط المباشر
    customer = original_msg.from_user
    customer_name = customer.first_name if customer.first_name else "عميل"
    # رابط يفتح المحادثة الخاصة فوراً
    customer_link = f"tg://user?id={customer.id}" if not customer.username else f"https://t.me/{customer.username}"
    
    alert_text = (
        f"🚨 **طلب مشوار جديد!**\n\n"
        f"📍 **الحي:** {district}\n"
        f"👤 **العميل:** {customer_name}\n"
        f"📝 **الطلب:**\n_{original_msg.text}_\n\n"
        f"📥 [اضغط هنا لمراسلة العميل خاص]({customer_link})"
    )

    sent_count = 0
    for d_id in drivers:
        try:
            await bot_sender.send_message(chat_id=d_id, text=alert_text, parse_mode=ParseMode.MARKDOWN)
            sent_count += 1
            await asyncio.sleep(0.05) # تأخير بسيط لتجنب الحظر
        except Exception as e:
            print(f"⚠️ لم تصل للسائق {d_id}: {e}", flush=True)
            continue
            
    print(f"✅ تم إرسال الإشعار إلى {sent_count} سائق.", flush=True)

# ---------------------------------------------------------
# 4. رادار مراقبة المجموعات (Scraper)
# ---------------------------------------------------------
@user_app.on_message(filters.group & ~filters.service)
async def scraper_handler(client, message):
    if not message.text: return
    
    # توحيد النص لتسهيل المطابقة
    text = normalize_text(message.text)
    
    # التحقق من وجود كلمات مفتاحية
    if any(key in text for key in KEYWORDS):
        # البحث عن اسم الحي داخل الرسالة
        for city, districts in CITIES_DISTRICTS.items():
            for dist in districts:
                # توحيد اسم الحي أيضاً قبل المقارنة
                if normalize_text(dist) in text:
                    print(f"🎯 تم صيد طلب في حي: {dist}", flush=True)
                    await notify_drivers(city, dist, message)
                    return # نكتفي بأول حي يتم اكتشافه

# ---------------------------------------------------------
# 5. تشغيل النظام بالكامل
# ---------------------------------------------------------
async def start_bot():
    print("🚀 جاري تشغيل النظام على Render...", flush=True)
    
    # تشغيل السيرفر الوهمي في Thread منفصل
    threading.Thread(target=run_health_check, daemon=True).start()
    
    # تشغيل مهمة التنشيط الذاتي في الخلفية
    asyncio.create_task(keep_alive())
    
    # بدء تشغيل حساب الرادار
    await user_app.start()
    
    # خطوة مهمة: تحديث قائمة المحادثات لضمان رؤية المجموعات
    print("🔄 جاري تحديث قائمة المجموعات...", flush=True)
    async for dialog in user_app.get_dialogs(limit=50):
        # مجرد المرور عليها يكفي لتحديث الكاش
        pass
        
    print("✅ الرادار يعمل الآن ويراقب جميع المجموعات بنجاح!", flush=True)
    
    # إبقاء البوت يعمل للأبد
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(start_bot())
