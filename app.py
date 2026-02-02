import asyncio
import threading
import httpx
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from telegram import Bot
from telegram.constants import ParseMode

# استيراد الإعدادات
from config import get_db_connection, normalize_text, CITIES_DISTRICTS, BOT_TOKEN

# إعدادات الحساب
API_ID = "36360458"
API_HASH = "daae4628b4b4aac1f0ebfce23c4fa272"
SESSION_STRING = "BAIq0QoApqDmvNIHZnbO2VxSWBdRlJ5SP7S19VeM7rV0Umjc1mO70IQx-Un7FdoYE27YpogRdiB-KXmzvk1zZl_u_CZSC7mQ7M7XdGrpIDvhhAhxVacbpIPary3Zh9J36X1hCZgBhpX9qneOiGxzQcGBdF7XMfsFdYI6_Be2hiPoKUFMtLflsrnWmLCNkKJFhylzubFLMX9KMzn7VnUG5rI9xCfDEae0emFjPA1FqysJV3P2ehe-HanA6GpaIxGOoDGOv_IyyySHFb0UAP4i19Xm5-i5SHUZNiT8e72DX1SLZn40Z5XRgEIdTrfoHDyyOfqvT676UlOLJHiHzQ0c06u6RvPMvAAAAAH-ZrzOAA"

KEYWORDS = ["مشوار", "توصيل", "تكسي", "تاكسي", "مطلوب", "محتاج", "سواق", "ابي يوصل"]
RENDER_URL = "https://pppl-odrd.onrender.com/"

user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# 1. خادم الويب (للـ Render Health Check)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Bot is active")

def run_health_check():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()

# 2. إرسال الإشعارات
async def notify_drivers(city, district, original_msg):
    conn = get_db_connection()
    if not conn: return
    try:
        search_term = normalize_text(district)
        with conn.cursor() as cur:
            cur.execute(
                """SELECT user_id FROM users 
                   WHERE role = 'driver' 
                   AND (REPLACE(REPLACE(districts, 'ة', 'ه'), 'ال', '') ILIKE %s)""",
                (f"%{search_term}%",)
            )
            drivers = [row[0] for row in cur.fetchall()]
    except: return
    finally: conn.close()

    if not drivers: return

    customer = original_msg.from_user
    customer_name = customer.first_name if customer.first_name else "عميل"
    customer_link = f"tg://user?id={customer.id}" if not customer.username else f"https://t.me/{customer.username}"
    
    alert_text = (
        f"🚨 **طلب مشوار جديد!**\n\n"
        f"📍 **الحي:** {district}\n"
        f"👤 **العميل:** {customer_name}\n"
        f"📝 **الطلب:**\n_{original_msg.text}_\n\n"
        f"📥 [مراسلة العميل خاص]({customer_link})"
    )

    for d_id in drivers:
        try:
            await bot_sender.send_message(chat_id=d_id, text=alert_text, parse_mode=ParseMode.MARKDOWN)
        except: continue

# 3. الرادار (تم إصلاح الفلتر هنا)
@user_app.on_message(filters.group & ~filters.service)
async def scraper_handler(client, message):
    if not message.text: return
    
    # طباعة الرسائل في السجلات للمراقبة
    print(f"📩 من {message.chat.title}: {message.text}", flush=True)

    clean_text = normalize_text(message.text)
    
    if any(normalize_text(key) in clean_text for key in KEYWORDS):
        for city, districts in CITIES_DISTRICTS.items():
            for dist in districts:
                if normalize_text(dist) in clean_text:
                    print(f"🎯 تم الصيد: حي {dist}", flush=True)
                    await notify_drivers(city, dist, message)
                    return

async def start_bot():
    threading.Thread(target=run_health_check, daemon=True).start()
    await user_app.start()
    async for dialog in user_app.get_dialogs(limit=30): pass
    print("✅ النظام جاهز ومراقب المجموعات يعمل...", flush=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(start_bot())
