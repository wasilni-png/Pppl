import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client
from telegram import Bot
from telegram.constants import ParseMode
import google.generativeai as genai
from config import normalize_text, CITIES_DISTRICTS, BOT_TOKEN, get_db_connection

# --- إعدادات الحساب والذكاء الاصطناعي ---
API_ID = "36360458"
API_HASH = "daae4628b4b4aac1f0ebfce23c4fa272"
SESSION_STRING = "BAIq0QoApqDmvNIHZnbO2VxSWBdRlJ5SP7S19VeM7rV0Umjc1mO70IQx-Un7FdoYE27YpogRdiB-KXmzvk1zZl_u_CZSC7mQ7M7XdGrpIDvhhAhxVacbpIPary3Zh9J36X1hCZgBhpX9qneOiGxzQcGBdF7XMfsFdYI6_Be2hiPoKUFMtLflsrnWmLCNkKJFhylzubFLMX9KMzn7VnUG5rI9xCfDEae0emFjPA1FqysJV3P2ehe-HanA6GpaIxGOoDGOv_IyyySHFb0UAP4i19Xm5-i5SHUZNiT8e72DX1SLZn40Z5XRgEIdTrfoHDyyOfqvT676UlOLJHiHzQ0c06u6RvPMvAAAAAH-ZrzOAA"

# إعداد Gemini - تم تعديل المسمى لتجنب خطأ 404
genai.configure(api_key="AIzaSyADYritHhOSTJNN1wxQiRH0Rwoo1ycL_HI")
ai_model = genai.GenerativeModel('gemini-1.5-flash')

user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# الكلمات المفتاحية للطوارئ (في حال تعطل AI)
INTENT_WORDS = ["مشوار", "توصيل", "سواق", "كابتن", "سيارة", "يوصلني", "يوديني", "ابغى", "ابي", "أبي"]

# --- دالة استشارة الذكاء الاصطناعي مع نظام طوارئ ---
async def is_real_delivery_order(text):
    prompt = f"هل الرسالة التالية طلب مشوار أو توصيل حقيقي؟ رد بـ YES أو NO فقط: {text}"
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: ai_model.generate_content(prompt))
        return "YES" in response.text.strip().upper()
    except Exception as e:
        print(f"⚠️ فشل AI: {e} | سيتم استخدام الفلترة التقليدية.")
        # نظام الطوارئ: إذا تعطل AI، نبحث عن الكلمات المفتاحية يدوياً
        return any(word in text for word in INTENT_WORDS)

# --- خادم الويب (Render Health Check) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"AI Radar is Active")

# --- دالة إرسال الإشعارات للسائقين ---
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
        customer_name = customer.first_name if customer.first_name else "عميل"
        customer_link = f"tg://user?id={customer.id}" if not customer.username else f"https://t.me/{customer.username}"
        
        alert_text = (
            f"🤖 **طلب مشوار ذكي**\n\n"
            f"📍 **الحي:** {district}\n"
            f"👤 **العميل:** {customer_name}\n"
            f"📝 **الطلب:**\n_{original_msg.text}_\n\n"
            f"📥 [مراسلة العميل خاص]({customer_link})"
        )
        for d_id in drivers:
            try: await bot_sender.send_message(chat_id=d_id, text=alert_text, parse_mode=ParseMode.MARKDOWN)
            except: continue
        print(f"✅ تم الإرسال لحي {district}")
    finally: conn.close()

# --- المحرك الرئيسي للرادار ---
async def start_radar():
    await user_app.start()
    me = await user_app.get_me()
    print(f"✅ تم تسجيل الدخول! الرادار يعمل باسم: {me.first_name}")
    
    monitored_chats = []
    async for dialog in user_app.get_dialogs(limit=100):
        if "GROUP" in str(dialog.chat.type).upper():
            monitored_chats.append({"id": dialog.chat.id, "title": dialog.chat.title})
    
    print(f"📡 مراقبة نشطة لـ ({len(monitored_chats)}) مجموعة.")

    last_id = {}
    while True:
        for chat in monitored_chats:
            try:
                async for msg in user_app.get_chat_history(chat["id"], limit=1):
                    if chat["id"] not in last_id:
                        last_id[chat["id"]] = msg.id; continue
                    
                    if msg.id > last_id[chat["id"]]:
                        last_id[chat["id"]] = msg.id
                        if (msg.from_user and msg.from_user.id == me.id) or not msg.text: continue

                        print(f"📩 رسالة جديدة من [{chat['title']}]")
                        
                        # الفلترة الذكية
                        if await is_real_delivery_order(msg.text):
                            text_c = normalize_text(msg.text)
                            for city, districts in CITIES_DISTRICTS.items():
                                for d in districts:
                                    if normalize_text(d) in text_c:
                                        print(f"🎯 طلب مؤكد في: {d}")
                                        await notify_drivers(city, d, msg)
                                        break
                await asyncio.sleep(0.5)
            except: continue
        await asyncio.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), HealthCheckHandler).serve_forever(), daemon=True).start()
    asyncio.run(start_radar())
