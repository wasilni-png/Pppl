"""
🚖 بوت النقل الذكي - نسخة بأزرار تعمل 100%
"""

import os
import logging
from flask import Flask, request, jsonify
import telebot
from telebot import types

# ============================================================================
# إعدادات أساسية
# ============================================================================

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# الحصول على التوكن
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    BOT_TOKEN = "8425005126:AAH9I7qu0gjKEpKX52rFWHsuCn9Bw5jaNr0"

# تهيئة التطبيق والبوت
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# تخزين
users = {}
active_drivers = {}
ride_requests = []

# ============================================================================
# دوال لإنشاء الأزرار (مبسطة لضمان العمل)
# ============================================================================

def create_main_keyboard():
    """لوحة مفاتيح رئيسية - Reply Keyboard"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = [
        '🚖 طلب رحلة',
        '📍 إرسال موقعي',
        '💰 رصيدي',
        '📋 رحلاتي',
        '⚙️ الإعدادات',
        '📞 الدعم',
        '👤 حسابي',
        '🎫 العروض'
    ]
    
    # إضافة الأزرار بطرق مختلفة لضمان الظهور
    markup.row('🚖 طلب رحلة', '📍 إرسال موقعي')
    markup.row('💰 رصيدي', '📋 رحلاتي')
    markup.row('⚙️ الإعدادات', '📞 الدعم')
    markup.row('👤 حسابي', '🎫 العروض')
    
    return markup

def create_driver_keyboard():
    """لوحة مفاتيح للسائقين"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    markup.row('🟢 بدء العمل', '🔴 إيقاف')
    markup.row('📍 تحديث موقعي', '📊 الطلبات')
    markup.row('💰 أرباحي', '📈 إحصائيات')
    markup.row('🏠 القائمة الرئيسية')
    
    return markup

def create_inline_main_menu():
    """قائمة داخلية - Inline Keyboard"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # الصف الأول
    markup.add(
        types.InlineKeyboardButton("🚖 طلب رحلة", callback_data="req_ride"),
        types.InlineKeyboardButton("💰 رصيدي", callback_data="my_balance")
    )
    
    # الصف الثاني
    markup.add(
        types.InlineKeyboardButton("📋 رحلاتي", callback_data="my_rides"),
        types.InlineKeyboardButton("⭐ تقييماتي", callback_data="my_ratings")
    )
    
    # الصف الثالث
    markup.add(
        types.InlineKeyboardButton("🎫 العروض", callback_data="offers"),
        types.InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")
    )
    
    # الصف الرابع
    markup.add(
        types.InlineKeyboardButton("📞 الدعم", callback_data="support"),
        types.InlineKeyboardButton("ℹ️ عن البوت", callback_data="about")
    )
    
    return markup

def create_ride_types_menu():
    """أزرار أنواع الرحلات"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.row(
        types.InlineKeyboardButton("🚗 عادية", callback_data="ride_normal"),
        types.InlineKeyboardButton("🚙 فاخرة", callback_data="ride_premium")
    )
    
    markup.row(
        types.InlineKeyboardButton("🚐 عائلية", callback_data="ride_family"),
        types.InlineKeyboardButton("🚗 اقتصادية", callback_data="ride_economy")
    )
    
    markup.row(
        types.InlineKeyboardButton("↩️ رجوع", callback_data="back_main")
    )
    
    return markup

def create_quick_actions():
    """أزرار سريعة"""
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    markup.row(
        types.InlineKeyboardButton("🚖", callback_data="quick_ride"),
        types.InlineKeyboardButton("📍", callback_data="quick_location"),
        types.InlineKeyboardButton("💰", callback_data="quick_balance")
    )
    
    markup.row(
        types.InlineKeyboardButton("📞", callback_data="quick_support"),
        types.InlineKeyboardButton("⭐", callback_data="quick_rate"),
        types.InlineKeyboardButton("⚙️", callback_data="quick_settings")
    )
    
    return markup

