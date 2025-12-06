"""
🚖 بوت النقل الذكي - نسخة معدلة بدون before_first_request
"""

import os
import logging
from flask import Flask, request, jsonify
import telebot
from telebot import types
import threading
import time

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
    BOT_TOKEN = "BOT_TOKEN"

# تهيئة التطبيق والبوت
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# تخزين
users = {}
active_drivers = {}
ride_requests = []

# متغير لتتبع حالة الويب هوك
webhook_set = False

# ============================================================================
# دالة لإعداد الويب هوك بعد بدء التطبيق
# ============================================================================

def setup_webhook_after_start():
    """إعداد الويب هوك بعد بدء التطبيق بفترة قصيرة"""
    time.sleep(2)  # انتظار 2 ثانية لبدء التطبيق
    
    try:
        # الحصول على اسم المضيف من متغيرات البيئة أو استخدام افتراضي
        host = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')
        
        if host:
            webhook_url = f"https://{host}/webhook"
        else:
            # إذا لم يكن هناك مضيف خارجي، قد نكون في التطوير المحلي
            webhook_url = None
            logger.warning("⚠️ لم يتم العثور على مضيف خارجي، لن يتم تعيين ويب هوك تلقائياً")
            return
        
        # إزالة أي ويب هوك سابق وتعيين الجديد
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=webhook_url)
        
        global webhook_set
        webhook_set = True
        
        logger.info(f"✅ تم تعيين ويب هوك على: {webhook_url}")
        
    except Exception as e:
        logger.error(f"❌ فشل تعيين ويب هوك: {e}")

# ============================================================================
# دوال لإنشاء الأزرار
# ============================================================================

def create_main_keyboard():
    """لوحة مفاتيح رئيسية"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    markup.row('🚖 طلب رحلة', '📍 إرسال موقعي')
    markup.row('💰 رصيدي', '📋 رحلاتي')
    markup.row('⚙️ الإعدادات', '📞 الدعم')
    markup.row('👤 حسابي', '🎫 العروض')
    
    return markup

def create_inline_main_menu():
    """قائمة داخلية رئيسية"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("🚖 طلب رحلة", callback_data="req_ride"),
        types.InlineKeyboardButton("💰 رصيدي", callback_data="my_balance")
    )
    
    markup.add(
        types.InlineKeyboardButton("📋 رحلاتي", callback_data="my_rides"),
        types.InlineKeyboardButton("⭐ تقييماتي", callback_data="my_ratings")
    )
    
    markup.add(
        types.InlineKeyboardButton("🎫 العروض", callback_data="offers"),
        types.InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")
    )
    
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

# ============================================================================
# معالجات الرسائل
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
    
    bot.send_message(
        message.chat.id,
        welcome_msg,
        reply_markup=create_main_keyboard()
    )
    
    # إرسال القائمة التفاعلية
    bot.send_message(
        message.chat.id,
        "📱 <b>القائمة التفاعلية السريعة:</b>\n(اضغط على الأزرار داخل الرسالة)",
        reply_markup=create_inline_main_menu()
    )

@bot.message_handler(func=lambda message: message.text == '🚖 طلب رحلة')
def handle_ride_request(message):
    """طلب رحلة جديدة"""
    logger.info(f"🚖 طلب رحلة من: {message.from_user.id}")
    
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

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """معالجة ضغطات الأزرار"""
    chat_id = call.message.chat.id
    
    bot.answer_callback_query(call.id, text="جاري المعالجة...")
    
    if call.data == "req_ride":
        bot.send_message(
            chat_id,
            "🚖 <b>طلب رحلة جديدة</b>\n\n"
            "الرجاء إرسال موقعك:",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                types.KeyboardButton("📍 إرسال موقعي", request_location=True)
            )
        )
    
    elif call.data.startswith("ride_"):
        ride_type = call.data.replace("ride_", "")
        types_map = {
            "normal": "عادية",
            "premium": "فاخرة",
            "family": "عائلية",
            "economy": "اقتصادية"
        }
        
        ride_name = types_map.get(ride_type, "عادية")
        
        bot.send_message(
            chat_id,
            f"✅ <b>تم اختيار رحلة {ride_name}</b>\n\n"
            f"الرجاء إرسال موقعك لبدء البحث عن سائق...",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                types.KeyboardButton("📍 إرسال موقعي", request_location=True)
            )
        )
    
    elif call.data == "back_main":
        bot.send_message(
            chat_id,
            "🏠 <b>القائمة الرئيسية</b>",
            reply_markup=create_main_keyboard()
        )
        
        bot.send_message(
            chat_id,
            "📱 <b>القائمة التفاعلية:</b>",
            reply_markup=create_inline_main_menu()
        )
    
    else:
        bot.send_message(
            chat_id,
            f"🔘 <b>تم الضغط على: {call.data}</b>\n\n"
            f"هذه الميزة قيد التطوير حالياً.",
            reply_markup=create_inline_main_menu()
        )

@bot.message_handler(content_types=['location'])
def handle_location(message):
    """معالجة الموقع"""
    location = message.location
    
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

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """معالجة جميع الرسائل الأخرى"""
    if message.text not in [
        '🚖 طلب رحلة', '📍 إرسال موقعي', '💰 رصيدي',
        '📋 رحلاتي', '⚙️ الإعدادات', '📞 الدعم',
        '👤 حسابي', '🎫 العروض'
    ]:
        bot.send_message(
            message.chat.id,
            "🤖 <b>مرحباً!</b>\n\n"
            "استخدم الأزرار أدناه للتنقل، أو اكتب /start لرؤية القائمة الرئيسية.",
            reply_markup=create_main_keyboard()
        )

