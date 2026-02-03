import asyncio
import threading
import sys
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client
from telegram import Bot
from telegram.constants import ParseMode
import google.generativeai as genai

# استيراد الإعدادات
try:
    from config import normalize_text, CITIES_DISTRICTS, BOT_TOKEN, get_db_connection
    print("✅ تم تحميل ملف config.py")
except Exception as e:
    print(f"❌ خطأ في config.py: {e}")
    sys.exit(1)

# إعدادات الحساب
API_ID = "36360458"
API_HASH = "daae4628b4b4aac1f0ebfce23c4fa272"
SESSION_STRING = "BAIq0QoApqDmvNIHZnbO2VxSWBdRlJ5SP7S19VeM7rV0Umjc1mO70IQx-Un7FdoYE27YpogRdiB-KXmzvk1zZl_u_CZSC7mQ7M7XdGrpIDvhhAhxVacbpIPary3Zh9J36X1hCZgBhpX9qneOiGxzQcGBdF7XMfsFdYI6_Be2hiPoKUFMtLflsrnWmLCNkKJFhylzubFLMX9KMzn7VnUG5rI9xCfDEae0emFjPA1FqysJV3P2ehe-HanA6GpaIxGOoDGOv_IyyySHFb0UAP4i19Xm5-i5SHUZNiT8e72DX1SLZn40Z5XRgEIdTrfoHDyyOfqvT676UlOLJHiHzQ0c06u6RvPMvAAAAAH-ZrzOAA"

# إعداد Gemini
genai.configure(api_key="AIzaSyADYritHhOSTJNN1wxQiRH0Rwoo1ycL_HI")
ai_model = genai.GenerativeModel('gemini-1.5-flash')

user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# --- وظيفة الذكاء الاصطناعي للتحليل ---
async def ai_analyze_message(text):
    prompt = f"صنف الرسالة التالية: '{text}'. إذا كانت طلب مشوار أو توصيل حقيقي رد بـ 'YES' فقط، وإذا كانت إعلان سائق أو غير ذلك رد بـ 'NO'."
    try:
        # تشغيل الطلب في خيط منفصل لعدم تجميد البوت
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: ai_model.generate_content(prompt))
        return response.text.strip().upper() == "YES"
    except:
        return False

# --- إرسال الإشعار للسائقين ---
async def notify_drivers(district, original_msg):
    conn = get_db_connection()
    if not conn: return
    try:
        search_term = normalize_text(district)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM users WHERE role = 'driver' AND (districts ILIKE %s)",
                (f"%{search_term}%",)
            )
            drivers = [row[0] for row in cur.fetchall()]
        
        if not drivers: return
        customer = original_msg.from_user
        customer_link = f"tg://user?id={customer.id}" if not customer.username else f"https://t.me/{customer.username}"
        alert_text = (
            f"🤖 **طلب مشوار ذكي (Gemini)**\n"
            f"📍 **الحي:** {district}\n"
            f"👤 **العميل:** {customer.first_name}\n"
            f"📝 **الطلب:**\n_{original_msg.text}_\n\n"
            f"📥 [مراسلة العميل خاص]({customer_link})"
        )
        for d_id in drivers:
            try: await bot_sender.send_message(chat_id=d_id, text=alert_text, parse_mode=ParseMode.MARKDOWN)
            except: continue
    finally: conn.close()

# --- خادم الويب ورادار التشغيل ---
async def start_radar():
    print("🚀 الرادار الذكي بدأ العمل...")
    await user_app.start()
    
    monitored_chats = []
    async for dialog in user_app.get_dialogs(limit=50):
        if "GROUP" in str(dialog.chat.type).upper():
            monitored_chats.append({"id": dialog.chat.id, "title": dialog.chat.title})

    last_id = {}
    while True:
        for chat in monitored_chats:
            try:
                async for msg in user_app.get_chat_history(chat["id"], limit=1):
                    if chat["id"] not in last_id:
                        last_id[chat["id"]] = msg.id; continue
                    
                    if msg.id > last_id[chat["id"]]:
                        last_id[chat["id"]] = msg.id
                        if not msg.text or len(msg.text) < 10: continue

                        # استشارة الذكاء الاصطناعي
                        if await ai_analyze_message(msg.text):
                            print(f"🎯 طلب حقيقي مكتشف في: {chat['title']}")
                            text_c = normalize_text(msg.text)
                            for city, districts in CITIES_DISTRICTS.items():
                                for d in districts:
                                    if normalize_text(d) in text_c:
                                        await notify_drivers(d, msg)
                                        break
            except: continue
        await asyncio.sleep(2)

# --- التشغيل ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Live")

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), HealthCheckHandler).serve_forever(), daemon=True).start()
    asyncio.run(start_radar())
