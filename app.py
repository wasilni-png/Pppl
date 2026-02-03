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

# الكلمات المفتاحية للطلب
KEYWORDS = ["مشوار", "توصيل", "ابي", "أبي", "محتاج", "مطلوب", "يوديني", "في", "من", "سواق", "كابتن"]

# قائمة الاستثناءات المدمجة (الشاملة)
EXCLUDED = [
    "زواج", "مسيار", "خطابة", "خطابه", "بنت", "شاب", "زواجات", "تعدد", "مطلقة", "ارملة", "امرأة",
    "للبيع", "حراج", "نظيف", "موديل", "مستعمل", "ممشى", "قير", "ماكينة", "مكينة", "بودي", "سعر", "سوم",
    "تويوتا", "كامري", "هونداي", "شاشة", "جوال", "ايفون", "اثاث", "كنب", "ثلاجة", "مكيف",
    "ايجار", "إيجار", "للإيجار", "للايجار", "شقة", "غرفة", "عمارة", "دور", "فيلا", "استراحة", "محل",
    "خدمتكم", "قروبات", "انضم", "وظائف", "وظيفة", "تعقيب", "معقب", "انجاز", "إنجاز", "تسقيط", "تجديد",
    "تامين", "تأمين", "قرض", "تمويل", "تسديد", "كفيل", "تنسيق", "نقل_عفش", "تنظيف", "مكافحة",
    "متواجد", "متاح", "شغال", "تحميل", "يوجد لدينا", "خدمة توصيل", "أسعارنا", "اسعارنا", "نصلكم", "جاهز",
    "للتوصيل", "نوصل", "متوفر", "اتصال", "واتساب", "تواصل", "بأفضل", "باقل", "ارخص"
]

user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Radar Clean Version Active")

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
        alert_text = f"🚨 **طلب مشوار جديد!**\n\n📍 **الحي:** {district}\n👤 **العميل:** {customer.first_name if customer.first_name else 'عميل'}\n📝 **الطلب:**\n_{original_msg.text}_\n\n📥 [مراسلة العميل خاص]({customer_link})"
        
        for d_id in drivers:
            try: await bot_sender.send_message(chat_id=d_id, text=alert_text, parse_mode=ParseMode.MARKDOWN)
            except: continue
        print(f"✅ تم الإرسال لحي {district}")
    finally: conn.close()

async def start_radar():
    await user_app.start()
    me = await user_app.get_me()
    print(f"✅ الرادار يعمل (فلتر الطول + الاستثناءات).. الحساب: {me.first_name}")
    
    monitored_chats = []
    async for dialog in user_app.get_dialogs(limit=50):
        if str(dialog.chat.type) in ["ChatType.GROUP", "ChatType.SUPERGROUP", "group", "supergroup"]:
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
                        if msg.from_user and msg.from_user.id == me.id: continue

                        if msg.text:
                            # --- 1. فلتر الطول ---
                            if len(msg.text) > 150:
                                print(f"⏭️ تم تجاهل رسالة طويلة من {chat['title']}")
                                continue

                            text_c = normalize_text(msg.text)
                            
                            # --- 2. فلتر الاستثناءات المدمجة ---
                            if any(ex in text_c for ex in EXCLUDED): 
                                continue

                            # --- 3. البحث عن الحي والكلمات ---
                            found_district = None
                            found_city = None
                            for city, districts in CITIES_DISTRICTS.items():
                                for d in districts:
                                    if normalize_text(d) in text_c:
                                        found_district = d
                                        found_city = city
                                        break
                                if found_district: break
                            
                            if found_district:
                                if any(normalize_text(k) in text_c for k in KEYWORDS):
                                    print(f"🎯 صيد: {msg.text[:30]}...")
                                    await notify_drivers(found_city, found_district, msg)
                await asyncio.sleep(1.2)
            except: continue
        await asyncio.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), HealthCheckHandler).serve_forever(), daemon=True).start()
    asyncio.run(start_radar())