def create_confirmation_buttons():
    """أزرار تأكيد"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("✅ نعم", callback_data="confirm_yes"),
        types.InlineKeyboardButton("❌ لا", callback_data="confirm_no")
    )
    
    return markup

# ============================================================================
# معالجات الرسائل الأساسية (مع أزرار Reply Keyboard)
# ============================================================================

@bot.message_handler(commands=['start', 'menu'])
def handle_start(message):
    """معالجة أمر /start"""
    user_id = str(message.from_user.id)
    name = message.from_user.first_name
    
    logger.info(f"👋 /start من: {name} ({user_id})")
    
    # حفظ بيانات المستخدم
    users[user_id] = {
        'id': user_id,
        'name': name,
        'username': message.from_user.username,
        'role': None,
        'balance': 0
    }
    
    # إرسال رسالة الترحيب مع Reply Keyboard
    welcome_msg = (
        f"🎉 <b>مرحباً {name} في بوت النقل الذكي!</b>\n\n"
        f"🚖 <b>أسرع وأأمن خدمة نقل</b>\n"
        f"✨ <b>اختر الخدمة المطلوبة من الأزرار أدناه:</b>"
    )
    
    # إرسال مع Reply Keyboard (تظهر أسفل الشاشة)
    bot.send_message(
        message.chat.id,
        welcome_msg,
        reply_markup=create_main_keyboard()
    )
    
    # بعد 1 ثانية، إرسال القائمة التفاعلية
    bot.send_message(
        message.chat.id,
        "📱 <b>القائمة التفاعلية السريعة:</b>\n(اضغط على الأزرار داخل الرسالة)",
        reply_markup=create_inline_main_menu()
    )

@bot.message_handler(func=lambda message: message.text == '🚖 طلب رحلة')
def handle_ride_request(message):
    """طلب رحلة جديدة"""
    logger.info(f"🚖 طلب رحلة من: {message.from_user.id}")
    
    # إرسال رسالة مع أزرار Inline
    bot.send_message(
        message.chat.id,
        "🚗 <b>اختر نوع الرحلة:</b>\n\n"
        "• 🚗 <b>عادية</b>: سعر أساسي\n"
        "• 🚙 <b>فاخرة</b>: راحة أكثر\n"
        "• 🚐 <b>عائلية</b>: سيارة كبيرة\n"
        "• 🚗 <b>اقتصادية</b>: توفير سعر",
        reply_markup=create_ride_types_menu()
    )

@bot.message_handler(func=lambda message: message.text == '💰 رصيدي')
def handle_balance(message):
    """عرض الرصيد"""
    user_id = str(message.from_user.id)
    
    # إنشاء أزرار Inline للرصيد
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💳 شحن", callback_data="charge_balance"),
        types.InlineKeyboardButton("📊 التفاصيل", callback_data="balance_details")
    )
    markup.add(
        types.InlineKeyboardButton("🎫 كوبون", callback_data="use_coupon"),
        types.InlineKeyboardButton("📤 سحب", callback_data="withdraw_money")
    )
    
    bot.send_message(
        message.chat.id,
        "💰 <b>حسابك المالي</b>\n\n"
        f"• الرصيد المتاح: <b>0.00 ر.س</b>\n"
        f"• المكافآت: <b>0.00 ر.س</b>\n"
        f"• القسائم: <b>0</b>\n\n"
        "اختر الإجراء:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '📞 الدعم')
def handle_support(message):
    """عرض خيارات الدعم"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📞 اتصال هاتفي", url="tel:+966500000000"),
        types.InlineKeyboardButton("💬 محادثة نصية", callback_data="chat_support"),
        types.InlineKeyboardButton("📧 بريد إلكتروني", url="mailto:support@example.com"),
        types.InlineKeyboardButton("📍 مواقع الفروع", callback_data="branches"),
        types.InlineKeyboardButton("❓ الأسئلة الشائعة", callback_data="faq")
    )
    
    bot.send_message(
        message.chat.id,
        "📞 <b>مركز الدعم والمساعدة</b>\n\n"
        "💬 <b>الدردشة المباشرة:</b> 24/7\n"
        "📱 <b>الهاتف:</b> 920000000\n"
        "✉️ <b>البريد:</b> support@example.com\n\n"
        "اختر طريقة التواصل:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '⚙️ الإعدادات')
def handle_settings(message):
    """عرض الإعدادات"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("👤 الملف الشخصي", callback_data="edit_profile"),
        types.InlineKeyboardButton("🔔 الإشعارات", callback_data="notifications"),
        types.InlineKeyboardButton("🌍 اللغة", callback_data="language"),
        types.InlineKeyboardButton("🔒 الخصوصية", callback_data="privacy"),
        types.InlineKeyboardButton("🎨 المظهر", callback_data="theme")
    )
    
    bot.send_message(
        message.chat.id,
        "⚙️ <b>الإعدادات</b>\n\n"
        "يمكنك تخصيص إعدادات حسابك:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '👤 حسابي')
def handle_profile(message):
    """عرض الملف الشخصي"""
    user_id = str(message.from_user.id)
    user_data = users.get(user_id, {})
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✏️ تعديل الاسم", callback_data="edit_name"),
        types.InlineKeyboardButton("📱 رقم الجوال", callback_data="edit_phone")
    )
    markup.add(
        types.InlineKeyboardButton("📧 البريد", callback_data="edit_email"),
        types.InlineKeyboardButton("🔐 كلمة المرور", callback_data="change_password")
    )
    
    bot.send_message(
        message.chat.id,
        f"👤 <b>الملف الشخصي</b>\n\n"
        f"• <b>الاسم:</b> {user_data.get('name', 'غير محدد')}\n"
        f"• <b>رقم العضوية:</b> #{user_id[-6:]}\n"
        f"• <b>تاريخ التسجيل:</b> اليوم\n"
        f"• <b>عدد الرحلات:</b> 0\n"
        f"• <b>التقييم:</b> ⭐⭐⭐⭐⭐\n\n"
        f"اختر ما تريد تعديله:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '🎫 العروض')
def handle_offers(message):
    """عرض العروض"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎁 أول رحلة مجاناً", callback_data="offer_first"),
        types.InlineKeyboardButton("👥 دعوة أصدقاء", callback_data="invite_friends"),
        types.InlineKeyboardButton("📱 حمّل التطبيق", callback_data="download_app"),
        types.InlineKeyboardButton("🎯 عرض العودة", callback_data="comeback_offer"),
        types.InlineKeyboardButton("📊 جميع العروض", callback_data="all_offers")
    )
    
    bot.send_message(
        message.chat.id,
        "🎫 <b>العروض والترقيات</b>\n\n"
        "🔥 <b>عروض حصرية لك!</b>\n\n"
        "1. 🎁 <b>الرحلة الأولى مجاناً</b>\n"
        "   - لحد 50 ريال\n"
        "   - صالح لـ 7 أيام\n\n"
        "2. 👥 <b>دعوة أصدقاء</b>\n"
        "   - احصل على 50 ريال\n"
        "   - لكل صديق\n\n"
        "اختر العرض:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '🏠 القائمة الرئيسية')
def handle_main_menu(message):
    """العودة للقائمة الرئيسية"""
    handle_start(message)

# ============================================================================
# معالجة الأزرار التفاعلية (Inline Keyboard)
# ============================================================================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """معالجة جميع ضغطات الأزرار التفاعلية"""
    user_id = str(call.from_user.id)
    chat_id = call.message.chat.id
    
    logger.info(f"🔘 ضغط زر: {call.data} من {user_id}")
    
    # إجابة سريعة عن الضغط
    bot.answer_callback_query(call.id, text="جاري المعالجة...")
    
    # معالجة حسب نوع الزر
    if call.data == "req_ride":
        # طلب رحلة
        bot.send_message(
            chat_id,
            "🚖 <b>طلب رحلة جديدة</b>\n\n"
            "الرجاء إرسال موقعك أو استخدام الزر أدناه:",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                types.KeyboardButton("📍 إرسال موقعي", request_location=True)
            )
        )
    
    elif call.data == "my_balance":
        # عرض الرصيد
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("💳 شحن الآن", callback_data="charge_now"),
            types.InlineKeyboardButton("📤 سحب", callback_data="withdraw_now")
        )
        
        bot.send_message(
            chat_id,
            "💰 <b>رصيدك الحالي: 0.00 ر.س</b>\n\n"
            "اختر الإجراء:",
            reply_markup=markup
        )
    
    elif call.data.startswith("ride_"):
        # اختيار نوع الرحلة
        ride_type = call.data.replace("ride_", "")
        types_map = {
            "normal": "عادية",
            "premium": "فاخرة",
            "family": "عائلية",
            "economy": "اقتصادية"
        }
        
        ride_name = types_map.get(ride_type, "عادية")
        
        # طلب الموقع بعد اختيار نوع الرحلة
        bot.send_message(
            chat_id,
            f"✅ <b>تم اختيار رحلة {ride_name}</b>\n\n"
            f"الرجاء إرسال موقعك لبدء البحث عن سائق...",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                types.KeyboardButton("📍 إرسال موقعي", request_location=True)
            )
        )
    
    elif call.data == "back_main":
        # العودة للقائمة الرئيسية
        bot.send_message(
            chat_id,
            "🏠 <b>القائمة الرئيسية</b>",
            reply_markup=create_main_keyboard()
        )
        
        # إرسال القائمة التفاعلية أيضاً
        bot.send_message(
            chat_id,
            "📱 <b>القائمة التفاعلية:</b>",
            reply_markup=create_inline_main_menu()
        )
    
    elif call.data == "support":
        # الدعم
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💬 محادثة نصية", callback_data="start_chat"),
            types.InlineKeyboardButton("📞 اتصال", url="tel:+966500000000"),
            types.InlineKeyboardButton("↩️ رجوع", callback_data="back_main")
        )
        
        bot.send_message(
            chat_id,
            "📞 <b>مركز الدعم</b>\n\n"
            "كيف يمكننا مساعدتك؟",
            reply_markup=markup
        )
    
    elif call.data == "settings":
        # الإعدادات
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("👤 الملف الشخصي", callback_data="edit_profile"),
            types.InlineKeyboardButton("🔔 الإشعارات", callback_data="notify_settings"),
            types.InlineKeyboardButton("🌍 اللغة: العربية", callback_data="change_lang"),
            types.InlineKeyboardButton("↩️ رجوع", callback_data="back_main")
        )
        
        bot.send_message(
            chat_id,
            "⚙️ <b>الإعدادات</b>\n\n"
            "اختر الإعداد الذي تريد تعديله:",
            reply_markup=markup
        )
    
    elif call.data == "confirm_yes":
        # تأكيد نعم
        bot.send_message(chat_id, "✅ <b>تم التأكيد بنجاح!</b>")
    
    elif call.data == "confirm_no":
        # تأكيد لا
        bot.send_message(chat_id, "❌ <b>تم الإلغاء</b>")
    
    elif call.data == "quick_ride":
        # طلب سريع
        bot.send_message(
            chat_id,
            "🚖 <b>طلب سريع</b>\n\n"
            "جاري البحث عن أقرب سائق...",
            reply_markup=create_confirmation_buttons()
        )
    
    else:
        # لأي زر آخر
        bot.send_message(
            chat_id,
            f"🔘 <b>تم الضغط على: {call.data}</b>\n\n"
            f"هذه الميزة قيد التطوير حالياً.",
            reply_markup=create_inline_main_menu()
        )

