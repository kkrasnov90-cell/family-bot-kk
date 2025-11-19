import sys
import os

# 🎯 Добавляем корневую папку проекта в пути Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram.ext import Application, CommandHandler
from database.connection import SessionLocal
from database.models import FamilyMember
from services.notification_service import NotificationService
from config import Config
import asyncio


class FamilyBot:
    def __init__(self):
        self.application = Application.builder().token(Config.BOT_TOKEN).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Настраиваем обработчики команд"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("today", self.today))
        self.application.add_handler(CommandHandler("test_notify", self.test_notify))
        self.application.add_handler(CommandHandler("add_member", self.add_member))
        self.application.add_handler(CommandHandler("list", self.list_members))

    async def start(self, update, context):
        """Обработчик команды /start"""
        await update.message.reply_text(
            "👋 Привет! Я Family Bot KK!\n"
            "Я напоминаю о днях рождения и семейных событиях.\n\n"
            "📅 Команды:\n"
            "/today - события на сегодня\n"
            "/test_notify - тест уведомлений\n"
            "/list - список семьи\n"
            "/add_member - добавить члена семьи\n\n"
            "⚡ Автоматические уведомления в 9:00 каждый день!"
        )

    async def today(self, update, context):
        """Обработчик команды /today - события на сегодня"""
        await self.send_today_events(update.message.chat_id)

    async def test_notify(self, update, context):
        """Тестовая команда для проверки уведомлений"""
        await update.message.reply_text("🔔 Тестирую уведомления...")
        await self.send_today_events(update.message.chat_id)

    async def add_member(self, update, context):
        """Добавление нового члена семьи"""
        await update.message.reply_text(
            "👥 Добавление нового члена семьи\n\n"
            "Используйте формат:\n"
            "`/add_member Имя Фамилия ДД.ММ.ГГГГ`\n\n"
            "Пример:\n"
            "`/add_member Иван Сидоров 15.03.1990`"
        )

    async def list_members(self, update, context):
        """Показать всех членов семьи"""
        db = SessionLocal()
        try:
            service = NotificationService(db)
            members = db.query(FamilyMember).all()

            if not members:
                await update.message.reply_text("👥 В базе пока нет членов семьи")
                return

            message = "👥 Члены семьи:\n\n"
            for member in members:
                age = service.calculate_age(member.birth_date)
                message += f"• {member.name} - {member.birth_date.strftime('%d.%m.%Y')} ({age} лет)\n"

            await update.message.reply_text(message)

        except Exception as e:
            await update.message.reply_text("❌ Ошибка при получении данных")
        finally:
            db.close()

    async def send_today_events(self, chat_id):
        """Отправляет события на сегодня в указанный чат"""
        db = SessionLocal()
        try:
            service = NotificationService(db)
            birthdays, events = service.get_today_events()

            if not birthdays and not events:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text="📅 Сегодня нет знаменательных дат"
                )
                return

            # Отправляем дни рождения
            for member in birthdays:
                message = service.format_birthday_message(member)
                await self.application.bot.send_message(chat_id=chat_id, text=message)
                await asyncio.sleep(0.5)

            # Отправляем события
            for event in events:
                message = service.format_event_message(event)
                await self.application.bot.send_message(chat_id=chat_id, text=message)
                await asyncio.sleep(0.5)

        except Exception as e:
            await self.application.bot.send_message(
                chat_id=chat_id,
                text="❌ Ошибка при получении данных"
            )
        finally:
            db.close()

    def run(self):
        """Запускаем бота"""
        print("🤖 Бот запущен! Ожидаю команды...")
        print("📋 Доступные команды: /start, /today, /test_notify, /list, /add_member")
        self.application.run_polling()

# --- 🚀 ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (ШАГ 3) ---
from database.models import Base, FamilyMember
from database.connection import engine, SessionLocal

# Создаём таблицы
Base.metadata.create_all(bind=engine)

# Добавляем семью при первом запуске
def seed_family():
    db = SessionLocal()
    try:
        if db.query(FamilyMember).count() == 0:
            names = ["Кирилл", "Екатерина", "Ксения"]
            for name in names:
                db.add(FamilyMember(name=name))
            db.commit()
            print("✅ Семья добавлена в базу")
        else:
            print("ℹ️ Семья уже существует")
    finally:
        db.close()

seed_family()
# --- 🚀 КОНЕЦ ИНИЦИАЛИЗАЦИИ ---


if __name__ == "__main__":
    bot = FamilyBot()
    bot.run()
