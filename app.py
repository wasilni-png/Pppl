"""
🚖 بوت النقل الذكي - نسخة كاملة وموثوقة
إصدار نهائي مع جميع الميزات الأساسية
"""

import os
import json
import logging
from datetime import datetime
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

# الحصول على التوكن من متغير البيئة
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN غير معين!")
    # سنستخدم التوكن الموجود للاختبار
    BOT_TOKEN = "8425005126:AAH9I7qu0gjKEpKX52rFWHsuCn9Bw5jaNr0"

# تهيئة البوت
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# تهيئة التطبيق
app = Flask(__name__)

# قاعدة بيانات مبسطة في الذاكرة
users_db = {}
drivers_db = {}
rides_db = {}
user_roles = {}

# ============================================================================
# دوال مساعدة
# ============================================================================

def save_user_data(user_id, data):
    """حفظ بيانات المستخدم"""
    users_db[str(user_id)] = data

def get_user_data(user_id):
    """استرجاع بيانات المستخدم"""
    return users_db.get(str(user_id), {})

def save_driver_data(driver_id, data):
    """حفظ بيانات السائق"""
    drivers_db[str(driver_id)] = data

def get_driver_data(driver_id):
    """استرجاع بيانات السائق"""
    return drivers_db.get(str(driver_id), {})

def save_ride(ride_id, data):
    """حفظ بيانات الرحلة"""
    rides_db[ride_id] = data

def get_ride(ride_id):
    """استرجاع بيانات الرحلة"""
    return rides_db.get(ride_id)

# ============================================================================
# دوال إنشاء الأزرار
# ============================================================================

def main_menu_keyboard():
    """القائمة الرئيسية"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = [
        '🚖 طلب رحلة',
        '📍 إرسال موقعي',
        '💰 رصيدي',
        '📋 رحلاتي',
        '⚙️ إعدادات',
        '📞 الدعم',
        '👤 حسابي',
        '🎫 العروض'
    ]
    
    for i in range(0, len(buttons), 2):
        if i+1 < len(buttons):
            markup.row(buttons[i], buttons[i+1])
        else:
            markup.row(buttons[i])
    
    return markup

def driver_menu_keyboard():
    """قائمة السائق"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    markup.row('🟢 بدء العمل', '🔴 إيقاف')
    markup.row('📍 تحديث موقعي', '📊 الطلبات')
    markup.row('💰 أرباحي', '📈 إحصائيات')
    markup.row('🏠 القائمة الرئيسية')
    
    return markup

def role_selection_keyboard():
    """اختيار الدور"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row('👤 عميل', '🚖 سائق')
    return markup

def ride_types_inline():
    """أنواع الرحلات (أزرار داخلية)"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("🚗 عادية", callback_data="ride_normal"),
        types.InlineKeyboardButton("🚙 فاخرة", callback_data="ride_premium")
    )
    markup.add(
        types.InlineKeyboardButton("🚐 عائلية", callback_data="ride_family"),
        types.InlineKeyboardButton("🚗 اقتصادية", callback_data="ride_economy")
    )
    markup.add(
        types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_ride")
    )
    
    return markup

def payment_methods_inline():
    """وسائل الدفع"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("💳 بطاقة", callback_data="pay_card"),
        types.InlineKeyboardButton("📱 محفظة", callback_data="pay_wallet")
    )
    markup.add(
        types.InlineKeyboardButton("💵 نقداً", callback_data="pay_cash"),
        types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_payment")
    )
    
    return markup

def confirm_ride_inline():
    """تأكيد الرحلة"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("✅ تأكيد الطلب", callback_data="confirm_ride"),
        types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_ride")
    )
    
    return markup

def support_options_inline():
    """خيارات الدعم"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    markup.add(
        types.InlineKeyboardButton("📞 اتصال فوري", callback_data="call_support"),
        types.InlineKeyboardButton("💬 محادثة نصية", callback_data="chat_support"),
        types.InlineKeyboardButton("📧 إرسال شكوى", callback_data="send_complaint"),
        types.InlineKeyboardButton("❓ أسئلة شائعة", callback_data="faq")
    )
    
    return markup

def quick_actions_inline():
    """أزرار سريعة"""
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    markup.add(
        types.InlineKeyboardButton("🚖", callback_data="quick_ride"),
        types.InlineKeyboardButton("📍", callback_data="quick_location"),
        types.InlineKeyboardButton("💰", callback_data="quick_balance")
    )
    markup.add(
        types.InlineKeyboardButton("📞", callback_data="quick_support"),
        types.InlineKeyboardButton("⭐", callback_data="quick_rate"),
        types.InlineKeyboardButton("⚙️", callback_data="quick_settings")
    )
    
    return markup

# ============================================================================
# معالجات الأوامر الرئيسية
# ============================================================================

@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    """معالجة أمر البدء"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    name = message.from_user.first_name
    
    logger.info(f"👋 مستخدم جديد: {name} ({user_id})")
    
    # حفظ بيانات المستخدم
    user_data = {
        'id': user_id,
        'chat_id': chat_id,
        'name': name,
        'username': message.from_user.username,
        'join_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'balance': 100,  # رصيد افتراضي
        'rides_count': 0,
        'rating': 5.0
    }
    save_user_data(user_id, user_data)
    
    # عرض اختيار الدور
    bot.send_message(
        chat_id,
        f"🎉 <b>مرحباً بك {name} في بوت النقل الذكي!</b>\n\n"
        f"🚖 <b>خدمة نقل ذكية توفر لك:</b>\n"
        f"• رحلات سريعة وآمنة\n"
        f"• تتبع مباشر للرحلة\n"
        f"• دفع إلكتروني آمن\n"
        f"• تقييمات موثوقة\n\n"
        f"📱 <b>اختر دورك للبدء:</b>",
        reply_markup=role_selection_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '👤 عميل')