# ============================================================================
# معالجة أنواع أخرى من الرسائل
# ============================================================================

@bot.message_handler(content_types=['location'])
def handle_location(message):
    """معالجة الموقع المرسل"""
    location = message.location
    
    logger.info(f"📍 موقع من: {message.from_user.id}")
    
    # عرض أزرار بعد استلام الموقع
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ تأكيد", callback_data="confirm_location"),
        types.InlineKeyboardButton("🔄 إعادة الإرسال", callback_data="resend_location")
    )
    markup.add(
        types.InlineKeyboardButton("🚖 طلب الآن", callback_data="request_now"),
        types.InlineKeyboardButton("📍 اختر من الخريطة", callback_data="pick_map")
    )
    
    bot.send_message(
        message.chat.id,
        f"📍 <b>تم استلام موقعك!</b>\n\n"
        f"الإحداثيات:\n"
        f"• خط العرض: {location.latitude:.6f}\n"
        f"• خط الطول: {location.longitude:.6f}\n\n"
        f"هل تريد المتابعة؟",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '📍 إرسال موقعي')
def handle_send_location_button(message):
    """زر إرسال الموقع"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📍 إرسال موقعي الحالي", request_location=True)
    )
    markup.add(types.KeyboardButton("🏠 القائمة الرئيسية"))
    
    bot.send_message(
        message.chat.id,
        "📍 <b>إرسال الموقع</b>\n\n"
        "اضغط على الزر أدناه لمشاركة موقعك الحالي:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """معالجة جميع الرسائل الأخرى"""
    logger.info(f"📩 رسالة: {message.text} من {message.from_user.id}")
    
    # إذا كانت رسالة غير معروفة، نعرض القائمة
    if message.text not in [
        '🚖 طلب رحلة', '📍 إرسال موقعي', '💰 رصيدي',
        '📋 رحلاتي', '⚙️ الإعدادات', '📞 الدعم',
        '👤 حسابي', '🎫 العروض', '🏠 القائمة الرئيسية'
    ]:
        bot.send_message(
            message.chat.id,
            "🤖 <b>مرحباً!</b>\n\n"
            "استخدم الأزرار أدناه للتنقل، أو اكتب /start لرؤية القائمة الرئيسية.",
            reply_markup=create_main_keyboard()
        )

# ============================================================================
# صفحات الويب (مبسطة)
# ============================================================================

@app.route('/')
def home():
    """الصفحة الرئيسية"""
    try:
        bot_info = bot.get_me()
        bot_status = f"@{bot_info.username}"
    except:
        bot_status = "❌ غير متصل"
    
    return f'''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>🚖 بوت النقل الذكي</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                padding: 20px;
                text-align: center;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .btn {{
                display: inline-block;
                padding: 10px 20px;
                margin: 10px;
                background: #0088cc;
                color: white;
                text-decoration: none;
                border-radius: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚖 بوت النقل الذكي</h1>
            <p>البوت يعمل بنجاح!</p>
            <p>🤖 <strong>البوت:</strong> {bot_status}</p>
            <p>👥 <strong>المستخدمين:</strong> {len(users)}</p>
            
            <div style="margin: 30px 0;">
                <h3>🔘 أنواع الأزرار في البوت:</h3>
                <p>1. Reply Keyboard (أسفل الشاشة)</p>
                <p>2. Inline Keyboard (داخل الرسالة)</p>
            </div>
            
            <div>
                <a href="/set_webhook" class="btn">⚙️ تعيين ويب هوك</a>
                <a href="https://t.me/Dhdhdyduudbot" target="_blank" class="btn">💬 فتح البوت</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/set_webhook')
def set_webhook():
    """تعيين ويب هوك"""
    try:
        webhook_url = f"https://{request.host}/webhook"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        
        return '''
        <!DOCTYPE html>
        <html dir="rtl">
        <head><meta charset="UTF-8"></head>
        <body style="padding: 50px; text-align: center;">
            <h2>✅ تم تعيين الويب هوك بنجاح!</h2>
            <p>يمكنك الآن استخدام البوت مع الأزرار التفاعلية</p>
            <a href="/">العودة</a>
        </body>
        </html>
        '''
    except Exception as e:
        return f'<h2>❌ خطأ: {str(e)}</h2>'

@app.route('/webhook', methods=['POST'])
def webhook():
    """نقطة استقبال تحديثات Telegram"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK'
    return 'Bad Request'

# ============================================================================
# تشغيل التطبيق
# ============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 بدء التشغيل على منفذ {port}")
    
    # إزالة أي ويب هوك سابق وتعيين جديد
    bot.remove_webhook()
    
    # تشغيل التطبيق
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # على Render، نعيين ويب هوك تلقائياً
    @app.before_first_request
    def setup_webhook():
        webhook_url = f"https://{app.config.get('SERVER_NAME', '')}/webhook"
        if not webhook_url.startswith('https://'):
            webhook_url = f"https://{webhook_url}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logger.info(f"✅ تم تعيين ويب هوك على: {webhook_url}")