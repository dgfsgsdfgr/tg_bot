"""
Telegram-бот для напоминаний о приёме воды и витаминов
Переработанная версия с APScheduler и SQLite
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from datetime import datetime
import pytz
import random
import asyncio

from models import Database
from repository import UserRepository, ProfileRepository, ReminderTimeRepository
from scheduler_service import ReminderScheduler, MOTIVATIONAL_MESSAGES

# Конфигурация
BOT_TOKEN = "8419802170:AAFgmn5fMDr8FODBI8QEs5AGuauoZEbIohA"
BOT_TOKENMoe = "8331119281:AAGqHdISGtFkGVlt9LF0vuMFYkQOY8ZnTbg"
BOT_TOKENnastya = "8419802170:AAFgmn5fMDr8FODBI8QEs5AGuauoZEbIohA"
DATABASE_URL = "sqlite:///bot_data.db"

# Глобальные объекты
database = Database(DATABASE_URL)
scheduler = None


def get_main_menu_keyboard():
    """Главное меню бота"""
    keyboard = [
        [KeyboardButton("📋 Меню"), KeyboardButton("📖 Инструкция")],
        [KeyboardButton("👥 Профили"), KeyboardButton("⚙️ Настройки")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    if not update.effective_user or not update.message:
        return

    user_id = str(update.effective_user.id)
    
    session = database.get_session()
    try:
        UserRepository.get_or_create(session, user_id)
    finally:
        session.close()

    welcome_text = (
        "👋 Привет! Я бот-помощник для напоминаний о приёме воды и витаминов!\n\n"
        "Я помогу тебе:\n"
        "💧 Не забывать пить воду\n"
        "💊 Вовремя принимать витамины\n"
        "👨‍👩‍👧‍👦 Заботиться о здоровье всей семьи\n\n"
        "Используй меню ниже для управления ботом!\n"
        "Начни с создания профиля - нажми '👥 Профили'"
    )

    await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard())


async def debug_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /debug - информация о напоминаниях"""
    if not update.effective_user or not update.message:
        return

    user_id = str(update.effective_user.id)
    
    session = database.get_session()
    try:
        user = UserRepository.get(session, user_id)
        if not user:
            await update.message.reply_text("Пользователь не найден в базе данных")
            return

        debug_text = f"🔧 ОТЛАДОЧНАЯ ИНФОРМАЦИЯ\n\n"
        debug_text += f"User ID: {user_id}\n"
        debug_text += f"Часовой пояс: {user.timezone}\n"
        debug_text += f"Текущее время: {datetime.now(pytz.timezone(user.timezone)).strftime('%H:%M:%S')}\n\n"

        if user.active_profile:
            profile = user.active_profile
            debug_text += f"Активный профиль: {profile.name}\n"
            debug_text += f"Типы напоминаний: {', '.join(profile.reminder_types) or 'не выбраны'}\n"
            debug_text += f"Время: {', '.join(profile.time_strings) or 'не установлено'}\n\n"

            jobs_count = scheduler.get_jobs_count(user_id)
            debug_text += f"Активных задач: {jobs_count}\n"
        else:
            debug_text += "❌ Нет активного профиля\n"

        debug_text += f"\nВсего задач в планировщике: {scheduler.get_jobs_count()}"

        await update.message.reply_text(debug_text)
    finally:
        session.close()


