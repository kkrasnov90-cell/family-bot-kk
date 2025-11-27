import sys
import os
from datetime import date, datetime 
import secrets
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters
# ✅ ИСПРАВЛЕНИЕ 1: Заменяем BackgroundScheduler на AsyncIOScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler 
from telegram.constants import ParseMode 

# 🎯 Добавляем корневую папку проекта в пути Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- ИМПОРТЫ МОДЕЛЕЙ И БАЗЫ ДАННЫХ (КРИТИЧЕСКИ ВАЖНО) ---
from database.connection import SessionLocal, engine
from database.models import Base, FamilyMember, FamilyEvent
from services.notification_service import NotificationService
from config import Config

# ----------------------------------------------------
# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
# ----------------------------------------------------

def pluralize_years(age):
    """Возвращает возраст с правильным склонением слова 'год/года/лет'."""
    if age is None:
        return ""
    
    # Специальный случай для чисел 11-14 (11, 12, 13, 14 лет)
    if 11 <= age % 100 <= 14:
        return f"{age} лет"

    # Общее правило, основанное на последней цифре
    last_digit = age % 10
    
    if last_digit == 1:
        return f"{age} год"  # 1, 21, 31 год
    elif 2 <= last_digit <= 4:
        return f"{age} года" # 2, 3, 4, 22, 23, 24 года
    else:
        return f"{age} лет" # 5-0 лет


# --- 🚀 ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---


# 1. ГАРАНТИРУЕМ СОЗДАНИЕ ТАБЛИЦ. 
Base.metadata.create_all(bind=engine) 

def seed_family():
    """Добавляет начальные данные, только если база ПУСТА."""
    db = SessionLocal()
    try:
        if db.query(FamilyMember).count() == 0:
            initial_members = [
                ("Кирилл Краснов", date(1990, 4, 11)),
            ]
            for name, bday in initial_members:
                db.add(FamilyMember(name=name, birth_date=bday))
            db.commit()
            print("✅ Семья добавлена в базу (инициализация).")
        else:
            print("ℹ️ Семья уже существует")
    finally:
        db.close()

seed_family()

# --- 🚀 КОНЕЦ ИНИЦИАЛИЗАЦИИ ---

