"""
🚖 بوت النقل الذكي - نسخة مع واجهة تفاعلية محسنة
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
    BOT_TOKEN = "8425005126:8314762629:AAFewIWyTZmANrnkaSyUZHUiDU0NmioJayo"

# تهيئة التطبيق والبوت
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# تخزين
users = {}
active_drivers = {}
ride_requests = []

# ============================================================================
# دوال مساعدة للواجهة التفاعلية
# ============================================================================

def create_main_menu():
    """إنشاء القائمة الرئيسية مع الأزرار الداخلية"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = [
        types.InlineKeyboardButton("🚖 طلب رحلة", callback_data="request_ride"),
        types.InlineKeyboardButton("📋 رحلاتي", callback_data="my_rides"),
        types.InlineKeyboardButton("💰 رصيدي", callback_data="my_balance"),
        types.InlineKeyboardButton("⭐ التقييمات", callback_data="ratings"),
        types.InlineKeyboardButton("🎫 العروض", callback_data="offers"),
        types.InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings"),
        types.InlineKeyboardButton("📞 الدعم", callback_data="support"),
        types.InlineKeyboardButton("ℹ️ عن البوت", callback_data="about")
    ]
    
    # ترتيب الأزرار في صفوف
    for i in range(0, len(buttons), 2):
        if i+1 < len(buttons):
            markup.add(buttons[i], buttons[i+1])
        else:
            markup.add(buttons[i])
    
    return markup

def create_driver_menu():
    """إنشاء قائمة السائق مع الأزرار الداخلية"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = [
        types.InlineKeyboardButton("🟢 بدء العمل", callback_data="driver_start"),
        types.InlineKeyboardButton("🔴 إيقاف", callback_data="driver_stop"),
        types.InlineKeyboardButton("📍 تحديث الموقع", callback_data="update_location"),
        types.InlineKeyboardButton("📊 الطلبات", callback_data="view_requests"),
        types.InlineKeyboardButton("💰 الأرباح", callback_data="driver_earnings"),
        types.InlineKeyboardButton("📈 الإحصائيات", callback_data="driver_stats"),
        types.InlineKeyboardButton("👤 الملف", callback_data="driver_profile"),
        types.InlineKeyboardButton("⚙️ الإعدادات", callback_data="driver_settings")
    ]
    
    for i in range(0, len(buttons), 2):
        if i+1 < len(buttons):
            markup.add(buttons[i], buttons[i+1])
        else:
            markup.add(buttons[i])
    
    return markup

def create_ride_types_menu():
    """قائمة أنواع الرحلات"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    markup.add(
        types.InlineKeyboardButton("🚗 سيارة عادية", callback_data="ride_normal"),
        types.InlineKeyboardButton("🚙 سيارة فاخرة", callback_data="ride_premium"),
        types.InlineKeyboardButton("🚐 عائلية", callback_data="ride_family"),
        types.InlineKeyboardButton("🚗 اقتصادية", callback_data="ride_economy"),
        types.InlineKeyboardButton("↩️ رجوع", callback_data="back_to_main")
    )
    
    return markup

def create_payment_menu():
    """قائمة وسائل الدفع"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    markup.add(
        types.InlineKeyboardButton("💳 بطاقة ائتمان", callback_data="pay_card"),
        types.InlineKeyboardButton("📱 محفظة إلكترونية", callback_data="pay_wallet"),
        types.InlineKeyboardButton("💵 نقداً", callback_data="pay_cash"),
        types.InlineKeyboardButton("↩️ رجوع", callback_data="back_to_main")
    )
    
    return markup

def create_confirmation_menu():
    """قائمة تأكيد"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("✅ تأكيد", callback_data="confirm_yes"),
        types.InlineKeyboardButton("❌ إلغاء", callback_data="confirm_no")
    )
    
    return markup

def create_rating_menu():
    """قائمة التقييم"""
    markup = types.InlineKeyboardMarkup(row_width=5)
    
    markup.add(
        types.InlineKeyboardButton("⭐", callback_data="rate_1"),
        types.InlineKeyboardButton("⭐⭐", callback_data="rate_2"),
        types.InlineKeyboardButton("⭐⭐⭐", callback_data="rate_3"),
        types.InlineKeyboardButton("⭐⭐⭐⭐", callback_data="rate_4"),
        types.InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="rate_5")
    )
    
    return markup

