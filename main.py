import os
import logging
from datetime import datetime, timezone, timedelta
from hijri_converter import Gregorian
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# إعداد السجلات
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# رمز إجبار الاتجاه من اليمين إلى اليسار (Right-to-Left Mark)
RLM = "\u200f"

# هيكل البيانات لكل مجموعة {chat_id: data}
chats_data = {}


def get_chat_data(chat_id: int):
    """جلب أو إنشاء بيانات مستقلة للمجموعة"""
    if chat_id not in chats_data:
        chats_data[chat_id] = {
            "is_registration_open": True,
            "session_type": "",
            "roles": {},       # {user_id: {"name": str, "username": str, ...}}
            "listeners": {},   # {user_id: {"name": str, "username": str}}
            "excused": {}      # {user_id: {"name": str, "username": str}}
        }
    return chats_data[chat_id]


def get_formatted_header(chat_id: int):
    """توليد ترويسة التاريخ والوقت بتوقيت مصر بتنسيق متوازن"""
    egypt_offset = timedelta(hours=3)  # توقيت مصر UTC+3
    now = datetime.now(timezone.utc) + egypt_offset
    hijri_date = Gregorian(now.year, now.month, now.day).to_hijri()

    gregorian_str = now.strftime("%Y / %m / %d")
    hijri_str = f"{hijri_date.year} / {hijri_date.month} / {hijri_date.day}"
    time_str = now.strftime("%I:%M %p")

    data = get_chat_data(chat_id)
    session_type = data["session_type"]
    session_line = f"     {session_type}\n" if session_type else ""

    header = (
        f"❖════════════════════❖\n"
        f" 🗓️ <b>التاريخ الميلادي :</b> {gregorian_str}\n"
        f" 🌙 <b>التاريخ الهجري :</b> {hijri_str}\n"
        f" ⏰ <b>الساعة (مصر) :</b> {time_str}\n"
        f"❖════════════════════❖\n"
        f"      <b>🌷 رضا الرحمن مبتغانا 🌷</b>\n"
        f"{session_line}"
        f"❖════════════════════❖\n"
    )
    return header


def generate_full_caption(chat_id: int):
    """بناء النص الكامل للقائمة الخاصة بالمجموعة"""
    c_data = get_chat_data(chat_id)
    caption = get_formatted_header(chat_id) + "\n"

    # 1. قسم أدوار الغاليات
    caption += f"{RLM}<b>🏷️ أدوار الغاليات :</b>\n"
    if c_data["roles"]:
        for idx, (u_id, data) in enumerate(c_data["roles"].items(), 1):
            user_text = f"<b>{data['name']}</b>"
            if data['username']:
                user_text += f" (@{data['username']})"

            line = f"{RLM}{idx}-🌷 {user_text}"
            if data.get('read'):
                line += " ✅️"
            if data.get('similar'):
                line += " ☑️"
            if data.get('meanings'):
                line += " ✔️"
            caption += f"{line}\n"
    else:
        caption += f"{RLM}لا يوجد أسماء بعد\n"

    # فاصل
    caption += f"\n{RLM}🔹️🔹️🔹️🔹️🔹️🔹️🔹️🔹️🔹️🔹️🔹️🔹️🔹️\n\n"

    # 2. قسم المستمعات
    caption += f"{RLM}<b>🏷️ المستمعات:</b>\n"
    if c_data["listeners"]:
        for idx, (u_id, data) in enumerate(c_data["listeners"].items(), 1):
            user_text = f"<b>{data['name']}</b>"
            if data['username']:
                user_text += f" (@{data['username']})"
            caption += f"{RLM}{idx}-🌸 {user_text}\n"
    else:
        caption += f"{RLM}لا يوجد أسماء بعد\n"

    # فاصل
    caption += f"\n{RLM}🔹️🔹️🔹️🔹️🔹️🔹️🔹️🔹️🔹️🔹️🔹️🔹️🔹️\n\n"

    # 3. قسم المعتذرات
    caption += f"{RLM}<b>🏷️ المعتذرات:</b>\n"
    if c_data["excused"]:
        for idx, (u_id, data) in enumerate(c_data["excused"].items(), 1):
            user_text = f"<b>{data['name']}</b>"
            if data['username']:
                user_text += f" (@{data['username']})"
            caption += f"{RLM}{idx}-🍂 {user_text}\n"
    else:
        caption += f"{RLM}لا يوجد أسماء بعد\n"

    # ختام القائمة
    caption += (
        "\n<b>كفارة المجلس</b>\n\n"
        "«سُبْحَانَكَ اللَّهُمَّ وَبِحَمْدِكَ، أَشْهَدُ أَنْ لَا إِلَهَ إِلَّا أَنْتَ، "
        "أَسْتَغْفِرُكَ وَأَتُوبُ إِلَيْكَ»"
    )

    return caption