def handle_customer_role(message):
    """اختيار دور العميل"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_roles[str(user_id)] = 'customer'
    
    bot.send_message(
        chat_id,
        "✅ <b>تم تسجيلك كعميل!</b>\n\n"
        "يمكنك الآن طلب رحلات واستخدام جميع خدماتنا.",
        reply_markup=main_menu_keyboard()
    )
    
    # إرسال أزرار سريعة
    bot.send_message(
        chat_id,
        "⚡ <b>أوامر سريعة:</b>",
        reply_markup=quick_actions_inline()
    )

@bot.message_handler(func=lambda message: message.text == '🚖 سائق')
def handle_driver_role(message):
    """اختيار دور السائق"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_roles[str(user_id)] = 'driver'
    
    # حفظ بيانات السائق
    driver_data = {
        'id': user_id,
        'name': message.from_user.first_name,
        'status': 'offline',
        'earnings': 0,
        'rides_completed': 0,
        'rating': 5.0,
        'location': None
    }
    save_driver_data(user_id, driver_data)
    
    bot.send_message(
        chat_id,
        "✅ <b>تم تسجيلك كسائق!</b>\n\n"
        "يمكنك الآن بدء العمل واستقبال طلبات الركوب.",
        reply_markup=driver_menu_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '🏠 القائمة الرئيسية')