def create_quick_actions_menu():
    """أزرار سريعة للعمليات المتكررة"""
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    markup.add(
        types.InlineKeyboardButton("🚖 طلب", callback_data="quick_request"),
        types.InlineKeyboardButton("📍 موقعي", callback_data="quick_location"),
        types.InlineKeyboardButton("💰 رصيد", callback_data="quick_balance")
    )
    
    markup.add(
        types.InlineKeyboardButton("📞 دعم", callback_data="quick_support"),
        types.InlineKeyboardButton("⭐ تقييم", callback_data="quick_rate"),
        types.InlineKeyboardButton("⚙️ إعدادات", callback_data="quick_settings")
    )
    
    return markup

# ============================================================================
# معالجات الأزرار التفاعلية
# ============================================================================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """معالجة جميع ضغطات الأزرار التفاعلية"""
    user_id = str(call.from_user.id)
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    logger.info(f"🔘 ضغط زر: {call.data} من {user_id}")
    
    try:
        # حذف الرسالة القديمة
        bot.delete_message(chat_id, message_id)
    except:
        pass
    
    # معالجة البيانات حسب النوع
    if call.data == "request_ride":
        handle_ride_request_callback(chat_id)
    
    elif call.data == "my_rides":
        handle_my_rides_callback(chat_id, user_id)
    
    elif call.data == "my_balance":
        handle_balance_callback(chat_id, user_id)
    
    elif call.data == "settings":
        handle_settings_callback(chat_id)
    
    elif call.data == "support":
        handle_support_callback(chat_id)
    
    elif call.data == "about":
        handle_about_callback(chat_id)
    
    elif call.data == "back_to_main":
        handle_start_callback(chat_id, call.from_user)
    
    elif call.data.startswith("ride_"):
        handle_ride_type_callback(chat_id, call.data)
    
    elif call.data.startswith("pay_"):
        handle_payment_callback(chat_id, call.data)
    
    elif call.data.startswith("rate_"):
        handle_rating_callback(chat_id, call.data, user_id)
    
    elif call.data == "driver_start":
        handle_driver_start_callback(chat_id, user_id)
    
    elif call.data == "driver_stop":
        handle_driver_stop_callback(chat_id, user_id)
    
    elif call.data == "view_requests":
        handle_view_requests_callback(chat_id, user_id)
    
    # إضافة رد للزر المضغوط
    bot.answer_callback_query(call.id, text="جاري المعالجة...")

# ============================================================================
# دوال معالجة الأزرار
# ============================================================================

def handle_ride_request_callback(chat_id):
    """معالجة طلب رحلة عبر الزر"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📍 أرسل موقعك تلقائياً", callback_data="send_location_auto"),
        types.InlineKeyboardButton("📝 أدخل العنوان يدوياً", callback_data="enter_address"),
        types.InlineKeyboardButton("🚗 اختر نوع السيارة", callback_data="select_car_type"),
        types.InlineKeyboardButton("↩️ رجوع", callback_data="back_to_main")
    )
    
    bot.send_message(
        chat_id,
        "📍 <b>طلب رحلة جديدة</b>\n\n"
        "اختر طريقة تحديد الموقع:",
        reply_markup=markup
    )

def handle_my_rides_callback(chat_id, user_id):
    """معالجة عرض الرحلات"""
    # عرض قائمة الرحلات مع أزرار
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔄 الرحلات الحالية", callback_data="current_rides"),
        types.InlineKeyboardButton("📜 السابقة", callback_data="past_rides")
    )
    markup.add(
        types.InlineKeyboardButton("📤 تصدير", callback_data="export_rides"),
        types.InlineKeyboardButton("↩️ رجوع", callback_data="back_to_main")
    )
    
    bot.send_message(
        chat_id,
        "📋 <b>رحلاتي</b>\n\n"
        "يمكنك عرض الرحلات الحالية والسابقة:",
        reply_markup=markup
    )

def handle_balance_callback(chat_id, user_id):
    """معالجة عرض الرصيد"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💳 شحن الرصيد", callback_data="recharge"),
        types.InlineKeyboardButton("📤 سحب", callback_data="withdraw")
    )
    markup.add(
        types.InlineKeyboardButton("💸 كوبون خصم", callback_data="coupon"),
        types.InlineKeyboardButton("📊 التفاصيل", callback_data="balance_details")
    )
    markup.add(
        types.InlineKeyboardButton("↩️ رجوع", callback_data="back_to_main")
    )
    
    bot.send_message(
        chat_id,
        "💰 <b>رصيدك</b>\n\n"
        f"• الرصيد الحالي: <b>0.00 ر.س</b>\n"
        f"• الرصيد المحجوز: <b>0.00 ر.س</b>\n"
        f"• إجمالي المشتريات: <b>0.00 ر.س</b>\n\n"
        "اختر الإجراء المطلوب:",
        reply_markup=markup
    )