def get_session_selection_keyboard():
    """توليد لوحة اختيار نوع الحلقة عند البدء"""
    keyboard = [
        [
            InlineKeyboardButton("حلقة تدبر", callback_data="set_session_tadabbur"),
            InlineKeyboardButton("حلقة سرد", callback_data="set_session_sard"),
        ],
        [
            InlineKeyboardButton("حلقة تصحيح تلاوة", callback_data="set_session_tashih"),
            InlineKeyboardButton("حلقة تجويد", callback_data="set_session_tajweed"),
        ],
        [
            InlineKeyboardButton("حلقة تكرار", callback_data="set_session_tikrar"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_keyboard(chat_id: int):
    """توليد الأزرار التفاعلية بناءً على حالة المجموعة"""
    c_data = get_chat_data(chat_id)
    keyboard = []

    if c_data["is_registration_open"]:
        keyboard.append([
            InlineKeyboardButton("🔘 سجل إسمي", callback_data="register_role"),
            InlineKeyboardButton("✅️ قرأت", callback_data="toggle_read"),
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("✅️ قرأت", callback_data="toggle_read"),
        ])

    keyboard.extend([
        [
            InlineKeyboardButton("☑️ متشابهات", callback_data="toggle_similar"),
            InlineKeyboardButton("✔️ معاني الكلمات", callback_data="toggle_meanings"),
        ],
        [
            InlineKeyboardButton("🎧 مستمعة", callback_data="register_listener"),
            InlineKeyboardButton("🚫 معتذرة", callback_data="register_excused"),
        ],
        [
            InlineKeyboardButton("❌️ أحذف إسمي", callback_data="delete_name"),
        ]
    ])

    return InlineKeyboardMarkup(keyboard)


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """التحقق مما إذا كان مستخدم الأمر أدمن في المجموعة"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if update.effective_chat.type == "private":
        return True

    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ["creator", "administrator"]


# --- الأوامر الثلاثة (للأدمن فقط) ---

async def startliste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⚠️ هذا الأمر مخصص لأدمن المجموعة فقط.")
        return

    chat_id = update.effective_chat.id
    c_data = get_chat_data(chat_id)
    
    c_data["is_registration_open"] = True
    c_data["roles"].clear()
    c_data["listeners"].clear()
    c_data["excused"].clear()

    await update.message.reply_text(
        "🌸 <b>الرجاء اختيار نوع الحلقة لإظهار القائمة:</b>",
        reply_markup=get_session_selection_keyboard(),
        parse_mode=ParseMode.HTML
    )


async def stopliste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⚠️ هذا الأمر مخصص لأدمن المجموعة فقط.")
        return

    chat_id = update.effective_chat.id
    c_data = get_chat_data(chat_id)
    c_data["is_registration_open"] = False

    await update.message.reply_text(
        generate_full_caption(chat_id),
        reply_markup=get_keyboard(chat_id),
        parse_mode=ParseMode.HTML
    )


async def deleteliste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⚠️ هذا الأمر مخصص لأدمن المجموعة فقط.")
        return

    chat_id = update.effective_chat.id
    c_data = get_chat_data(chat_id)
    
    c_data["roles"].clear()
    c_data["listeners"].clear()
    c_data["excused"].clear()
    c_data["session_type"] = ""
    c_data["is_registration_open"] = True

    await update.message.reply_text("🗑️ تم مسح كافة القوائم والأسماء بنجاح. يمكنك البدء بقائمة جديدة.")


# --- معالجة الضغط على الأزرار ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    user = query.from_user
    user_id = user.id
    full_name = user.first_name + (f" {user.last_name}" if user.last_name else "")
    username = user.username if user.username else ""
    data = query.data

    c_data = get_chat_data(chat_id)

    # --- خيارات تحديد نوع الحلقة للأدمن ---
    if data.startswith("set_session_"):
        if not await is_admin(update, context):
            await query.answer("⚠️ هذا الخيار مخصص للأدمن فقط!", show_alert=True)
            return

        sessions = {
            "set_session_tadabbur": "🔹️🔹️حلقة تدبر🔹️🔹️",
            "set_session_sard": "🔹️🔹️ حلقة سرد🔹️🔹️",
            "set_session_tashih": "🔹️🔹️حلقة تصحيح التلاوة 🔹️🔹️",
            "set_session_tajweed": "🔹️🔹️حلقة تجويد 🔹️🔹️",
            "set_session_tikrar": "🔹️🔹️حلقة تكرار 🔹️🔹️",
        }
        c_data["session_type"] = sessions.get(data, "")

        await query.edit_message_text(
            generate_full_caption(chat_id),
            reply_markup=get_keyboard(chat_id),
            parse_mode=ParseMode.HTML
        )
        return

    # --- باقي أزرار القائمة التفاعلية ---

    # 1. زر "سجل إسمي"
    if data == "register_role":
        if not c_data["is_registration_open"]:
            await query.answer("التسجيل مغلق حالياً!", show_alert=True)
            return
        c_data["listeners"].pop(user_id, None)
        c_data["excused"].pop(user_id, None)
        if user_id not in c_data["roles"]:
            c_data["roles"][user_id] = {
                "name": full_name,
                "username": username,
                "read": False,
                "similar": False,
                "meanings": False
            }

    # 2. زر "قرأت"
    elif data == "toggle_read":
        if user_id in c_data["roles"]:
            c_data["roles"][user_id]["read"] = not c_data["roles"][user_id]["read"]
        else:
            await query.answer("يجب أن تسجل اسمك أولاً عبر زر (سجل إسمي)!", show_alert=True)
            return

    # 3. زر "متشابهات"
    elif data == "toggle_similar":
        if user_id in c_data["roles"]:
            c_data["roles"][user_id]["similar"] = not c_data["roles"][user_id]["similar"]
        else:
            await query.answer("يجب أن تسجل اسمك أولاً عبر زر (سجل إسمي)!", show_alert=True)
            return

    # 4. زر "معاني الكلمات"
    elif data == "toggle_meanings":
        if user_id in c_data["roles"]:
            c_data["roles"][user_id]["meanings"] = not c_data["roles"][user_id].get("meanings", False)
        else:
            await query.answer("يجب أن تسجل اسمك أولاً عبر زر (سجل إسمي)!", show_alert=True)
            return

    # 5. زر "مستمعة"
    elif data == "register_listener":
        c_data["roles"].pop(user_id, None)
        c_data["excused"].pop(user_id, None)
        c_data["listeners"][user_id] = {"name": full_name, "username": username}

    # 6. زر "معتذرة"
    elif data == "register_excused":
        c_data["roles"].pop(user_id, None)
        c_data["listeners"].pop(user_id, None)
        c_data["excused"][user_id] = {"name": full_name, "username": username}

    # 7. زر "أحذف إسمي"
    elif data == "delete_name":
        c_data["roles"].pop(user_id, None)
        c_data["listeners"].pop(user_id, None)
        c_data["excused"].pop(user_id, None)

    # تحديث الرسالة الحالية
    await query.edit_message_text(
        generate_full_caption(chat_id),
        reply_markup=get_keyboard(chat_id),
        parse_mode=ParseMode.HTML
    )


def main():
    TOKEN = os.getenv("BOT_TOKEN")

    if not TOKEN:
        raise ValueError("خطأ: التوكن غير موجود! تأكد من إضافته في Railway تحت اسم BOT_TOKEN")

    app = Application.builder().token(TOKEN).build()

    # تسجيل الأوامر
    app.add_handler(CommandHandler("startliste", startliste))
    app.add_handler(CommandHandler("stopliste", stopliste))
    app.add_handler(CommandHandler("deleteliste", deleteliste))

    # تسجيل معالج الأزرار
    app.add_handler(CallbackQueryHandler(button_handler))

    # تشغيل البوت
    app.run_polling(allowed_updates=["message", "callback_query", "chat_member"])


if __name__ == "__main__":
    main()
