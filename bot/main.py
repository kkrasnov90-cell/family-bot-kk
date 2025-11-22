import sys
import os
from datetime import date
import secrets

# 🎯 Добавляем корневую папку проекта в пути Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram.ext import Application, CommandHandler
from database.connection import SessionLocal, engine
from database.models import Base, FamilyMember
from services.notification_service import NotificationService
from config import Config
import asyncio

# --- 🚀 ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
Base.metadata.create_all(bind=engine)

def seed_family():
    db = SessionLocal()
    try:
        if db.query(FamilyMember).count() == 0:
            names = ["Кирилл", "Екатерина", "Ксения"]
            default_bday = date.today()
            for name in names:
                db.add(FamilyMember(name=name, birth_date=default_bday))
            db.commit()
            print("✅ Семья добавлена в базу")
        else:
            print("ℹ️ Семья уже существует")
    finally:
        db.close()

seed_family()
# --- 🚀 КОНЕЦ ИНИЦИАЛИЗАЦИИ ---


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
        await self.send_today_events(update.message.chat_id)

    async def test_notify(self, update, context):
        await update.message.reply_text("🔔 Тестирую уведомления...")
        await self.send_today_events(update.message.chat_id)

    async def add_member(self, update, context):
        await update.message.reply_text(
            "👥 Добавление нового члена семьи\n\n"
            "Используйте формат:\n"
            "`/add_member Имя Фамилия ДД.ММ.ГГГГ`\n\n"
            "Пример:\n"
            "`/add_member Иван Сидоров 15.03.1990`"
        )

    async def list_members(self, update, context):
        db = SessionLocal()
        try:
            service = NotificationService(db)
            members = db.query(FamilyMember).all()

            if not members:
                await update.message.reply_text("👥 В базе пока нет членов семьи")
                return

            message = "👥 Члены семьи:\n\n"
            for member in members:
                # Если в модели есть birth_date — используем его
                if hasattr(member, 'birth_date') and member.birth_date:
                    age = service.calculate_age(member.birth_date)
                    message += f"• {member.name} - {member.birth_date.strftime('%d.%m.%Y')} ({age} лет)\n"
                else:
                    message += f"• {member.name}\n"

            await update.message.reply_text(message)

        except Exception as e:
            await update.message.reply_text("❌ Ошибка при получении данных")
        finally:
            db.close()

    async def send_today_events(self, chat_id):
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

            for member in birthdays:
                message = service.format_birthday_message(member)
                await self.application.bot.send_message(chat_id=chat_id, text=message)
                await asyncio.sleep(0.5)

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
        """Запускаем бота через webhook"""
        # PORT = int(os.environ.get("PORT", 8080))
        # 1. Генерируем секрет
        # WEBHOOK_SECRET = secrets.token_hex(32)
        # # 2. Создаем путь, который будет слушать наше приложение
        # # Используем часть секретной строки, чтобы путь был уникальным и безопасным
        # PATH = f"/{WEBHOOK_SECRET}" # Например: /5a3b2c1d...
        # # старое.Railway автоматически даёт домен вида: https://<project>.up.railway.app
        # WEBHOOK_URL = f"https://poetic-gratitude.up.railway.app{PATH}"
        print("📡 Запуск бота через Long Polling...")
        self.application.run_polling()

        # print(f"📡 Запуск webhook на порту {PORT}")
        # print(f"🔗 Webhook URL: {WEBHOOK_URL}")

        # self.application.run_webhook(
        #     listen="0.0.0.0",
        #     port=PORT,
        #     url_path=PATH,
        #     webhook_url=WEBHOOK_URL,
        #     secret_token=WEBHOOK_SECRET  # исправвлен
        # )


if __name__ == "__main__":
    bot = FamilyBot()
    bot.run()
