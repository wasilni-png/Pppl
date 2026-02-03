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

# إعداد Gemini
genai.configure(api_key="AIzaSyADYritHhOSTJNN1wxQiRH0Rwoo1ycL_HI")
ai_model = genai.GenerativeModel('gemini-1.5-flash-latest')


user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

# --- دالة استشارة الذكاء الاصطناعي ---
async def is_real_delivery_order(text):
    prompt = f"""
    صنف الرسالة التالية بدقة: "{text}"
    هل هي طلب مشوار أو توصيل حقيقي من زبون؟ 
    - إذا كانت طلب توصيل أو مشوار (مثل: ابي سواق، يوديني، يوصلني، من..إلى): رد بكلمة "YES" فقط.
    - إذا كانت إعلان سائق، طلب سكن، زواج مسيار، بيع وشراء، أو أي شيء غير طلب مشوار: رد بكلمة "NO" فقط.
    الرد يجب أن يكون كلمة واحدة (YES أو NO).
    """
    try:
        # تشغيل الطلب في Thread منفصل لعدم تعطيل الرادار
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: ai_model.generate_content(prompt))
        return response.text.strip().upper() == "YES"
    except Exception as e:
        print(f"⚠️ خطأ في الذكاء الاصطناعي: {e}")
        return False

# --- خادم الويب ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"AI Radar is Live")

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
        customer_link = f"tg://user?id={customer.id}" if not customer.username else f"https://t.me/{customer.username}"
        alert_text = (
            f"🤖 **طلب مشوار (محلل بالذكاء الاصطناعي)**\n\n"
            f"📍 **الحي:** {district}\n"
            f"👤 **العميل:** {customer.first_name}\n"
            f"📝 **الطلب:**\n_{original_msg.text}_\n\n"
            f"📥 [مراسلة العميل خاص]({customer_link})"
        )
        for d_id in drivers:
            try: await bot_sender.send_message(chat_id=d_id, text=alert_text, parse_mode=ParseMode.MARKDOWN)
            except: continue
    finally: conn.close()

# --- المحرك الرئيسي للرادار ---
async def start_radar():
    await user_app.start()
    me = await user_app.get_me()
    print(f"✅ تم تسجيل الدخول بنجاح باسم: {me.first_name}")
    
    # 1. فحص المجموعات
    monitored_chats = []
    print("⏳ جاري فحص المجموعات المشترك بها...")
    async for dialog in user_app.get_dialogs(limit=100):
        # التحقق من نوع الشات بدقة
        chat_type = str(dialog.chat.type)
        if "GROUP" in chat_type.upper():
            monitored_chats.append({"id": dialog.chat.id, "title": dialog.chat.title})
    
    if not monitored_chats:
        print("❌ خطأ: الحساب لا يوجد به مجموعات! تأكد من انضمام الحساب لقروبات التوصيل.")
        return
    
    print(f"📡 مراقبة نشطة لـ ({len(monitored_chats)}) مجموعة.")
    for c in monitored_chats[:5]: # طباعة أول 5 مجموعات للتأكد
        print(f"🔗 مراقبة: {c['title']}")

    last_id = {}
    while True:
        for chat in monitored_chats:
            try:
                # سحب آخر رسالة
                async for msg in user_app.get_chat_history(chat["id"], limit=1):
                    # تخزين أول ID للرسالة لبدء المراقبة من اللحظة الحالية
                    if chat["id"] not in last_id:
                        last_id[chat["id"]] = msg.id
                        continue
                    
                    # فحص إذا كانت هناك رسالة جديدة
                    if msg.id > last_id[chat["id"]]:
                        last_id[chat["id"]] = msg.id
                        
                        # تجاهل رسائل البوت نفسه
                        if msg.from_user and msg.from_user.id == me.id:
                            continue

                        if msg.text:
                            print(f"📩 رسالة جديدة من [{chat['title']}]: {msg.text[:30]}...")
                            
                            # أ- التحقق من الطول
                            if len(msg.text) > 200:
                                print("⏭️ تم التجاهل: نص طويل جداً.")
                                continue

                            # ب- استشارة الذكاء الاصطناعي
                            print("🧠 جاري استشارة الذكاء الاصطناعي...")
                            if await is_real_delivery_order(msg.text):
                                print("✅ الذكاء الاصطناعي أكد: هذا طلب مشوار.")
                                
                                # ج- البحث عن الحي
                                text_c = normalize_text(msg.text)
                                found = False
                                for city, districts in CITIES_DISTRICTS.items():
                                    for d in districts:
                                        if normalize_text(d) in text_c:
                                            print(f"🎯 تم العثور على حي مطابق: {d}")
                                            await notify_drivers(city, d, msg)
                                            found = True
                                            break
                                    if found: break
                                
                                if not found:
                                    print("ℹ️ لم يتم العثور على اسم حي معروف في الرسالة.")
                            else:
                                print("❌ الذكاء الاصطناعي قرر: ليست رسالة طلب.")

                await asyncio.sleep(0.5) # تقليل التأخير لسرعة الاستجابة
            except Exception as e:
                print(f"⚠️ خطأ أثناء فحص {chat['title']}: {e}")
                continue
        await asyncio.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), HealthCheckHandler).serve_forever(), daemon=True).start()
    asyncio.run(start_radar())