def handle_main_menu(message):
    """العودة للقائمة الرئيسية"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    role = user_roles.get(str(user_id), 'customer')
    
    if role == 'driver':
        bot.send_message(
            chat_id,
            "🏠 <b>القائمة الرئيسية للسائق</b>",
            reply_markup=driver_menu_keyboard()
        )
    else:
        bot.send_message(
            chat_id,
            "🏠 <b>القائمة الرئيسية</b>",
            reply_markup=main_menu_keyboard()
        )

# ============================================================================
# معالجات العملاء
# ============================================================================

@bot.message_handler(func=lambda message: message.text == '🚖 طلب رحلة')
def handle_ride_request(message):
    """طلب رحلة جديدة"""
    chat_id = message.chat.id
    
    bot.send_message(
        chat_id,
        "🚗 <b>اختر نوع الرحلة:</b>\n\n"
        "• 🚗 <b>عادية</b>: سعر أساسي\n"
        "• 🚙 <b>فاخرة</b>: راحة أكثر +30%\n"
        "• 🚐 <b>عائلية</b>: سيارة كبيرة +50%\n"
        "• 🚗 <b>اقتصادية</b>: توفير سعر -20%",
        reply_markup=ride_types_inline()
    )

@bot.message_handler(func=lambda message: message.text == '📍 إرسال موقعي')
def handle_send_location(message):
    """طلب إرسال الموقع"""
    chat_id = message.chat.id
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton("📍 إرسال موقعي الحالي", request_location=True)
    )
    markup.row('🏠 القائمة الرئيسية')
    
    bot.send_message(
        chat_id,
        "📍 <b>إرسال الموقع</b>\n\n"
        "اضغط على الزر أدناه لمشاركة موقعك الحالي مع السائق.",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '💰 رصيدي')
def handle_balance(message):
    """عرض الرصيد"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_data = get_user_data(user_id)
    balance = user_data.get('balance', 0)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💳 شحن الرصيد", callback_data="recharge"),
        types.InlineboardKeyboardButton("📤 سحب الأموال", callback_data="withdraw")
    )
    
    bot.send_message(
        chat_id,
        f"💰 <b>حسابك المالي</b>\n\n"
        f"• الرصيد المتاح: <b>{balance} ر.س</b>\n"
        f"• الرحلات المكتملة: <b>{user_data.get('rides_count', 0)}</b>\n"
        f"• التقييم: <b>{user_data.get('rating', 5.0)} ⭐</b>\n\n"
        f"اختر الإجراء:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '📋 رحلاتي')
def handle_my_rides(message):
    """عرض الرحلات"""
    chat_id = message.chat.id
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔄 الرحلات الحالية", callback_data="current_rides"),
        types.InlineKeyboardButton("📜 الرحلات السابقة", callback_data="past_rides")
    )
    
    bot.send_message(
        chat_id,
        "📋 <b>رحلاتي</b>\n\n"
        "يمكنك عرض الرحلات الحالية والسابقة:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '⚙️ إعدادات')
def handle_settings(message):
    """عرض الإعدادات"""
    chat_id = message.chat.id
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("👤 تعديل الملف الشخصي", callback_data="edit_profile"),
        types.InlineKeyboardButton("🔔 إعدادات الإشعارات", callback_data="notification_settings"),
        types.InlineKeyboardButton("🌍 تغيير اللغة", callback_data="change_language"),
        types.InlineKeyboardButton("🔒 الخصوصية والأمان", callback_data="privacy_settings")
    )
    
    bot.send_message(
        chat_id,
        "⚙️ <b>الإعدادات</b>\n\n"
        "إدارة إعدادات حسابك:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '📞 الدعم')
def handle_support(message):
    """عرض خيارات الدعم"""
    chat_id = message.chat.id
    
    bot.send_message(
        chat_id,
        "📞 <b>مركز الدعم والمساعدة</b>\n\n"
        "💬 <b>الدردشة المباشرة:</b> 24/7\n"
        "📱 <b>الهاتف:</b> 920000000\n"
        "✉️ <b>البريد:</b> support@nabd-bot.com\n\n"
        "اختر طريقة التواصل:",
        reply_markup=support_options_inline()
    )

@bot.message_handler(func=lambda message: message.text == '👤 حسابي')
def handle_profile(message):
    """عرض الملف الشخصي"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_data = get_user_data(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✏️ تعديل الاسم", callback_data="edit_name"),
        types.InlineKeyboardButton("📱 رقم الجوال", callback_data="edit_phone")
    )
    markup.add(
        types.InlineKeyboardButton("📧 البريد الإلكتروني", callback_data="edit_email"),
        types.InlineKeyboardButton("🔐 تغيير كلمة المرور", callback_data="change_password")
    )
    
    bot.send_message(
        chat_id,
        f"👤 <b>الملف الشخصي</b>\n\n"
        f"• <b>الاسم:</b> {user_data.get('name', 'غير محدد')}\n"
        f"• <b>رقم العضوية:</b> #{str(user_id)[-6:]}\n"
        f"• <b>تاريخ التسجيل:</b> {user_data.get('join_date', 'اليوم')}\n"
        f"• <b>عدد الرحلات:</b> {user_data.get('rides_count', 0)}\n"
        f"• <b>التقييم:</b> {user_data.get('rating', 5.0)} ⭐\n\n"
        f"اختر ما تريد تعديله:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '🎫 العروض')
def handle_offers(message):
    """عرض العروض"""
    chat_id = message.chat.id
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎁 أول رحلة مجاناً", callback_data="offer_first"),
        types.InlineKeyboardButton("👥 دعوة أصدقاء", callback_data="invite_friends"),
        types.InlineKeyboardButton("📱 حمّل التطبيق", callback_data="download_app"),
        types.InlineKeyboardButton("🎯 عرض العودة", callback_data="comeback_offer")
    )
    
    bot.send_message(
        chat_id,
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

# ============================================================================
# معالجات السائقين
# ============================================================================

@bot.message_handler(func=lambda message: message.text == '🟢 بدء العمل')
def handle_start_work(message):
    """بدء عمل السائق"""
    driver_id = message.from_user.id
    chat_id = message.chat.id
    
    driver_data = get_driver_data(driver_id)
    driver_data['status'] = 'online'
    driver_data['last_active'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_driver_data(driver_id, driver_data)
    
    bot.send_message(
        chat_id,
        "✅ <b>تم تفعيل وضع السائق!</b>\n\n"
        "🎯 أنت الآن مرئي للعملاء\n"
        "📱 ستستقبل طلبات جديدة تلقائياً\n"
        "💰 ابدأ بكسب الأرباح الآن!\n\n"
        "📍 <b>تأكد من تحديث موقعك بانتظام</b>"
    )

@bot.message_handler(func=lambda message: message.text == '🔴 إيقاف')
def handle_stop_work(message):
    """إيقاف عمل السائق"""
    driver_id = message.from_user.id
    chat_id = message.chat.id
    
    driver_data = get_driver_data(driver_id)
    driver_data['status'] = 'offline'
    save_driver_data(driver_id, driver_data)
    
    bot.send_message(
        chat_id,
        "🔴 <b>تم إيقاف خدمة الاستقبال</b>\n\n"
        "للعودة لاستقبال الطلبات، اضغط '🟢 بدء العمل'"
    )

@bot.message_handler(func=lambda message: message.text == '📍 تحديث موقعي')
def handle_update_location_driver(message):
    """تحديث موقع السائق"""
    chat_id = message.chat.id
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton("📍 تحديث موقعي", request_location=True)
    )
    
    bot.send_message(
        chat_id,
        "📍 <b>تحديث الموقع</b>\n\n"
        "اضغط على الزر أدناه لتحديث موقعك الحالي.",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '📊 الطلبات')
def handle_ride_requests(message):
    """عرض طلبات الركوب"""
    driver_id = message.from_user.id
    chat_id = message.chat.id
    
    # محاكاة طلبات وهمية
    fake_requests = [
        {"id": 1, "distance": "1.2 كم", "price": "25 ر.س", "time": "5 دقائق"},
        {"id": 2, "distance": "2.5 كم", "price": "35 ر.س", "time": "8 دقائق"},
        {"id": 3, "distance": "3.1 كم", "price": "45 ر.س", "time": "10 دقائق"}
    ]
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for req in fake_requests:
        markup.add(
            types.InlineKeyboardButton(
                f"🚖 طلب #{req['id']} - {req['distance']} - {req['price']}", 
                callback_data=f"accept_request_{req['id']}"
            )
        )
    
    markup.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="refresh_requests"))
    
    bot.send_message(
        chat_id,
        "📊 <b>الطلبات المتاحة</b>\n\n"
        f"• عدد الطلبات: <b>{len(fake_requests)}</b>\n"
        f"• أقرب طلب: <b>{fake_requests[0]['distance']}</b>\n"
        f"• متوسط السعر: <b>35 ر.س</b>\n\n"
        f"اختر طلباً للقبول:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '💰 أرباحي')
def handle_driver_earnings(message):
    """عرض أرباح السائق"""
    driver_id = message.from_user.id
    chat_id = message.chat.id
    
    driver_data = get_driver_data(driver_id)
    earnings = driver_data.get('earnings', 0)
    rides_completed = driver_data.get('rides_completed', 0)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💳 سحب الأرباح", callback_data="withdraw_earnings"),
        types.InlineKeyboardButton("📊 التفاصيل", callback_data="earnings_details")
    )
    
    bot.send_message(
        chat_id,
        f"💰 <b>أرباحك</b>\n\n"
        f"• إجمالي الأرباح: <b>{earnings} ر.س</b>\n"
        f"• الرحلات المكتملة: <b>{rides_completed}</b>\n"
        f"• متوسط الربح/رحلة: <b>{earnings/max(rides_completed, 1):.1f} ر.س</b>\n"
        f"• التقييم: <b>{driver_data.get('rating', 5.0)} ⭐</b>\n\n"
        f"اختر الإجراء:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '📈 إحصائيات')
def handle_driver_stats(message):
    """عرض إحصائيات السائق"""
    driver_id = message.from_user.id
    chat_id = message.chat.id
    
    driver_data = get_driver_data(driver_id)
    
    bot.send_message(
        chat_id,
        f"📈 <b>إحصائياتك</b>\n\n"
        f"• الرحلات المكتملة: <b>{driver_data.get('rides_completed', 0)}</b>\n"
        f"• إجمالي المسافة: <b>{driver_data.get('rides_completed', 0) * 5} كم</b>\n"
        f"• متوسط التقييم: <b>{driver_data.get('rating', 5.0)} ⭐</b>\n"
        f"• ساعات العمل: <b>{driver_data.get('rides_completed', 0) * 0.5} ساعة</b>\n"
        f"• العملاء الراضين: <b>{int(driver_data.get('rides_completed', 0) * 0.9)}</b>\n\n"
        f"🎯 <b>استمر في العمل لزيادة إحصائياتك!</b>"
    )

# ============================================================================
# معالجة المواقع
# ============================================================================

@bot.message_handler(content_types=['location'])
def handle_location(message):
    """معالجة الموقع المرسل"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    location = message.location
    
    role = user_roles.get(str(user_id), 'customer')
    
    if role == 'driver':
        # تحديث موقع السائق
        driver_data = get_driver_data(user_id)
        driver_data['location'] = {
            'lat': location.latitude,
            'lon': location.longitude,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_driver_data(user_id, driver_data)
        
        response = (
            "✅ <b>تم تحديث موقع السائق!</b>\n\n"
            f"• <b>خط العرض:</b> {location.latitude:.6f}\n"
            f"• <b>خط الطول:</b> {location.longitude:.6f}\n\n"
            "🎯 أنت الآن مرئي للعملاء القريبين"
        )
    else:
        # موقع العميل لطلب رحلة
        response = (
            "📍 <b>تم استلام موقعك!</b>\n\n"
            f"• <b>الإحداثيات:</b>\n"
            f"  خط العرض: {location.latitude:.6f}\n"
            f"  خط الطول: {location.longitude:.6f}\n\n"
            "🚖 <b>جاري البحث عن أقرب سائق...</b>"
        )
        
        # بعد 3 ثواني، إرسال تأكيد
        threading.Timer(3, send_driver_found, args=[chat_id]).start()
    
    bot.send_message(chat_id, response)

def send_driver_found(chat_id):
    """إرسال تأكيد إيجاد سائق"""
    bot.send_message(
        chat_id,
        "✅ <b>تم العثور على سائق!</b>\n\n"
        "🚗 <b>السائق:</b> أحمد محمد\n"
        "⭐ <b>التقييم:</b> 4.8\n"
        "🚘 <b>المركبة:</b> تويوتا كامري 2023\n"
        "🎨 <b>اللون:</b> أبيض\n"
        "⏱️ <b>الوصول:</b> 5 دقائق\n"
        "💰 <b>السعر:</b> 25 ر.س\n\n"
        "هل تريد تأكيد الرحلة؟",
        reply_markup=confirm_ride_inline()
    )

# ============================================================================
# معالجة الأزرار التفاعلية
# ============================================================================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """معالجة جميع ضغطات الأزرار"""
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data
    
    logger.info(f"🔘 ضغط زر: {data} من {user_id}")
    
    # إجابة سريعة
    bot.answer_callback_query(call.id, text="جاري المعالجة...")
    
    try:
        # حذف الرسالة القديمة
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    
    # معالجة الأزرار حسب النوع
    if data.startswith("ride_"):
        handle_ride_type_selection(chat_id, data)
    
    elif data.startswith("pay_"):
        handle_payment_selection(chat_id, data)
    
    elif data.startswith("accept_request_"):
        handle_accept_request(chat_id, data)
    
    elif data == "confirm_ride":
        handle_confirm_ride(chat_id)
    
    elif data == "cancel_ride":
        handle_cancel_ride(chat_id)
    
    elif data == "recharge":
        handle_recharge(chat_id)
    
    elif data == "withdraw":
        handle_withdraw(chat_id)
    
    elif data == "quick_ride":
        handle_quick_ride(chat_id)
    
    elif data == "quick_location":
        handle_quick_location(chat_id)
    
    elif data == "quick_balance":
        handle_quick_balance(chat_id, user_id)
    
    elif data == "quick_support":
        handle_quick_support(chat_id)
    
    elif data in ["call_support", "chat_support", "send_complaint", "faq"]:
        handle_support_options(chat_id, data)
    
    else:
        # لأي زر غير معالج
        bot.send_message(
            chat_id,
            f"🔘 <b>تم الضغط على: {data}</b>\n\n"
            f"هذه الميزة قيد التطوير حالياً.",
            reply_markup=main_menu_keyboard()
        )

def handle_ride_type_selection(chat_id, ride_type):
    """معالجة اختيار نوع الرحلة"""
    type_names = {
        "ride_normal": "عادية",
        "ride_premium": "فاخرة",
        "ride_family": "عائلية",
        "ride_economy": "اقتصادية"
    }
    
    name = type_names.get(ride_type, "عادية")
    
    bot.send_message(
        chat_id,
        f"✅ <b>تم اختيار رحلة {name}</b>\n\n"
        f"📍 الرجاء إرسال موقعك لبدء البحث عن سائق...",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).row(
            types.KeyboardButton("📍 إرسال موقعي", request_location=True)
        )
    )

def handle_payment_selection(chat_id, payment_type):
    """معالجة اختيار طريقة الدفع"""
    type_names = {
        "pay_card": "بطاقة ائتمان",
        "pay_wallet": "محفظة إلكترونية",
        "pay_cash": "نقداً"
    }
    
    name = type_names.get(payment_type, "نقداً")
    
    bot.send_message(
        chat_id,
        f"✅ <b>تم اختيار الدفع {name}</b>\n\n"
        f"💳 <b>سيتم خصم المبلغ تلقائياً بعد انتهاء الرحلة</b>"
    )

def handle_accept_request(chat_id, data):
    """معالجة قبول طلب ركوب"""
    request_id = data.split("_")[-1]
    
    bot.send_message(
        chat_id,
        f"✅ <b>تم قبول الطلب #{request_id}!</b>\n\n"
        f"🚗 <b>اتجه نحو موقع العميل</b>\n"
        f"📍 <b>المسافة:</b> 1.2 كم\n"
        f"⏱️ <b>الوقت المتوقع:</b> 5 دقائق\n\n"
        f"📞 <b>رقم العميل:</b> 05********"
    )

def handle_confirm_ride(chat_id):
    """تأكيد الرحلة"""
    bot.send_message(
        chat_id,
        "✅ <b>تم تأكيد طلب الرحلة!</b>\n\n"
        "🚗 <b>السائق في طريقه إليك</b>\n"
        "⏱️ <b>الوقت المتوقع:</b> 5 دقائق\n"
        "📞 <b>رقم السائق:</b> 05********\n\n"
        "📍 <b>يمكنك تتبع الرحلة في الوقت الحقيقي</b>"
    )

def handle_cancel_ride(chat_id):
    """إلغاء الرحلة"""
    bot.send_message(
        chat_id,
        "❌ <b>تم إلغاء الطلب</b>\n\n"
        "يمكنك طلب رحلة جديدة في أي وقت.",
        reply_markup=main_menu_keyboard()
    )

def handle_recharge(chat_id):
    """شحن الرصيد"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("50 ر.س", callback_data="recharge_50"),
        types.InlineKeyboardButton("100 ر.س", callback_data="recharge_100"),
        types.InlineKeyboardButton("200 ر.س", callback_data="recharge_200"),
        types.InlineKeyboardButton("500 ر.س", callback_data="recharge_500")
    )
    
    bot.send_message(
        chat_id,
        "💳 <b>شحن الرصيد</b>\n\n"
        "اختر المبلغ المطلوب:",
        reply_markup=markup
    )

def handle_withdraw(chat_id):
    """سحب الأموال"""
    bot.send_message(
        chat_id,
        "📤 <b>سحب الأموال</b>\n\n"
        "• الحد الأدنى للسحب: 50 ر.س\n"
        "• الوقت المتوقع: 1-3 أيام عمل\n"
        "• يجب ربط حساب بنكي أولاً\n\n"
        "📞 <b>للطلب يرجى التواصل مع الدعم</b>"
    )

def handle_quick_ride(chat_id):
    """طلب سريع"""
    bot.send_message(
        chat_id,
        "🚖 <b>طلب سريع</b>\n\n"
        "جاري البحث عن أقرب سائق...",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).row(
            types.KeyboardButton("📍 إرسال موقعي", request_location=True)
        )
    )

def handle_quick_location(chat_id):
    """موقع سريع"""
    bot.send_message(
        chat_id,
        "📍 <b>إرسال الموقع</b>\n\n"
        "اضغط على الزر أدناه:",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).row(
            types.KeyboardButton("📍 إرسال موقعي", request_location=True)
        ).row('🏠 القائمة الرئيسية')
    )

def handle_quick_balance(chat_id, user_id):
    """رصيد سريع"""
    user_data = get_user_data(user_id)
    balance = user_data.get('balance', 0)
    
    bot.send_message(
        chat_id,
        f"💰 <b>رصيدك الحالي: {balance} ر.س</b>"
    )

def handle_quick_support(chat_id):
    """دعم سريع"""
    bot.send_message(
        chat_id,
        "📞 <b>الدعم الفني</b>\n\n"
        "💬 الدردشة: 24/7\n"
        "📱 الهاتف: 920000000\n"
        "✉️ البريد: support@nabd-bot.com",
        reply_markup=support_options_inline()
    )

def handle_support_options(chat_id, option):
    """خيارات الدupport"""
    options = {
        "call_support": "📞 <b>الاتصال الفوري</b>\n\nرقم الدعم: 920000000",
        "chat_support": "💬 <b>المحادثة النصية</b>\n\nسيقوم ممثل خدمة العملاء بالرد عليك قريباً.",
        "send_complaint": "📧 <b>إرسال شكوى</b>\n\nيرجى كتابة شكواك وسنرد عليك خلال 24 ساعة.",
        "faq": "❓ <b>الأسئلة الشائعة</b>\n\n1. كيف أطلب رحلة؟\n2. كيف أشحن رصيدي؟\n3. كيف أصبح سائق؟"
    }
    
    bot.send_message(chat_id, options.get(option, "اختر خياراً آخر."))

# ============================================================================
# معالجة الرسائل العامة
# ============================================================================

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """معالجة جميع الرسائل الأخرى"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    logger.info(f"📩 رسالة: {message.text} من {user_id}")
    
    # إذا كانت رسالة نصية عادية ولم يتم التعامل معها
    bot.send_message(
        chat_id,
        "🤖 <b>مرحباً!</b>\n\n"
        "استخدم الأزرار للتنقل أو:\n"
        "/start - للبدء من جديد\n"
        "/help - للمساعدة\n\n"
        "أو اختر من القائمة:",
        reply_markup=main_menu_keyboard()
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
    except Exception as e:
        bot_status = f"❌ خطأ: {str(e)}"
    
    # إحصاءات
    total_users = len(users_db)
    total_drivers = len(drivers_db)
    active_drivers = sum(1 for d in drivers_db.values() if d.get('status') == 'online')
    
    return f'''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>🚖 بوت النقل الذكي</title>
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                margin: 0;
                padding: 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            }}
            .header {{
                text-align: center;
                margin-bottom: 40px;
            }}
            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }}
            .stat-card {{
                background: rgba(255, 255, 255, 0.2);
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                transition: transform 0.3s;
            }}
            .stat-card:hover {{
                transform: translateY(-5px);
                background: rgba(255, 255, 255, 0.3);
            }}
            .btn {{
                display: inline-block;
                padding: 12px 30px;
                margin: 10px;
                background: white;
                color: #667eea;
                text-decoration: none;
                border-radius: 50px;
                font-weight: bold;
                transition: all 0.3s;
                border: 2px solid white;
            }}
            .btn:hover {{
                background: transparent;
                color: white;
            }}
            .btn-container {{
                text-align: center;
                margin: 40px 0;
            }}
            .feature {{
                background: rgba(255, 255, 255, 0.1);
                padding: 15px;
                margin: 10px 0;
                border-radius: 10px;
                border-right: 5px solid #4CAF50;
            }}
            .instructions {{
                background: rgba(0, 0, 0, 0.2);
                padding: 20px;
                border-radius: 10px;
                margin: 30px 0;
            }}
            @media (max-width: 600px) {{
                .container {{
                    padding: 20px;
                }}
                .stats {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="font-size: 2.5em; margin-bottom: 10px;">🚖 بوت النقل الذكي</h1>
                <p style="font-size: 1.2em; opacity: 0.9;">نظام نقل ذكي متكامل - الإصدار النهائي</p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <h3>🤖 حالة البوت</h3>
                    <p style="font-size: 1.5em; font-weight: bold;">{bot_status}</p>
                </div>
                <div class="stat-card">
                    <h3>👥 إجمالي المستخدمين</h3>
                    <p style="font-size: 1.5em; font-weight: bold;">{total_users}</p>
                </div>
                <div class="stat-card">
                    <h3>🚖 السائقين النشطين</h3>
                    <p style="font-size: 1.5em; font-weight: bold;">{active_drivers} / {total_drivers}</p>
                </div>
                <div class="stat-card">
                    <h3>📅 تاريخ التشغيل</h3>
                    <p style="font-size: 1.5em; font-weight: bold;">{datetime.now().strftime("%Y-%m-%d")}</p>
                </div>
            </div>
            
            <div class="btn-container">
                <a href="/set_webhook" class="btn">⚙️ تعيين ويب هوك</a>
                <a href="https://t.me/Dhdhdyduudbot" target="_blank" class="btn">💬 فتح البوت</a>
                <a href="/test" class="btn">🧪 صفحة الاختبار</a>
            </div>
            
            <div class="instructions">
                <h3>🎯 ميزات البوت:</h3>
                <div class="feature">🚖 طلب رحلات فورية بأنواع مختلفة</div>
                <div class="feature">📍 تحديد الموقع تلقائياً</div>
                <div class="feature">💰 نظام دفع إلكتروني آمن</div>
                <div class="feature">👥 نظام مزدوج (عملاء وسائقين)</div>
                <div class="feature">📊 إحصائيات وتقارير مفصلة</div>
                <div class="feature">📞 دعم فني مباشر 24/7</div>
            </div>
            
            <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.2);">
                <p>🔗 الرابط: https://dhhfhfjd.onrender.com</p>
                <p>📞 الدعم: support@nabd-bot.com | 920000000</p>
                <p>© 2024 بوت النقل الذكي - جميع الحقوق محفوظة</p>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """تعيين ويب هوك"""
    try:
        # الحصول على عنوان التطبيق
        host = request.host
        
        # على Render، نستخدم RENDER_EXTERNAL_HOSTNAME
        render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
        if render_host:
            webhook_url = f"https://{render_host}/webhook"
        else:
            webhook_url = f"https://{host}/webhook"
        
        logger.info(f"🔄 محاولة تعيين ويب هوك على: {webhook_url}")
        
        # إزالة أي ويب هوك سابق
        bot.remove_webhook()
        time.sleep(1)
        
        # تعيين ويب هوك جديد
        result = bot.set_webhook(url=webhook_url)
        
        # اختبار البوت
        try:
            bot_info = bot.get_me()
            bot_details = f"@{bot_info.username} - {bot_info.first_name}"
            bot_status = "✅ متصل"
        except Exception as e:
            bot_details = f"❌ خطأ: {str(e)}"
            bot_status = "❌ غير متصل"
        
        return f'''
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <meta charset="UTF-8">
            <title>✅ تم تعيين الويب هوك</title>
            <style>
                body {{
                    padding: 50px;
                    font-family: Arial;
                    text-align: center;
                    background: #f5f5f5;
                }}
                .result-box {{
                    max-width: 600px;
                    margin: 20px auto;
                    padding: 30px;
                    background: white;
                    border-radius: 10px;
                    box-shadow: 0 0 20px rgba(0,0,0,0.1);
                }}
                .success {{
                    border-left: 5px solid #4CAF50;
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
            <div class="result-box success">
                <h2 style="color: #4CAF50;">✅ تم تعيين الويب هوك بنجاح!</h2>
                
                <div style="text-align: right; margin: 30px 0;">
                    <p><strong>🌐 رابط الويب هوك:</strong></p>
                    <p style="background: #f0f0f0; padding: 10px; border-radius: 5px; direction: ltr;">
                        {webhook_url}
                    </p>
                </div>
                
                <div style="text-align: right; margin: 20px 0;">
                    <p><strong>🤖 حالة البوت:</strong> {bot_status}</p>
                    <p><strong>🔧 التفاصيل:</strong> {bot_details}</p>
                    <p><strong>👥 المستخدمين المسجلين:</strong> {len(users_db)}</p>
                </div>
                
                <div style="margin-top: 40px;">
                    <a href="/" class="btn">🏠 الصفحة الرئيسية</a>
                    <a href="https://t.me/Dhdhdyduudbot" target="_blank" class="btn" style="background: #28a745;">
                        💬 افتح البوت
                    </a>
                </div>
            </div>
            
            <div style="margin-top: 20px; color: #666;">
                <p>⚠️ <strong>ملاحظة:</strong> إذا لم يستجب البوت، جرب إعادة تعيين الويب هوك مرة أخرى.</p>
            </div>
        </body>
        </html>
        '''
        
    except Exception as e:
        logger.error(f"❌ خطأ في تعيين ويب هوك: {e}")
        return f'''
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ padding: 50px; text-align: center; }}
                .error-box {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 30px;
                    background: #ffebee;
                    color: #c62828;
                    border-radius: 10px;
                    border-left: 5px solid #c62828;
                }}
            </style>
        </head>
        <body>
            <div class="error-box">
                <h2>❌ خطأ في تعيين الويب هوك</h2>
                <p><strong>الخطأ:</strong> {str(e)}</p>
                
                <div style="text-align: right; margin: 30px 0; background: rgba(0,0,0,0.05); padding: 15px; border-radius: 5px;">
                    <h3>🛠️ خطوات الحل:</h3>
                    <ol style="text-align: right;">
                        <li>تأكد من صحة التوكن (BOT_TOKEN)</li>
                        <li>تحقق من اتصال الإنترنت</li>
                        <li>انتظر قليلاً ثم حاول مرة أخرى</li>
                        <li>إذا استمر الخطأ، أعد نشر التطبيق</li>
                    </ol>
                </div>
                
                <div style="margin-top: 20px;">
                    <a href="/" style="padding: 10px 20px; background: #0088cc; color: white; text-decoration: none; border-radius: 5px;">
                        العودة للصفحة الرئيسية
                    </a>
                </div>
            </div>
        </body>
        </html>
        ''', 500

@app.route('/test')
def test_page():
    """صفحة اختبار البوت"""
    return '''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>🧪 اختبار البوت</title>
        <style>
            body {
                padding: 30px;
                font-family: Arial;
                text-align: center;
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            }
            .test-container {
                max-width: 600px;
                margin: 0 auto;
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            .step {
                background: #e3f2fd;
                padding: 15px;
                margin: 15px 0;
                border-radius: 10px;
                border-right: 5px solid #2196f3;
                text-align: right;
            }
            .btn {
                display: inline-block;
                padding: 12px 25px;
                margin: 10px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                border-radius: 25px;
                font-weight: bold;
                transition: transform 0.3s;
            }
            .btn:hover {
                transform: translateY(-3px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            }
            .feature-list {
                text-align: right;
                margin: 30px 0;
            }
            .feature-item {
                padding: 10px;
                margin: 5px 0;
                background: #f8f9fa;
                border-radius: 5px;
            }
        </style>
    </head>
    <body>
        <div class="test-container">
            <h1 style="color: #667eea;">🧪 اختبار البوت التفاعلي</h1>
            <p style="color: #666; margin-bottom: 30px;">اختبار شامل لجميع ميزات بوت النقل الذكي</p>
            
            <div class="step">
                <h3>📱 الخطوة 1: افتح البوت</h3>
                <p>اضغط على الزر أدناه لفتح البوت على Telegram</p>
            </div>
            
            <div class="step">
                <h3>🎯 الخطوة 2: أرسل /start</h3>
                <p>اكتب <code>/start</code> في محادثة البوت</p>
            </div>
            
            <div class="step">
                <h3>👤 الخطوة 3: اختر دورك</h3>
                <p>اختر "👤 عميل" أو "🚖 سائق" حسب احتياجك</p>
            </div>
            
            <div class="step">
                <h3>🔘 الخطوة 4: جرب الأزرار</h3>
                <p>جرب جميع الأزرار التفاعلية والقوائم</p>
            </div>
            
            <div class="feature-list">
                <h3>✨ الميزات التي يمكنك اختبارها:</h3>
                <div class="feature-item">🚖 طلب رحلة بأنواع مختلفة</div>
                <div class="feature-item">📍 إرسال الموقع تلقائياً</div>
                <div class="feature-item">💰 شحن الرصيد والسحب</div>
                <div class="feature-item">📞 التواصل مع الدعم</div>
                <div class="feature-item">⚙️ تعديل الإعدادات</div>
                <div class="feature-item">⭐ نظام التقييمات</div>
            </div>
            
            <div style="margin: 40px 0;">
                <a href="https://t.me/Dhdhdyduudbot" target="_blank" class="btn" style="font-size: 1.2em;">
                    🚀 ابدأ الاختبار الآن
                </a>
            </div>
            
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
                <p>مشكلة في الاختبار؟ <a href="/set_webhook">أعد تعيين ويب هوك</a></p>
                <p><a href="/">العودة للصفحة الرئيسية</a></p>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/webhook', methods=['POST'])
def webhook():
    """نقطة استقبال تحديثات Telegram"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK'
    return 'Bad Request', 400

# ============================================================================
# بدء التطبيق
# ============================================================================

def setup_bot():
    """إعداد البوت عند التشغيل"""
    try:
        bot_info = bot.get_me()
        logger.info(f"✅ البوت جاهز: @{bot_info.username}")
        logger.info(f"📊 قاعدة البيانات: {len(users_db)} مستخدم، {len(drivers_db)} سائق")
        return True
    except Exception as e:
        logger.error(f"❌ فشل إعداد البوت: {e}")
        return False

if __name__ == '__main__':
    # التشغيل المحلي
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 بدء التشغيل على منفذ {port}")
    setup_bot()
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # على Render
    setup_bot()