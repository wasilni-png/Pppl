import asyncio
from pyrogram import Client
from telegram import Bot
from telegram.constants import ParseMode
from config import normalize_text, CITIES_DISTRICTS, BOT_TOKEN, get_db_connection

# بياناتك
API_ID = "36360458"
API_HASH = "daae4628b4b4aac1f0ebfce23c4fa272"
SESSION_STRING = "BAIq0QoApqDmvNIHZnbO2VxSWBdRlJ5SP7S19VeM7rV0Umjc1mO70IQx-Un7FdoYE27YpogRdiB-KXmzvk1zZl_u_CZSC7mQ7M7XdGrpIDvhhAhxVacbpIPary3Zh9J36X1hCZgBhpX9qneOiGxzQcGBdF7XMfsFdYI6_Be2hiPoKUFMtLflsrnWmLCNkKJFhylzubFLMX9KMzn7VnUG5rI9xCfDEae0emFjPA1FqysJV3P2ehe-HanA6GpaIxGOoDGOv_IyyySHFb0UAP4i19Xm5-i5SHUZNiT8e72DX1SLZn40Z5XRgEIdTrfoHDyyOfqvT676UlOLJHiHzQ0c06u6RvPMvAAAAAH-ZrzOAA"

KEYWORDS = ["مشوار", "توصيل", "تكسي", "تاكسي", "مطلوب", "محتاج", "سواق", "ابي يوصل", "احتاج"]

user_app = Client("my_session", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)
bot_sender = Bot(token=BOT_TOKEN)

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
            f"🚨 **طلب مشوار جديد!**\n\n"
            f"📍 **الحي:** {district}\n"
            f"👤 **العميل:** {customer_name}\n"
            f"📝 **الطلب:**\n_{original_msg.text}_\n\n"
            f"📥 [اضغط هنا لمراسلة العميل خاص]({customer_link})"
        )

        for d_id in drivers:
            try:
                await bot_sender.send_message(chat_id=d_id, text=alert_text, parse_mode=ParseMode.MARKDOWN)
            except: continue
        print(f"✅ تم إرسال الطلب لـ {len(drivers)} سائق في حي {district}")
    except Exception as e:
        print(f"❌ خطأ في الإرسال: {e}")
    finally:
        conn.close()

# --- دالة المراقبة الرئيسية ---
async def start_radar():
    await user_app.start()
    print("✅ بدأ الرادار بنظام السحب اليدوي المتطور...")
    
    monitored_chats = []
    async for dialog in user_app.get_dialogs(limit=50):
        if str(dialog.chat.type) in ["ChatType.GROUP", "ChatType.SUPERGROUP", "group", "supergroup"]:
            monitored_chats.append({"id": dialog.chat.id, "title": dialog.chat.title})

    print(f"📡 مراقبة نشطة لـ {len(monitored_chats)} مجموعة.")
    last_checked_id = {}

    while True:
        for chat in monitored_chats:
            try:
                async for message in user_app.get_chat_history(chat["id"], limit=1):
                    if chat["id"] not in last_checked_id:
                        last_checked_id[chat["id"]] = message.id
                        continue
                    
                    if message.id > last_checked_id[chat["id"]]:
                        last_checked_id[chat["id"]] = message.id
                        if message.text:
                            text_clean = normalize_text(message.text)
                            # فحص الكلمات المفتاحية والأحياء
                            if any(normalize_text(k) in text_clean for k in KEYWORDS):
                                for city, districts in CITIES_DISTRICTS.items():
                                    for dist in districts:
                                        if normalize_text(dist) in text_clean:
                                            print(f"🎯 صيد ثمين في [{chat['title']}]: {dist}")
                                            await notify_drivers(city, dist, message)
                                            break
            except:
                continue
        await asyncio.sleep(2.5) # مهلة بسيطة لتجنب حظر الـ API

if __name__ == "__main__":
    asyncio.run(start_radar())