async def show_instruction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать инструкцию"""
    if not update.message:
        return

    instruction = (
        "📖 ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ БОТА\n\n"
        "1️⃣ Создание профиля:\n"
        "   • Нажми '👥 Профили'\n"
        "   • Выбери '+ Добавить профиль'\n"
        "   • Введи имя (например: 'Мама', 'Ребёнок')\n\n"
        "2️⃣ Настройка напоминаний:\n"
        "   • Выбери профиль\n"
        "   • Настрой тип напоминаний (вода/витамины/оба)\n"
        "   • Установи время напоминаний\n\n"
        "3️⃣ Часовой пояс:\n"
        "   • Зайди в '⚙️ Настройки'\n"
        "   • Выбери свой часовой пояс\n\n"
        "4️⃣ Управление:\n"
        "   • Меню - основные функции\n"
        "   • Профили - управление профилями\n"
        "   • Настройки - настройки бота\n\n"
        "💡 Совет: Создай отдельные профили для каждого члена семьи!"
    )

    await update.message.reply_text(instruction, reply_markup=get_main_menu_keyboard())


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать главное меню"""
    if not update.effective_user or not update.message:
        return

    user_id = str(update.effective_user.id)
    
    session = database.get_session()
    try:
        user = UserRepository.get(session, user_id)
        
        if user and user.active_profile:
            profile_text = f"✅ Активный профиль: {user.active_profile.name}"
            status = "✅ Включены"
        else:
            profile_text = "❌ Нет активного профиля"
            status = "❌ Выключены"

        menu_text = (
            f"📋 ГЛАВНОЕ МЕНЮ\n\n"
            f"{profile_text}\n\n"
            f"Доступные команды:\n"
            f"👥 Профили - управление профилями\n"
            f"⚙️ Настройки - настройки бота\n"
            f"📖 Инструкция - как пользоваться\n\n"
            f"Статус напоминаний: {status}"
        )

        await update.message.reply_text(menu_text, reply_markup=get_main_menu_keyboard())
    finally:
        session.close()


