import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client
from telegram import Bot
from telegram.constants import ParseMode
from config import normalize_text, CITIES_DISTRICTS, BOT_TOKEN, get_db_connection

# --- إعدادات الحساب ---
API_ID = "36360458"
API_HASH = "daae4628b4b4aac1f0ebfce23c4fa272"
SESSION_STRING = "BAIq0QoApqDmvNIHZnbO2VxSWBdRlJ5SP7S19VeM7rV0Umjc1mO70IQx-Un7FdoYE27YpogRdiB-KXmzvk1zZl_u_CZSC7mQ7M7XdGrpIDvhhAhxVacbpIPary3Zh9J36X1hCZgBhpX9qneOiGxzQcGBdF7XMfsFdYI6_Be2hiPoKUFMtLflsrnWmLCNkKJFhylzubFLMX9KMzn7VnUG5rI9xCfDEae0emFjPA1FqysJV3P2ehe-HanA6GpaIxGOoDGOv_IyyySHFb0UAP4i19Xm5-i5SHUZNiT8e72DX1SLZn40Z5XRgEIdTrfoHDyyOfqvT676UlOLJHiHzQ0c06u6RvPMvAAAAAH-ZrzOAA"

# --- القوائم الذكية للفلترة ---
DESTINATION_INDICATORS = ["الى", "إلى", "ل", "لحي", "على", "رايح", "للمطار", "للسوق"]

EXCLUDED = [
    "زواج", "مسيار", "خطابة", "خطابه", "بنت", "شاب", "زواجات", "تعدد", "مطلقة", "امرأة",
    "للبيع", "حراج", "نظيف", "موديل", "مستعمل", "سعر", "سوم", "اثاث", "شاشة", "جوال",
    "ايجار", "إيجار", "شقة", "غرفة", "غرفه", "عمارة", "دور", "سكن", "اشارك", "انام",
    "وظائف", "وظيفة", "تعقيب", "معقب", "انجاز", "تسقيط", "قرض", "تمويل", "تسديد",
    "متواجد", "متاح", "شغال", "تحميل", "يوجد لدينا", "خدمة توصيل", "أسعارنا", "جاهز",
    "للتوصيل", "نوصل", "متوفر", "يمني", "سوداني", "مصري", "مطعم", "فزعة"
]

# الكلمات التي تؤكد وجود طلب (Intent) حتى لو لم يتوفر مسار "من-إلى" صريح
INTENT_WORDS = ["مشوار", "توصيل", "سواق", "كابتن", "سيارة", "يوصلني", "يوديني", "ابغى", "ابي", "أبي"]

user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# --- خادم الويب (لإرضاء Render ومنع التوقف) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Radar Engine is Running Safely")

def run_health_check():
    try:
        server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
        server.serve_forever()
    except: pass

# --- دالة إرسال الإشعارات للسائقين ---
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
        
        if not drivers: return

        customer = original_msg.from_user
        customer_name = customer.first_name if customer.first_name else "عميل"
        customer_link = f"tg://user?id={customer.id}" if not customer.username else f"https://t.me/{customer.username}"
        
        alert_text = (
            f"🚨 **طلب مشوار جديد ومفحوص!**\n\n"
            f"📍 **الحي المكتشف:** {district}\n"
            f"👤 **العميل:** {customer_name}\n"
            f"📝 **الطلب:**\n_{original_msg.text}_\n\n"
            f"📥 [اضغط هنا لمراسلة العميل خاص]({customer_link})"
        )

        for d_id in drivers:
            try:
                await bot_sender.send_message(chat_id=d_id, text=alert_text, parse_mode=ParseMode.MARKDOWN)
            except: continue
        print(f"✅ تم إرسال الطلب لـ {len(drivers)} سائق في {district}")
    finally:
        conn.close()

# --- المحرك الرئيسي للرادار ---
async def start_radar():
    await user_app.start()
    me = await user_app.get_me()
    print(f"✅ الرادار يعمل الآن بنظام الفلترة الثلاثية.. الحساب: {me.first_name}")
    
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
                        
                        # 1. تجاهل رسائلك وتجاهل الرسائل الطويلة جداً
                        if (msg.from_user and msg.from_user.id == me.id) or not msg.text or len(msg.text) > 160:
                            continue

                        text_c = normalize_text(msg.text)
                        
                        # 2. فلتر الاستثناءات الصارم (منع السكن والمسيار والبيع)
                        if any(ex in text_c for ex in EXCLUDED):
                            continue

                        # 3. منطق المسارات والنية (Route & Intent logic)
                        is_route = "من" in text_c and any(ind in text_c for ind in DESTINATION_INDICATORS)
                        has_intent = any(k in text_c for k in INTENT_WORDS)

                        if is_route or has_intent:
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
                                print(f"🎯 صيد حقيقي في [{chat['title']}]: {msg.text[:40]}...")
                                await notify_drivers(found_city, found_district, msg)
                
                await asyncio.sleep(1.2) # تأخير بسيط لتجنب حظر تليجرام
            except Exception as e:
                if "420" in str(e): await asyncio.sleep(30)
                continue
        await asyncio.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_health_check, daemon=True).start()
    asyncio.run(start_radar())