def handle_settings_callback(chat_id):
    """معالجة الإعدادات"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("👤 البيانات الشخصية", callback_data="edit_profile"),
        types.InlineKeyboardButton("🔔 الإشعارات", callback_data="notifications"),
        types.InlineKeyboardButton("🌍 اللغة", callback_data="language"),
        types.InlineKeyboardButton("🔒 الخصوصية", callback_data="privacy"),
        types.InlineKeyboardButton("📱 المظهر", callback_data="theme"),
        types.InlineKeyboardButton("↩️ رجوع", callback_data="back_to_main")
    )
    
    bot.send_message(
        chat_id,
        "⚙️ <b>الإعدادات</b>\n\n"
        "يمكنك تخصيص إعدادات حسابك:",
        reply_markup=markup
    )

def handle_support_callback(chat_id):
    """معالجة الدعم الفني"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📞 اتصال فوري", callback_data="call_support"),
        types.InlineKeyboardButton("💬 محادثة نصية", callback_data="chat_support"),
        types.InlineKeyboardButton("📧 بريد إلكتروني", callback_data="email_support"),
        types.InlineKeyboardButton("❓ الأسئلة الشائعة", callback_data="faq"),
        types.InlineKeyboardButton("↩️ رجوع", callback_data="back_to_main")
    )
    
    bot.send_message(
        chat_id,
        "📞 <b>الدعم الفني</b>\n\n"
        "• هاتف الدعم: <b>920000000</b>\n"
        "• البريد: <b>support@example.com</b>\n"
        "• ساعات العمل: 24/7\n\n"
        "اختر طريقة التواصل:",
        reply_markup=markup
    )