async def show_profiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список профилей"""
    if not update.effective_user:
        return

    user_id = str(update.effective_user.id)
    
    session = database.get_session()
    try:
        user = UserRepository.get(session, user_id)
        profiles = ProfileRepository.get_by_user(session, user_id)

        keyboard = []

        if profiles:
            for profile in profiles:
                emoji = "✅" if user and user.active_profile_id == profile.id else "⚪"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{emoji} {profile.name}",
                        callback_data=f"profile_select_{profile.id}"
                    )
                ])

        keyboard.append([
            InlineKeyboardButton("➕ Добавить профиль", callback_data="profile_add")
        ])
        keyboard.append([
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")
        ])

        text = "👥 ПРОФИЛИ\n\n"
        if profiles:
            text += "Выбери профиль для настройки или создай новый:"
        else:
            text += "У тебя пока нет профилей. Создай первый профиль!"

        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        elif update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
    finally:
        session.close()


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать настройки"""
    if not update.effective_user:
        return

    user_id = str(update.effective_user.id)
    
    session = database.get_session()
    try:
        user = UserRepository.get_or_create(session, user_id)
        current_tz = user.timezone

        keyboard = [
            [InlineKeyboardButton("🌍 Изменить часовой пояс", callback_data="settings_timezone")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]
        ]

        text = (
            f"⚙️ НАСТРОЙКИ\n\n"
            f"Текущий часовой пояс: {current_tz}\n"
            f"Время бота: {datetime.now(pytz.timezone(current_tz)).strftime('%H:%M')}"
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        elif update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
    finally:
        session.close()


async def show_timezone_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор часового пояса"""
    if not update.callback_query:
        return

    timezones = [
        ("🇷🇺 Москва (МСК)", "Europe/Moscow"),
        ("🇷🇺 Екатеринбург (YEKT)", "Asia/Yekaterinburg"),
        ("🇷🇺 Новосибирск (NOVT)", "Asia/Novosibirsk"),
        ("🇷🇺 Владивосток (VLAT)", "Asia/Vladivostok"),
        ("🇺🇦 Киев", "Europe/Kiev"),
        ("🇰🇿 Алматы", "Asia/Almaty"),
        ("🇧🇾 Минск", "Europe/Minsk"),
    ]

    keyboard = []
    for name, tz in timezones:
        keyboard.append([InlineKeyboardButton(name, callback_data=f"tz_set_{tz}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="settings")])

    await update.callback_query.edit_message_text(
        "🌍 ВЫБОР ЧАСОВОГО ПОЯСА\n\nВыбери свой часовой пояс:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_profile_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, profile_id: int):
    """Настройки конкретного профиля"""
    if not update.callback_query or not update.effective_user:
        return

    user_id = str(update.effective_user.id)
    
    session = database.get_session()
    try:
        user = UserRepository.get(session, user_id)
        profile = ProfileRepository.get(session, profile_id)
        
        if not profile:
            await update.callback_query.answer("❌ Профиль не найден!")
            return

        reminder_types = profile.reminder_types
        water = "✅" if "water" in reminder_types else "⬜"
        vitamins = "✅" if "vitamins" in reminder_types else "⬜"

        times = profile.time_strings
        times_text = ", ".join(times) if times else "не установлено"

        is_active = user and user.active_profile_id == profile_id
        activate_text = "✅ Профиль активен" if is_active else "🔘 Активировать профиль"

        keyboard = [
            [
                InlineKeyboardButton(f"{water} Вода", callback_data=f"toggle_water_{profile_id}"),
                InlineKeyboardButton(f"{vitamins} Витамины", callback_data=f"toggle_vitamins_{profile_id}")
            ],
            [InlineKeyboardButton("⏰ Настроить время", callback_data=f"set_times_{profile_id}")],
            [InlineKeyboardButton("🧪 Тестовое напоминание", callback_data=f"test_{profile_id}")],
            [InlineKeyboardButton(activate_text, callback_data=f"activate_{profile_id}")],
            [InlineKeyboardButton("🗑️ Удалить профиль", callback_data=f"delete_confirm_{profile_id}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="profiles")]
        ]

        text = (
            f"⚙️ НАСТРОЙКИ ПРОФИЛЯ: {profile.name}\n\n"
            f"Типы напоминаний:\n"
            f"💧 Вода: {water}\n"
            f"💊 Витамины: {vitamins}\n\n"
            f"⏰ Время напоминаний:\n{times_text}\n\n"
            f"Статус: {'✅ АКТИВЕН' if is_active else '⚪ не активен'}"
        )

        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        session.close()


async def show_time_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, profile_id: int):
    """Показать выбор времени напоминаний"""
    if not update.callback_query or not update.effective_user:
        return

    user_id = str(update.effective_user.id)
    
    session = database.get_session()
    try:
        profile = ProfileRepository.get(session, profile_id)
        if not profile:
            await update.callback_query.answer("❌ Профиль не найден!")
            return

        current_times = profile.time_strings

        common_times = [
            "07:00", "08:00", "09:00", "10:00", "11:00", "12:00",
            "13:00", "14:00", "15:00", "16:00", "17:00", "18:00",
            "19:00", "20:00", "21:00", "22:00"
        ]

        keyboard = []
        row = []
        for i, t in enumerate(common_times):
            mark = "✅ " if t in current_times else ""
            row.append(
                InlineKeyboardButton(
                    f"{mark}{t}",
                    callback_data=f"time_toggle_{profile_id}_{t}"
                )
            )
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("⌨️ Ввести своё время", callback_data=f"time_custom_{profile_id}")])
        keyboard.append([InlineKeyboardButton("🗑️ Очистить все", callback_data=f"time_clear_{profile_id}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"profile_select_{profile_id}")])

        times_text = ", ".join(current_times) if current_times else "не выбрано"

        text = (
            f"⏰ НАСТРОЙКА ВРЕМЕНИ: {profile.name}\n\n"
            f"Текущее время напоминаний:\n{times_text}\n\n"
            f"Нажми на время, чтобы добавить/убрать:"
        )

        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        session.close()


async def send_test_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: str, profile_id: int):
    """Отправка тестового напоминания"""
    session = database.get_session()
    try:
        profile = ProfileRepository.get(session, profile_id)
        if not profile:
            await context.bot.send_message(chat_id=int(user_id), text="❌ Профиль не найден!")
            return

        reminder_types = profile.reminder_types
        if not reminder_types:
            await context.bot.send_message(
                chat_id=int(user_id),
                text="❌ Сначала выбери тип напоминаний (вода/витамины)!"
            )
            return

        reminder_type = reminder_types[0]
        motivation = random.choice(MOTIVATIONAL_MESSAGES)

        if reminder_type == "water":
            text = (
                f"🧪 ТЕСТОВОЕ НАПОМИНАНИЕ О ВОДЕ\n\n"
                f"Профиль: {profile.name}\n\n"
                f"✨ {motivation}\n\n"
                f"Время выпить стакан воды! 💧\n\n"
                f"(Это тестовое напоминание. Реальные напоминания придут в установленное время.)"
            )
        else:
            text = (
                f"🧪 ТЕСТОВОЕ НАПОМИНАНИЕ О ВИТАМИНАХ\n\n"
                f"Профиль: {profile.name}\n\n"
                f"✨ {motivation}\n\n"
                f"Не забудь принять витамины! 💊\n\n"
                f"(Это тестовое напоминание. Реальные напоминания придут в установленное время.)"
            )

        await context.bot.send_message(chat_id=int(user_id), text=text)
        print(f"✓ Тестовое напоминание отправлено пользователю {user_id}")
    except Exception as e:
        print(f"✗ Ошибка отправки тестового напоминания: {e}")
    finally:
        session.close()


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback-кнопок"""
    if not update.callback_query or not update.effective_user:
        return

    query = update.callback_query
    await query.answer()

    data = query.data
    if not data:
        return

    user_id = str(update.effective_user.id)
    
    session = database.get_session()
    try:
        UserRepository.get_or_create(session, user_id)

        if data == "back_to_menu":
            if query.message:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text="📋 Главное меню",
                    reply_markup=get_main_menu_keyboard()
                )

        elif data == "profiles":
            await show_profiles(update, context)

        elif data == "settings":
            await show_settings(update, context)

        elif data == "settings_timezone":
            await show_timezone_selection(update, context)

        elif data.startswith("tz_set_"):
            tz = data.replace("tz_set_", "")
            UserRepository.update_timezone(session, user_id, tz)
            scheduler.setup_user_reminders(user_id)
            await query.answer("✅ Часовой пояс изменён!")
            await show_settings(update, context)

        elif data == "profile_add":
            context.user_data["awaiting"] = "profile_name"
            if query.message:
                await query.message.reply_text(
                    "➕ СОЗДАНИЕ ПРОФИЛЯ\n\nВведи имя профиля (например: 'Мама', 'Ребёнок', 'Папа'):"
                )

        elif data.startswith("profile_select_"):
            profile_id = int(data.replace("profile_select_", ""))
            await show_profile_settings(update, context, profile_id)

        elif data.startswith("toggle_water_"):
            profile_id = int(data.replace("toggle_water_", ""))
            ProfileRepository.toggle_water(session, profile_id)
            
            user = UserRepository.get(session, user_id)
            if user and user.active_profile_id == profile_id:
                scheduler.setup_user_reminders(user_id)
            
            await show_profile_settings(update, context, profile_id)

        elif data.startswith("toggle_vitamins_"):
            profile_id = int(data.replace("toggle_vitamins_", ""))
            ProfileRepository.toggle_vitamins(session, profile_id)
            
            user = UserRepository.get(session, user_id)
            if user and user.active_profile_id == profile_id:
                scheduler.setup_user_reminders(user_id)
            
            await show_profile_settings(update, context, profile_id)

        elif data.startswith("set_times_"):
            profile_id = int(data.replace("set_times_", ""))
            await show_time_selection(update, context, profile_id)

        elif data.startswith("time_toggle_"):
            parts = data.replace("time_toggle_", "").rsplit("_", 1)
            profile_id = int(parts[0])
            time_value = parts[1]

            ReminderTimeRepository.toggle_time(session, profile_id, time_value)
            
            user = UserRepository.get(session, user_id)
            if user and user.active_profile_id == profile_id:
                scheduler.setup_user_reminders(user_id)
            
            await show_time_selection(update, context, profile_id)

        elif data.startswith("time_clear_"):
            profile_id = int(data.replace("time_clear_", ""))
            ReminderTimeRepository.clear_profile_times(session, profile_id)
            
            user = UserRepository.get(session, user_id)
            if user and user.active_profile_id == profile_id:
                scheduler.remove_user_reminders(user_id)
            
            await show_time_selection(update, context, profile_id)

        elif data.startswith("time_custom_"):
            profile_id = int(data.replace("time_custom_", ""))
            context.user_data["awaiting"] = f"custom_time_{profile_id}"
            if query.message:
                await query.message.reply_text("⌨️ Введи время в формате ЧЧ:ММ (например: 14:30):")

        elif data.startswith("test_"):
            profile_id = int(data.replace("test_", ""))
            await send_test_reminder(context, user_id, profile_id)

        elif data.startswith("activate_"):
            profile_id = int(data.replace("activate_", ""))
            UserRepository.set_active_profile(session, user_id, profile_id)
            scheduler.setup_user_reminders(user_id)
            
            profile = ProfileRepository.get(session, profile_id)
            await query.answer(f"✅ Профиль '{profile.name}' активирован!")
            await show_profile_settings(update, context, profile_id)

        elif data.startswith("delete_confirm_"):
            profile_id = int(data.replace("delete_confirm_", ""))
            profile = ProfileRepository.get(session, profile_id)
            
            keyboard = [
                [InlineKeyboardButton("✅ Да, удалить", callback_data=f"delete_yes_{profile_id}")],
                [InlineKeyboardButton("❌ Нет, отмена", callback_data=f"profile_select_{profile_id}")]
            ]

            await query.edit_message_text(
                f"⚠️ Удалить профиль '{profile.name}'?\n\nЭто действие нельзя отменить!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif data.startswith("delete_yes_"):
            profile_id = int(data.replace("delete_yes_", ""))
            profile = ProfileRepository.get(session, profile_id)
            profile_name = profile.name if profile else "неизвестный"

            user = UserRepository.get(session, user_id)
            if user and user.active_profile_id == profile_id:
                UserRepository.set_active_profile(session, user_id, None)
                scheduler.remove_user_reminders(user_id)

            ProfileRepository.delete(session, profile_id)
            await query.answer(f"🗑️ Профиль '{profile_name}' удалён!")
            await show_profiles(update, context)

    finally:
        session.close()


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    if not update.message or not update.effective_user:
        return

    text = update.message.text
    user_id = str(update.effective_user.id)

    if text in ["📋 Меню", "Меню"]:
        await show_menu(update, context)
    elif text in ["📖 Инструкция", "Инструкция"]:
        await show_instruction(update, context)
    elif text in ["👥 Профили", "Профили"]:
        await show_profiles(update, context)
    elif text in ["⚙️ Настройки", "Настройки"]:
        await show_settings(update, context)
    elif context.user_data.get("awaiting") == "profile_name":
        session = database.get_session()
        try:
            profile_name = text.strip()

            existing = ProfileRepository.get_by_name(session, user_id, profile_name)
            if existing:
                await update.message.reply_text(
                    f"❌ Профиль с именем '{profile_name}' уже существует. Выбери другое имя:"
                )
                return

            ProfileRepository.create(session, user_id, profile_name)
            context.user_data["awaiting"] = None

            await update.message.reply_text(
                f"✅ Профиль '{profile_name}' создан!\n\n"
                f"Теперь настрой его: выбери типы напоминаний и время.",
                reply_markup=get_main_menu_keyboard()
            )

            await show_profiles(update, context)
        finally:
            session.close()

    elif context.user_data.get("awaiting", "").startswith("custom_time_"):
        profile_id = int(context.user_data["awaiting"].replace("custom_time_", ""))

        try:
            parts = text.strip().split(":")
            if len(parts) != 2:
                raise ValueError("Invalid format")
            hour = int(parts[0])
            minute = int(parts[1])
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("Invalid time")

            time_value = f"{hour:02d}:{minute:02d}"

            session = database.get_session()
            try:
                ReminderTimeRepository.add_to_profile(session, profile_id, time_value)
                
                user = UserRepository.get(session, user_id)
                if user and user.active_profile_id == profile_id:
                    scheduler.setup_user_reminders(user_id)

                context.user_data["awaiting"] = None
                await update.message.reply_text(
                    f"✅ Время {time_value} добавлено!",
                    reply_markup=get_main_menu_keyboard()
                )
            finally:
                session.close()

        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат. Введи время в формате ЧЧ:ММ (например: 14:30):"
            )
    else:
        await update.message.reply_text(
            "Используй кнопки меню для управления ботом!",
            reply_markup=get_main_menu_keyboard()
        )


async def post_init(application: Application):
    """Инициализация после запуска бота"""
    global scheduler
    scheduler = ReminderScheduler(application.bot, database)
    scheduler.start()
    print("✓ Планировщик инициализирован и запущен")


async def post_shutdown(application: Application):
    """Очистка ресурсов при остановке"""
    if scheduler:
        scheduler.shutdown()
    database.close()
    print("✓ Ресурсы освобождены")


def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        print("❌ Ошибка: не установлен токен бота!")
        return

    print("🚀 Запуск бота...")
    print(f"📊 База данных: {DATABASE_URL}")

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("debug", debug_info))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("✅ Бот запущен и готов к работе!")
    print("📝 Используй Ctrl+C для остановки")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()