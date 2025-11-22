import sys
import os
from datetime import date, datetime 
import secrets
import asyncio


# 🎯 Добавляем корневую папку проекта в пути Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram.ext import Application, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler # <-- ИМПОРТ ПЛАНИРОВЩИКА
from database.connection import SessionLocal, engine
from database.models import Base, FamilyMember
from services.notification_service import NotificationService
from config import Config

# --- 🚀 ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
Base.metadata.create_all(bind=engine)

def seed_family():
    db = SessionLocal()
    try:
        # ⚠️ ВРЕМЕННЫЙ СКРИПТ ДЛЯ ОЧИСТКИ И ПЕРЕ-ИНИЦИАЛИЗАЦИИ
        print("⚠️ ВРЕМЕННОЕ УДАЛЕНИЕ ВСЕХ ЗАПИСЕЙ (включая Римму)...")
        db.query(FamilyMember).delete()
        db.commit()
        print("✅ Все старые записи удалены.")
        
        # ДОБАВЛЯЕМ ТОЛЬКО КИРИЛЛА (АДМИНА)
        initial_members = [
            # Используем корректную дату рождения
            ("Кирилл", date(1990, 4, 11)),      
        ]
        
        for name, bday in initial_members:
            db.add(FamilyMember(name=name, birth_date=bday))
        db.commit()
        print("✅ Инициализация завершена: добавлен только Кирилл с корректной датой.")

    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка при инициализации базы: {e}")
    finally:
        db.close()

seed_family()
# --- 🚀 КОНЕЦ ИНИЦИАЛИЗАЦИИ ---


class FamilyBot:
    def __init__(self):
        # Используем токен из Config для создания приложения
        self.application = Application.builder().token(Config.BOT_TOKEN).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Настраиваем обработчики команд"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("today", self.today))
        self.application.add_handler(CommandHandler("test_notify", self.test_notify))
        self.application.add_handler(CommandHandler("add_member", self.add_member))
        self.application.add_handler(CommandHandler("list", self.list_members))

    # --- ХЕНДЛЕРЫ КОМАНД ---

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
        """Добавляет нового члена семьи в базу данных, парся аргументы."""
        
        args = context.args
        db = SessionLocal()

        # 1. Проверка аргументов
        if len(args) != 3:
            # Если аргументов нет или их неправильное количество, выводим инструкцию
            return await update.message.reply_text(
                "❌ **Неверный формат команды!**\n\n"
                "Используйте формат:\n"
                "`/add_member Имя Фамилия ДД.ММ.ГГГГ`\n\n"
                "Пример:\n"
                "`/add_member Иван Сидоров 15.03.1990`",
                parse_mode='Markdown'
            )

        # 2. Парсинг данных
        name = f"{args[0]} {args[1]}" # Имя и Фамилия
        date_str = args[2]            # Дата в формате ДД.ММ.ГГГГ

        try:
            # 3. Парсинг даты
            birth_date = datetime.strptime(date_str, '%d.%m.%Y').date()
            
            # 4. Сохранение в БД
            new_member = FamilyMember(name=name, birth_date=birth_date)
            db.add(new_member)
            db.commit()
            
            await update.message.reply_text(
                f"🎉 **{name}** успешно добавлен(а) в семью!\n"
                f"Дата рождения: {birth_date.strftime('%d.%m.%Y')}",
                parse_mode='Markdown'
            )
            
        except ValueError:
            await update.message.reply_text(
                "❌ **Ошибка:** Неправильный формат даты.\n"
                "Дата должна быть в формате **ДД.ММ.ГГГГ** (например, 15.03.1990).",
                parse_mode='Markdown'
            )
        except Exception as e:
            db.rollback()
            await update.message.reply_text(f"❌ Произошла ошибка при сохранении: {e}")
        finally:
            db.close()

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

    # --- ЛОГИКА УВЕДОМЛЕНИЙ И ПЛАНИРОВЩИК ---

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
            # Выводим ошибку в консоль для отладки
            print(f"❌ Ошибка при отправке уведомления в чат {chat_id}: {e}")
            await self.application.bot.send_message(
                chat_id=chat_id,
                text="❌ Ошибка при получении данных для уведомления"
            )
        finally:
            db.close()

    def schedule_daily_notifications(self):
        """Настраивает ежедневное уведомление в 9:00 UTC с помощью APScheduler."""
        scheduler = BackgroundScheduler()

        # Планируем вызов асинхронной функции send_daily_reminder
        # Планировщик использует время UTC (время сервера Railway).
        scheduler.add_job(
            self.send_daily_reminder,
            'cron',
            hour=9, # 9:00 UTC
            minute=0
        )
        scheduler.start()
        print("✅ Планировщик ежедневных уведомлений запущен на 9:00 UTC.")

    async def send_daily_reminder(self):
        """Обертка для send_today_events для использования в планировщике."""
        # Используем ADMIN_CHAT_ID (из Config), который должен быть установлен в Railway
        target_chat_id = Config.ADMIN_CHAT_ID
        if target_chat_id:
            print(f"⏰ Отправка ежедневного уведомления в чат {target_chat_id}...")
            # Вызываем асинхронную функцию
            await self.send_today_events(target_chat_id)
        else:
            print("❌ ADMIN_CHAT_ID не установлен, ежедневное уведомление пропущено.")

    # --- ЗАПУСК БОТА ---

    def run(self):
        """Запускаем бота через Long Polling и активируем планировщик."""
        
        # 1. Запускаем планировщик, который будет работать в фоновом режиме
        self.schedule_daily_notifications() 

        # 2. Запускаем основной цикл Telegram (Long Polling)
        print("📡 Запуск бота через Long Polling...")
        self.application.run_polling()


if __name__ == "__main__":
    bot = FamilyBot()
    bot.run()