class FamilyBot:
    def __init__(self):
        # Используем токен из Config для создания приложения
        self.application = Application.builder().token(Config.BOT_TOKEN).build()
        self.setup_handlers()

    # 🎯 ФУНКЦИЯ: Проверяет права администратора
    def is_admin_chat(self, chat_id):
        """Проверяет, совпадает ли chat_id с ADMIN_CHAT_ID из Config."""
        return str(chat_id) == str(Config.ADMIN_CHAT_ID)


    def setup_handlers(self):
        """Настраиваем обработчики команд"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("today", self.today))
        self.application.add_handler(CommandHandler("test_notify", self.test_notify))
        self.application.add_handler(CommandHandler("add_member", self.add_member))
        self.application.add_handler(CommandHandler("remove_member", self.remove_member))
        self.application.add_handler(CommandHandler("list", self.list_members))
        self.application.add_handler(CommandHandler("set_photo", self.set_photo_command))
        
        # 🎯 ПОСТОЯННАЯ АДМИН-КОМАНДА /file_id
        self.application.add_handler(CommandHandler("file_id", self.file_id_command))
        
        # Обработчик ответов на фото
        self.application.add_handler(MessageHandler(
            filters.PHOTO & filters.REPLY, self.handle_photo_reply
        ))

    async def set_commands(self, application): # Добавляем application как аргумент, хотя он не нужен
        """Устанавливает список команд в меню Telegram."""
        commands = [
            ("start", "👋 Приветствие и цели бота"),
            ("today", "📅 События на сегодня"),
            ("list", "👥 Показать всех членов семьи"),
            ("add_member", "➕ Добавить члена семьи (админ)"),
            ("remove_member", "🗑️ Удалить члена семьи (админ)"),
            ("set_photo", "📸 Инструкция: установить фото (админ)"),
            ("test_notify", "🔔 Проверить уведомления"),
            ("file_id", "🔑 Получить ID файла (админ)"), 
        ]
        
        # Вызываем метод Telegram API для установки команд
        await self.application.bot.set_my_commands(commands)
        print("✅ Меню команд Telegram успешно установлено.")


    # --- ХЕНДЛЕРЫ КОМАНД ---

    async def start(self, update, context):
        """
        Обработчик команды /start. 
        Отправляет красивое приветствие, цели и возможности бота (Вариант 1).
        """
        
        GREETING_PHOTO_ID = getattr(Config, 'GREETING_PHOTO_ID', None)
        
        # 🎯 НОВЫЙ ТЕКСТ (Вариант 1)
        message_text = (
            "**👋 С возвращением! Я Семейный Хранитель.**\n\n"
            
            "Моя задача — хранить в памяти всё, что важно для вашей семьи, и делиться этим с вами в нужный момент.\n\n"
            
            "**🌟 Как я работаю?**\n"
            "Я работаю автоматически и тихо, отправляя уведомления **каждый день в 9:00 UTC**:\n"
            "• **Дни рождения** 🎂\n"
            "• **Годовщины** 💍\n"
            "• **Важные события** 🗓️\n\n"
            
            "**⚙️ Управление**\n"
            "Все команды для управления членами семьи, событиями и фотографиями доступны в **Меню** (кнопка `/`)"
        )

        if GREETING_PHOTO_ID:
            await update.message.reply_photo(
                photo=GREETING_PHOTO_ID,
                caption=message_text,
                parse_mode=ParseMode.MARKDOWN 
            )
        else:
            await update.message.reply_text(
                message_text,
                parse_mode=ParseMode.MARKDOWN 
            )

    async def file_id_command(self, update, context):
        """Возвращает file_id медиафайла, на который была дана команда. (Только для админа)"""
        
        # 🛑 ПРОВЕРКА ПРАВ
        if not self.is_admin_chat(update.message.chat_id):
            return await update.message.reply_text(
                "❌ **Доступ запрещен!** Эта команда только для администратора.",
                parse_mode=ParseMode.MARKDOWN
            )

        replied_message = update.message.reply_to_message
        if not replied_message:
            return await update.message.reply_text(
                "❌ **Используйте команду как ответ на медиафайл** (фото, видео, документ), ID которого хотите получить.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        file_id = None
        file_type = None

        # Проверяем, какой тип медиафайла содержится в ответном сообщении
        if replied_message.photo:
            file_id = replied_message.photo[-1].file_id
            file_type = "Фотография"
        elif replied_message.document:
            file_id = replied_message.document.file_id
            file_type = "Документ"
        elif replied_message.video:
            file_id = replied_message.video.file_id
            file_type = "Видео"
        elif replied_message.audio:
            file_id = replied_message.audio.file_id
            file_type = "Аудио"

        # Отправка результата
        if file_id:
            message = (
                f"✅ **File ID для {file_type}**:\n"
                f"```\n{file_id}\n```"
            )
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            
            # Также печатаем в логах Railway для удобства копирования
            print(f"\n\n--- ⚠️ FILE ID ({file_type}): {file_id} ⚠️ ---\n\n")
        else:
            await update.message.reply_text(
                "❌ **Медиафайл не найден!** Пожалуйста, ответьте на фото, видео или документ.",
                parse_mode=ParseMode.MARKDOWN
            )


    async def set_photo_command(self, update, context):
        """Инструктирует пользователя, как установить фотографию."""
        await update.message.reply_text(
            "📸 Чтобы установить фотографию для члена семьи:\n\n"
            "1. Найдите сообщение, где вы <b>добавили</b> этого члена семьи (через <code>/add_member</code>).\n"
            "2. <b>Ответьте (Reply)</b> на это сообщение командой: <code>/set_photo Имя Фамилия</code>\n"
            "3. <b>Ответьте (Reply)</b> на вашу же команду <code>/set_photo...</code> <b>самой фотографией!</b>\n\n"
            "<i>Это сложно, но безопасно. Введите <code>/set_photo Имя Фамилия</code>, а затем ответьте на это сообщение фотографией.</i>",
            # 🎯 ИСПРАВЛЕНИЕ: Используем HTML вместо MARKDOWN
            parse_mode=ParseMode.HTML 
        )
    async def handle_photo_reply(self, update, context):
        """Обрабатывает фотографию, отправленную в ответ на команду /set_photo."""
        
        # 🛑 ПРОВЕРКА ПРАВ
        if not self.is_admin_chat(update.message.chat_id):
            return 
        # 🛑 КОНЕЦ ПРОВЕРКИ

        if not update.message.reply_to_message:
            return 

        original_message = update.message.reply_to_message.text
        if not original_message or not original_message.startswith('/set_photo'):
            return 

        args = original_message.split()[1:] 

        if len(args) < 2:
            return await update.message.reply_text(
                "❌ **Не удалось определить имя.** Используйте формат `/set_photo Имя Фамилия`",
                parse_mode=ParseMode.MARKDOWN
            )

        name_to_find = " ".join(args).strip()
        photo_file_id = update.message.photo[-1].file_id

        db = SessionLocal()
        try:
            member = db.query(FamilyMember).filter(
                FamilyMember.name == name_to_find
            ).first()

            if member:
                member.photo_file_id = photo_file_id
                db.commit()
                await update.message.reply_text(
                    f"📸 Фотография для **{member.name}** успешно сохранена и привязана!",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    f"❌ Член семьи с именем **{name_to_find}** не найден.",
                    parse_mode=ParseMode.MARKDOWN
                )

        except Exception as e:
            db.rollback()
            await update.message.reply_text(f"❌ Произошла ошибка при сохранении фото: {e}")
        finally:
            db.close()

    async def today(self, update, context):
        await self.send_today_events(update.message.chat_id)

    async def test_notify(self, update, context):
        await update.message.reply_text("🔔 Тестирую уведомления...")
        await self.send_today_events(update.message.chat_id)

    async def remove_member(self, update, context):
        """Удаляет члена семьи из базы данных по имени и фамилии."""
        # 🛑 ПРОВ
