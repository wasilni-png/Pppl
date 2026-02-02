import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from telegram import Bot
from telegram.constants import ParseMode

# --- الإعدادات من ملف config الخاص بك ---
from config import get_db_connection, normalize_text, CITIES_DISTRICTS, BOT_TOKEN

# إعدادات الحساب (UserBot)
API_ID = "36360458"
API_HASH = "daae4628b4b4aac1f0ebfce23c4fa272"
# الصق الكود الطويل الذي أرسلته هنا
SESSION_STRING = "BAIq0QoApqDmvNIHZnbO2VxSWBdRlJ5SP7S19VeM7rV0Umjc1mO70IQx-Un7FdoYE27YpogRdiB-KXmzvk1zZl_u_CZSC7mQ7M7XdGrpIDvhhAhxVacbpIPary3Zh9J36X1hCZgBhpX9qneOiGxzQcGBdF7XMfsFdYI6_Be2hiPoKUFMtLflsrnWmLCNkKJFhylzubFLMX9KMzn7VnUG5rI9xCfDEae0emFjPA1FqysJV3P2ehe-HanA6GpaIxGOoDGOv_IyyySHFb0UAP4i19Xm5-i5SHUZNiT8e72DX1SLZn40Z5XRgEIdTrfoHDyyOfqvT676UlOLJHiHzQ0c06u6RvPMvAAAAAH-ZrzOAA"

KEYWORDS = ["مشوار", "توصيل", "تكسي", "تاكسي", "مطلوب", "محتاج", "سواق", "ابي يوصل"]

user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# --- خادم وهمي لإرضاء منصة Render ومنع إغلاق التطبيق ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active and monitoring...")

def run_health_check():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()

# --- دالة إرسال الإشعارات للسائقين (فتح خاص العميل) ---
async def notify_drivers(city, district, original_msg):
    conn = get_db_connection()
    if not conn: 
        print("❌ فشل الاتصال بقاعدة البيانات")
        return
    
    try:
        # توحيد النص للبحث بمرونة أكبر (ة/هـ)
        search_term = district.replace('ة', 'ه').replace('أ', 'ا')
        
        with conn.cursor() as cur:
            cur.execute(
                """SELECT user_id FROM users 
                   WHERE role = 'driver' 
                   AND (REPLACE(REPLACE(districts, 'ة', 'ه'), 'أ', 'ا') ILIKE %s)""",
                (f"%{search_term}%",)
            )
            drivers = [row[0] for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return
    finally: conn.close()

    print(f"📡 محاولة إرسال لـ {len(drivers)} سائق في حي {district}...")

    if not drivers: return

    customer = original_msg.from_user
    customer_name = customer.first_name if customer.first_name else "عميل"
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
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"⚠️ فشل الإرسال للسائق {d_id}: {e}")
            continue
            
    print(f"✅ تم إرسال التنبيه لـ {sent_count} سائق بنجاح.")


# --- رادار مراقبة المجموعات ---
@user_app.on_message((filters.group | filters.supergroup) & ~filters.service)
async def scraper_handler(client, message):
    if not message.text: return
    
    # سطر للتشخيص - سيطبع كل رسالة تصل من أي مجموعة
    print(f"📩 رسالة جديدة من [{message.chat.title}]: {message.text}", flush=True)
    
    text = normalize_text(message.text)
    # ... باقي الكود

    
    if any(key in text for key in KEYWORDS):
        for city, districts in CITIES_DISTRICTS.items():
            for dist in districts:
                if normalize_text(dist) in text:
                    print(f"🎯 صيد جديد في حي: {dist}")
                    await notify_drivers(city, dist, message)
                    break

async def start_bot():
    print("🚀 جاري تشغيل النظام على Render...")
    threading.Thread(target=run_health_check, daemon=True).start()
    await user_app.start()
    print("✅ الرادار يعمل ويراقب جميع المجموعات!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(start_bot())