# ============================================================================
# صفحات الويب
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
            .status {{
                padding: 10px;
                background: #f0f0f0;
                border-radius: 5px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚖 بوت النقل الذكي</h1>
            <p>الإصدار المعدل - بدون before_first_request</p>
            
            <div class="status">
                <p>🤖 <strong>البوت:</strong> {bot_status}</p>
                <p>👥 <strong>المستخدمين:</strong> {len(users)}</p>
                <p>🌐 <strong>الويب هوك:</strong> {'✅ مفعل' if webhook_set else '❌ غير مفعل'}</p>
            </div>
            
            <div>
                <a href="/set_webhook" class="btn">⚙️ تعيين ويب هوك</a>
                <a href="https://t.me/Dhdhdyduudbot" target="_blank" class="btn">💬 فتح البوت</a>
                <a href="/test" class="btn">🧪 اختبار</a>
            </div>
            
            <div style="margin-top: 30px;">
                <h3>🔘 مميزات البوت:</h3>
                <p>• أزرار تفاعلية داخل الرسائل</p>
                <p>• تحديد الموقع تلقائياً</p>
                <p>• طلب رحلة بنقرة واحدة</p>
                <p>• دعم فني مباشر</p>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/set_webhook')
def set_webhook():
    """تعيين ويب هوك يدوياً"""
    try:
        # الحصول على عنوان التطبيق
        host = request.host
        webhook_url = f"https://{host}/webhook"
        
        # إزالة أي ويب هوك سابق
        bot.remove_webhook()
        
        # تعيين ويب هوك جديد
        bot.set_webhook(url=webhook_url)
        
        global webhook_set
        webhook_set = True
        
        logger.info(f"✅ تم تعيين ويب هوك على: {webhook_url}")
        
        return f'''
        <!DOCTYPE html>
        <html dir="rtl">
        <head><meta charset="UTF-8"></head>
        <body style="padding: 50px; text-align: center;">
            <h2 style="color: green;">✅ تم تعيين الويب هوك بنجاح!</h2>
            <p><strong>الرابط:</strong> {webhook_url}</p>
            <p><strong>الحالة:</strong> البوت جاهز لاستقبال الرسائل</p>
            <div style="margin-top: 30px;">
                <a href="https://t.me/Dhdhdyduudbot" target="_blank" 
                   style="padding: 10px 20px; background: #0088cc; color: white; text-decoration: none; border-radius: 5px;">
                    💬 افتح البوت الآن
                </a>
            </div>
            <div style="margin-top: 20px;">
                <a href="/">العودة للصفحة الرئيسية</a>
            </div>
        </body>
        </html>
        '''
        
    except Exception as e:
        logger.error(f"❌ خطأ في تعيين الويب هوك: {e}")
        return f'''
        <div style="padding: 50px; text-align: center;">
            <h2 style="color: red;">❌ خطأ في تعيين الويب هوك</h2>
            <p>{str(e)}</p>
            <a href="/">العودة</a>
        </div>
        ''', 500

@app.route('/test')
def test_page():
    """صفحة اختبار"""
    return '''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>🧪 اختبار البوت</title>
        <style>
            body { padding: 30px; font-family: Arial; text-align: center; }
        </style>
    </head>
    <body>
        <h1>🧪 اختبار البوت</h1>
        
        <div style="background: #f0f0f0; padding: 20px; border-radius: 10px; margin: 20px auto; max-width: 500px;">
            <h3>📱 خطوات الاختبار:</h3>
            <ol style="text-align: right;">
                <li>افتح تطبيق Telegram</li>
                <li>ابحث عن: <strong>@Dhdhdyduudbot</strong></li>
                <li>أرسل: <code>/start</code></li>
                <li>اضغط على أي زر في القائمة</li>
                <li>جرب الأزرار التفاعلية داخل الرسائل</li>
            </ol>
        </div>
        
        <div style="margin-top: 30px;">
            <a href="https://t.me/Dhdhdyduudbot" target="_blank" 
               style="padding: 15px 30px; background: #0088cc; color: white; text-decoration: none; border-radius: 8px; font-size: 1.2em;">
                🚀 افتح البوت الآن
            </a>
        </div>
        
        <div style="margin-top: 30px;">
            <a href="/">العودة للصفحة الرئيسية</a>
        </div>
    </body>
    </html>
    '''

@app.route('/webhook', methods=['POST'])
def webhook():
    """نقطة استقبال تحديثات Telegram"""
    if request.headers.get('content-type') == 'application/json':
        try:
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return 'OK'
        except Exception as e:
            logger.error(f"❌ خطأ في ويب هوك: {e}")
            return 'Error', 500
    return 'Bad Request', 400

# ============================================================================
# بدء التطبيق
# ============================================================================

if __name__ == '__main__':
    # التشغيل المحلي
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 بدء التشغيل على منفذ {port}")
    
    # بدء خيط لإعداد الويب هوك
    webhook_thread = threading.Thread(target=setup_webhook_after_start)
    webhook_thread.daemon = True
    webhook_thread.start()
    
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # على Render، نبدأ خيط لإعداد الويب هوك بعد بدء التطبيق
    webhook_thread = threading.Thread(target=setup_webhook_after_start)
    webhook_thread.daemon = True
    webhook_thread.start()