def handle_about_callback(chat_id):
    """معالجة معلومات البوت"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📱 التطبيق", callback_data="download_app"),
        types.InlineKeyboardButton("📄 الشروط", callback_data="terms"),
        types.InlineKeyboardButton("🔒 الخصوصية", callback_data="privacy_policy"),
        types.InlineKeyboardButton("⭐ تقييم", callback_data="rate_app")
    )
    markup.add(
        types.InlineKeyboardButton("↩️ رجوع", callback_data="back_to_main")
    )
    
    bot.send_message(
        chat_id,
        "ℹ️ <b>عن بوت النقل الذكي</b>\n\n"
        "🚖 <b>أول تطبيق نقل ذكي في المنطقة</b>\n\n"
        "• بدأنا في 2024\n"
        "• أكثر من 100,000 مستخدم\n"
        "• 5,000+ سائق\n"
        "• 4.8 ⭐ تقييم\n\n"
        "<b>مميزاتنا:</b>\n"
        "✓ رحلات آمنة\n"
        "✓ أسعار تنافسية\n"
        "✓ دفع إلكتروني\n"
        "✓ تتبع مباشر",
        reply_markup=markup
    )

def handle_driver_start_callback(chat_id, user_id):
    """بدء عمل السائق"""
    active_drivers[user_id] = {
        'id': user_id,
        'status': 'active',
        'earnings': 0
    }
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📍 تحديث الموقع", callback_data="update_location"),
        types.InlineKeyboardButton("📊 الطلبات", callback_data="view_requests"),
        types.InlineKeyboardButton("💰 الأرباح", callback_data="driver_earnings"),
        types.InlineKeyboardButton("🔴 إيقاف", callback_data="driver_stop")
    )
    
    bot.send_message(
        chat_id,
        "✅ <b>تم تفعيل وضع السائق!</b>\n\n"
        "🎯 أنت الآن مرئي للعملاء\n"
        "📱 ستستقبل طلبات جديدة تلقائياً\n"
        "💰 ابدأ بكسب الأرباح الآن!\n\n"
        "📊 <b>الأوامر السريعة:</b>",
        reply_markup=markup
    )

def handle_view_requests_callback(chat_id, user_id):
    """عرض طلبات الركوب"""
    if ride_requests:
        markup = types.InlineKeyboardMarkup(row_width=1)
        for i, ride in enumerate(ride_requests[:5]):  # عرض أول 5 طلبات
            markup.add(
                types.InlineKeyboardButton(
                    f"🚖 طلب #{i+1} - {ride.get('distance', '0')}km", 
                    callback_data=f"accept_ride_{i}"
                )
            )
        markup.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="driver_dashboard"))
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="view_requests"))
        markup.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="driver_dashboard"))
    
    bot.send_message(
        chat_id,
        f"📊 <b>الطلبات المتاحة</b>\n\n"
        f"• عدد الطلبات: <b>{len(ride_requests)}</b>\n"
        f"• أقرب طلب: <b>1.5 كم</b>\n"
        f"• متوسط السعر: <b>25 ر.س</b>\n\n"
        f"اختر طلباً للقبول:",
        reply_markup=markup
    )

# ============================================================================
# معالجات الرسائل الرئيسية (محسنة)
# ============================================================================

@bot.message_handler(commands=['start', 'menu'])
def handle_start(message):
    """معالجة أمر /start مع واجهة تفاعلية"""
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
    
    # إنشاء لوحة مفاتيح رئيسية
    markup_reply = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup_reply.add(
        types.KeyboardButton('🚖 طلب رحلة'),
        types.KeyboardButton('📍 إرسال موقعي', request_location=True)
    )
    markup_reply.add(
        types.KeyboardButton('💰 رصيدي'),
        types.KeyboardButton('📋 رحلاتي')
    )
    markup_reply.add(
        types.KeyboardButton('⚙️ الإعدادات'),
        types.KeyboardButton('📞 الدعم')
    )
    
    # إرسال الرسالة مع الأزرار التفاعلية
    bot.send_message(
        message.chat.id,
        f"🎉 <b>مرحباً {name} في بوت النقل الذكي!</b>\n\n"
        "🚖 <b>أسرع وأأمن خدمة نقل</b>\n"
        "✨ <b>اختر الخدمة المطلوبة:</b>",
        reply_markup=markup_reply
    )
    
    # إرسال الأزرار التفاعلية الرئيسية
    bot.send_message(
        message.chat.id,
        "📱 <b>القائمة التفاعلية السريعة:</b>",
        reply_markup=create_main_menu()
    )
    
    # إرسال أزرار سريعة للعمليات المتكررة
    bot.send_message(
        message.chat.id,
        "⚡ <b>أوامر سريعة:</b>",
        reply_markup=create_quick_actions_menu()
    )

def handle_start_callback(chat_id, user):
    """نسخة من handle_start للاستدعاء من الأزرار"""
    user_id = str(user.id)
    name = user.first_name
    
    # إنشاء لوحة مفاتيح رئيسية
    markup_reply = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup_reply.add(
        types.KeyboardButton('🚖 طلب رحلة'),
        types.KeyboardButton('📍 إرسال موقعي', request_location=True)
    )
    markup_reply.add(
        types.KeyboardButton('💰 رصيدي'),
        types.KeyboardButton('📋 رحلاتي')
    )
    markup_reply.add(
        types.KeyboardButton('⚙️ الإعدادات'),
        types.KeyboardButton('📞 الدعم')
    )
    
    bot.send_message(
        chat_id,
        f"🏠 <b>القائمة الرئيسية</b>\n\n"
        f"مرحباً مرة أخرى {name}!\n"
        "اختر الخدمة المطلوبة:",
        reply_markup=markup_reply
    )
    
    bot.send_message(
        chat_id,
        "📱 <b>القائمة التفاعلية:</b>",
        reply_markup=create_main_menu()
    )

@bot.message_handler(func=lambda message: message.text == '🚖 طلب رحلة')
def handle_ride_request(message):
    """طلب رحلة جديدة مع واجهة تفاعلية"""
    logger.info(f"🚖 طلب رحلة من: {message.from_user.id}")
    
    # عرض أنواع الرحلات
    bot.send_message(
        message.chat.id,
        "🚗 <b>اختر نوع الرحلة:</b>\n\n"
        "• 🚗 عادية: سعر أساسي\n"
        "• 🚙 فاخرة: راحة أكثر\n"
        "• 🚐 عائلية: سيارة كبيرة\n"
        "• 🚗 اقتصادية: توفير سعر",
        reply_markup=create_ride_types_menu()
    )

@bot.message_handler(func=lambda message: message.text == '💰 رصيدي')
def handle_balance(message):
    """عرض الرصيد مع واجهة تفاعلية"""
    user_id = str(message.from_user.id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💳 شحن الآن", callback_data="recharge_now"),
        types.InlineKeyboardButton("📊 التفاصيل", callback_data="balance_details"),
        types.InlineKeyboardButton("🎫 كوبون", callback_data="apply_coupon"),
        types.InlineKeyboardButton("📤 سحب", callback_data="withdraw_funds")
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

@bot.message_handler(func=lambda message: message.text == '⚙️ الإعدادات')
def handle_settings(message):
    """عرض الإعدادات مع واجهة تفاعلية"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("👤 تعديل الملف الشخصي", callback_data="edit_profile"),
        types.InlineKeyboardButton("🔔 إدارة الإشعارات", callback_data="manage_notifications"),
        types.InlineKeyboardButton("🌍 تغيير اللغة", callback_data="change_language"),
        types.InlineKeyboardButton("🔐 الأمان والخصوصية", callback_data="security"),
        types.InlineKeyboardButton("🗑️ حذف الحساب", callback_data="delete_account"),
        types.InlineKeyboardButton("↩️ رجوع", callback_data="back_to_main")
    )
    
    bot.send_message(
        message.chat.id,
        "⚙️ <b>الإعدادات والخصوصية</b>\n\n"
        "إدارة إعدادات حسابك وتخصيص تجربتك:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '📞 الدعم')
def handle_support(message):
    """عرض خيارات الدعم مع واجهة تفاعلية"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📞 اتصال هاتفي", url="tel:+966500000000"),
        types.InlineKeyboardButton("✉️ محادثة نصية", callback_data="start_chat"),
        types.InlineKeyboardButton("📧 بريد إلكتروني", url="mailto:support@example.com"),
        types.InlineKeyboardButton("📋 الأسئلة الشائعة", callback_data="show_faq"),
        types.InlineKeyboardButton("📍 مواقع الفروع", callback_data="branches")
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

@bot.message_handler(content_types=['location'])
def handle_location(message):
    """معالجة الموقع مع عرض أزرار تفاعلية"""
    location = message.location
    
    logger.info(f"📍 موقع من: {message.from_user.id}")
    
    # إنشاء أزرار تفاعلية بعد استلام الموقع
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ تأكيد الموقع", callback_data="confirm_location"),
        types.InlineKeyboardButton("🔄 إعادة الإرسال", callback_data="resend_location")
    )
    markup.add(
        types.InlineKeyboardButton("📍 اختيار من الخريطة", callback_data="pick_from_map"),
        types.InlineKeyboardButton("🚖 طلب الآن", callback_data="request_now")
    )
    
    bot.send_message(
        message.chat.id,
        f"📍 <b>تم استلام موقعك!</b>\n\n"
        f"• <b>الإحداثيات:</b>\n"
        f"  خط العرض: {location.latitude:.6f}\n"
        f"  خط الطول: {location.longitude:.6f}\n\n"
        f"هل تريد تأكيد هذا الموقع؟",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '👤 حسابي')
def handle_profile(message):
    """عرض الملف الشخصي مع أزرار تفاعلية"""
    user_id = str(message.from_user.id)
    user_data = users.get(user_id, {})
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✏️ تعديل الاسم", callback_data="edit_name"),
        types.InlineKeyboardButton("📱 رقم الجوال", callback_data="edit_phone")
    )
    markup.add(
        types.InlineKeyboardButton("📧 البريد الإلكتروني", callback_data="edit_email"),
        types.InlineKeyboardButton("📷 الصورة", callback_data="edit_photo")
    )
    markup.add(
        types.InlineKeyboardButton("⭐ تقييماتي", callback_data="my_ratings"),
        types.InlineKeyboardButton("🏆 إنجازات", callback_data="achievements")
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
    """عرض العروض والكوبونات"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎁 احصل على أول رحلة مجاناً", callback_data="offer_first_ride"),
        types.InlineKeyboardButton("👥 دعوة أصدقاء - احصل على 50 ر.س", callback_data="invite_friends"),
        types.InlineKeyboardButton("📱 حمّل التطبيق - خصم 20%", callback_data="download_app_offer"),
        types.InlineKeyboardButton("🎯 عرض العودة - 30% خصم", callback_data="comeback_offer"),
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
        "3. 📱 <b>خصم التطبيق</b>\n"
        "   - خصم 20% على أول 5 رحلات\n\n"
        "اختر العرض:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """معالجة جميع الرسائل الأخرى مع اقتراحات تفاعلية"""
    logger.info(f"📩 رسالة: {message.text} من {message.from_user.id}")
    
    # إنشاء أزرار سريعة للرد
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🚖 طلب رحلة", callback_data="request_ride"),
        types.InlineKeyboardButton("💰 رصيدي", callback_data="my_balance")
    )
    markup.add(
        types.InlineKeyboardButton("📞 الدعم", callback_data="support"),
        types.InlineKeyboardButton("🏠 القائمة", callback_data="back_to_main")
    )
    
    bot.reply_to(
        message,
        "🤖 <b>مرحباً!</b>\n\n"
        "يمكنني مساعدتك في:\n"
        "• طلب رحلة 🚖\n"
        "• معرفة رصيدك 💰\n"
        "• الدعم الفني 📞\n\n"
        "اختر من الأزرار أدناه أو اكتب /start",
        reply_markup=markup
    )

# ============================================================================
# صفحات الويب (محفوظة كما هي)
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
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.1);
                padding: 40px;
                border-radius: 20px;
                text-align: center;
            }}
            .features {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 15px;
                margin: 30px 0;
            }}
            .feature {{
                background: rgba(255, 255, 255, 0.2);
                padding: 15px;
                border-radius: 10px;
            }}
            .btn {{
                display: inline-block;
                padding: 12px 24px;
                background: white;
                color: #667eea;
                text-decoration: none;
                border-radius: 8px;
                margin: 10px;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚖 بوت النقل الذكي</h1>
            <p>نظام متكامل بإمكانيات تفاعلية متطورة</p>
            
            <div style="background: rgba(255,255,255,0.2); padding: 20px; border-radius: 10px; margin: 20px 0;">
                <p>🟢 <strong>الخادم يعمل بنجاح</strong></p>
                <p>🤖 <strong>البوت:</strong> {bot_status}</p>
                <p>👥 <strong>المستخدمين:</strong> {len(users)}</p>
                <p>🚕 <strong>السائقين:</strong> {len(active_drivers)}</p>
            </div>
            
            <h3>✨ المميزات الجديدة:</h3>
            <div class="features">
                <div class="feature">🎯 واجهة تفاعلية</div>
                <div class="feature">🚖 أزرار سريعة</div>
                <div class="feature">💰 شحن إلكتروني</div>
                <div class="feature">⭐ تقييم مباشر</div>
                <div class="feature">📍 تحديد مواقع</div>
                <div class="feature">📊 إحصائيات حية</div>
            </div>
            
            <div>
                <a href="/set_webhook" class="btn">⚙️ تعيين ويب هوك</a>
                <a href="/test_bot" class="btn">🧪 اختبار البوت</a>
                <a href="https://t.me/Dhdhdyduudbot" target="_blank" class="btn">💬 فتح البوت</a>
            </div>
            
            <div style="margin-top: 40px; opacity: 0.8;">
                <p>🔗 الرابط: https://dhhfhfjd.onrender.com</p>
                <p>© 2024 بوت النقل الذكي - الإصدار التفاعلي</p>
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
        logger.info(f"🔄 محاولة تعيين ويب هوك على: {webhook_url}")
        
        bot.remove_webhook()
        result = bot.set_webhook(url=webhook_url)
        bot_info = bot.get_me()
        
        return f'''
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <meta charset="UTF-8">
            <title>✅ تم تعيين الويب هوك</title>
            <style>
                body {{ padding: 50px; text-align: center; }}
                .success {{
                    background: #d4edda;
                    color: #155724;
                    padding: 20px;
                    border-radius: 10px;
                    margin: 20px auto;
                    max-width: 600px;
                }}
            </style>
        </head>
        <body>
            <div class="success">
                <h2>✅ تم تعيين الويب هوك بنجاح!</h2>
                <p><strong>البوت التفاعلي:</strong> @{bot_info.username}</p>
                <p><strong>الرابط:</strong> {webhook_url}</p>
                <p><strong>الميزات:</strong> أزرار تفاعلية، واجهة محسنة</p>
            </div>
            <div style="margin-top: 30px;">
                <a href="https://t.me/{bot_info.username}" target="_blank" 
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

@app.route('/test_bot')
def test_bot():
    """صفحة اختبار البوت"""
    return '''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>🧪 اختبار البوت التفاعلي</title>
        <style>
            body { padding: 30px; font-family: Arial; text-align: center; }
            .instructions { 
                background: #e9f7fe; 
                padding: 20px; 
                border-radius: 10px;
                text-align: right;
                margin: 20px auto;
                max-width: 500px;
            }
            .btn-test {
                display: inline-block;
                padding: 10px 20px;
                margin: 5px;
                background: #28a745;
                color: white;
                border-radius: 5px;
                text-decoration: none;
            }
        </style>
    </head>
    <body>
        <h1>🧪 اختبار البوت التفاعلي</h1>
        
        <div class="instructions">
            <h3>🚀 مميزات البوت الجديدة:</h3>
            <ul>
                <li>🎯 واجهة تفاعلية مع أزرار داخلية</li>
                <li>🚖 طلب رحلة بنقرة واحدة</li>
                <li>💰 شحن الرصيد مباشرة</li>
                <li>⭐ تقييم السائق بسهولة</li>
                <li>📍 تحديد مواقع متقدم</li>
                <li>📊 إحصائيات فورية</li>
            </ul>
            
            <h3>📱 خطوات الاختبار:</h3>
            <ol>
                <li>افتح تطبيق Telegram</li>
                <li>ابحث عن: <strong>@Dhdhdyduudbot</strong></li>
                <li>أرسل: <code>/start</code></li>
                <li>جرب الأزرار التفاعلية داخل الرسائل</li>
                <li>استخدم القوائم المنبثقة</li>
            </ol>
        </div>
        
        <div style="margin-top: 30px;">
            <h3>🔘 جرب هذه الأزرار في البوت:</h3>
            <div>
                <span class="btn-test">🚖 طلب رحلة</span>
                <span class="btn-test">💰 رصيدي</span>
                <span class="btn-test">⭐ التقييمات</span>
                <span class="btn-test">🎫 العروض</span>
                <span class="btn-test">⚙️ الإعدادات</span>
                <span class="btn-test">📞 الدعم</span>
            </div>
        </div>
        
        <div style="margin-top: 30px;">
            <a href="https://t.me/Dhdhdyduudbot" target="_blank" 
               style="padding: 15px 30px; background: #0088cc; color: white; text-decoration: none; border-radius: 8px; font-size: 1.2em;">
                🚀 افتح البوت التفاعلي الآن
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
            logger.info(f"📩 استلام تحديث: {update.update_id}")
            bot.process_new_updates([update])
            logger.info(f"✅ تم معالجة تحديث: {update.update_id}")
            return 'OK', 200
        except Exception as e:
            logger.error(f"❌ خطأ في ويب هوك: {e}")
            return 'Error', 500
    return 'Bad Request', 400

# ============================================================================
# تهيئة وتشغيل
# ============================================================================

def init_bot():
    """تهيئة البوت"""
    try:
        bot_info = bot.get_me()
        logger.info(f"✅ البوت التفاعلي جاهز: @{bot_info.username}")
        logger.info("✅ تم تحميل الواجهة التفاعلية مع الأزرار")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تهيئة البوت: {e}")
        return False

if __name__ != '__main__':
    init_bot()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 بدء التشغيل على منفذ {port}")
    app.run(host='0.0.0.0', port=port, debug=False)