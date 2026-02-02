import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client
from telegram import Bot
from telegram.constants import ParseMode
from config import normalize_text, CITIES_DISTRICTS, BOT_TOKEN, get_db_connection

# إعدادات الحساب
API_ID = "36360458"
API_HASH = "daae4628b4b4aac1f0ebfce23c4fa272"
SESSION_STRING = "BAIq0QoApqDmvNIHZnbO2VxSWBdRlJ5SP7S19VeM7rV0Umjc1mO70IQx-Un7FdoYE27YpogRdiB-KXmzvk1zZl_u_CZSC7mQ7M7XdGrpIDvhhAhxVacbpIPary3Zh9J36X1hCZgBhpX9qneOiGxzQcGBdF7XMfsFdYI6_Be2hiPoKUFMtLflsrnWmLCNkKJFhylzubFLMX9KMzn7VnUG5rI9xCfDEae0emFjPA1FqysJV3P2ehe-HanA6GpaIxGOoDGOv_IyyySHFb0UAP4i19Xm5-i5SHUZNiT8e72DX1SLZn40Z5XRgEIdTrfoHDyyOfqvT676UlOLJHiHzQ0c06u6RvPMvAAAAAH-ZrzOAA"
KEYWORDS = ["مشوار", "توصيل", "تكسي", "تاكسي", "مطلوب", "محتاج", "سواق", "ابي يوصل", "احتاج"]

user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# --- خادم الويب لإرضاء Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Radar is Running")

def run_health_check():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()

# --- دالة إرسال التنبيهات ---
async def notify_drivers(city, district, original_msg):
    conn = get_db_connection()
    if not conn: return
    try:
        search_term = normalize_text(district)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM users WHERE role = 'driver' AND (REPLACE(REPLACE(districts, 'ة', 'ه'), 'ال', '') ILIKE %s)",
                (f"%{search_term}%",)
            )
            drivers = [row[0] for row in cur.fetchall()]
        
        if not drivers: return
        customer = original_msg.from_user
        customer_link = f"tg://user?id={customer.id}" if not customer.username else f"https://t.me/{customer.username}"
        alert_text = f"🚨 **طلب مشوار جديد!**\n\n📍 **الحي:** {district}\n👤 **العميل:** {customer.first_name}\n📝 **الطلب:**\n_{original_msg.text}_\n\n📥 [مراسلة العميل خاص]({customer_link})"
        for d_id in drivers:
            try: await bot_sender.send_message(chat_id=d_id, text=alert_text, parse_mode=ParseMode.MARKDOWN)
            except: continue
    finally: conn.close()

# --- الرادار المطور ---
async def start_radar():
    await user_app.start()
    print("✅ الرادار يعمل الآن بنظام السحب المتوازن...")
    
    monitored_chats = []
    async for dialog in user_app.get_dialogs(limit=40):
        if str(dialog.chat.type) in ["ChatType.GROUP", "ChatType.SUPERGROUP", "group", "supergroup"]:
            monitored_chats.append({"id": dialog.chat.id, "title": dialog.chat.title})

    last_id = {}
    while True:
        for chat in monitored_chats:
            try:
                async for msg in user_app.get_chat_history(chat["id"], limit=1):
                    if chat["id"] not in last_id:
                        last_id[chat["id"]] = msg.id
                        continue
                    if msg.id > last_id[chat["id"]]:
                        last_id[chat["id"]] = msg.id
                        if msg.text:
                            text_c = normalize_text(msg.text)
                            if any(normalize_text(k) in text_c for k in KEYWORDS):
                                for city, districts in CITIES_DISTRICTS.items():
                                    for d in districts:
                                        if normalize_text(d) in text_c:
                                            print(f"🎯 صيد: {d}")
                                            await notify_drivers(city, d, msg)
                                            break
                # تأخير بسيط بين كل مجموعة ومجموعة لتجنب الـ Rate Limit
                await asyncio.sleep(1.5) 
            except Exception as e:
                if "420" in str(e): # حظر مؤقت من تليجرام
                    print("⚠️ تليجرام طلب الانتظار، جاري التوقف لـ 30 ثانية...")
                    await asyncio.sleep(30)
                continue
        await asyncio.sleep(5) # انتظار بين الدورات الكاملة

if __name__ == "__main__":
    threading.Thread(target=run_health_check, daemon=True).start()
    asyncio.run(start_radar())
