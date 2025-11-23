import sys
import os
from datetime import date, datetime 
import secrets
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from apscheduler.schedulers.background import BackgroundScheduler 

# 🎯 Добавляем корневую папку проекта в пути Python
# (Должен быть первым, чтобы импорты работали)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- ИМПОРТЫ МОДЕЛЕЙ И БАЗЫ ДАННЫХ (КРИТИЧЕСКИ ВАЖНО) ---
# После этого момента Python знает, что такое Base, engine, FamilyMember
from database.connection import SessionLocal, engine
from database.models import Base, FamilyMember, FamilyEvent
from services.notification_service import NotificationService
from config import Config


# ----------------------------------------------------
# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (ПЕРЕНЕСЕНЫ СЮДА) ---
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
# SQLAlchemy использует "CREATE TABLE IF NOT EXISTS", чтобы не ругаться, 
# если таблица уже есть. Это самая безопасная команда.
Base.metadata.create_all(bind=engine) 

def seed_family():
    """Добавляет начальные данные, только если база ПУСТА."""
    db = SessionLocal()
    try:
        # 2. Теперь таблица ГАРАНТИРОВАННО существует, и count() не вызовет ошибки.
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

    def setup_handlers(self):
        """Настраиваем обработчики команд"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("today", self.today))
        self.application.add_handler(CommandHandler("test_notify", self.test_notify))
        self.application.add_handler(CommandHandler("add_member", self.add_member))
        self.application.add_handler(CommandHandler("remove_member", self.remove_member))
        self.application.add_handler(CommandHandler("list", self.list_members))
        self.application.add_handler(CommandHandler("set_photo", self.set_photo_command))
        self.application.add_handler(MessageHandler(
            filters.PHOTO & filters.REPLY, self.handle_photo_reply
        ))

    # --- ХЕНДЛЕРЫ КОМАНД ---


    async def set_photo_command(self, update, context):
        """Инструктирует пользователя, как установить фотографию."""
        await update.message.reply_text(
            "📸 Чтобы установить фотографию для члена семьи:\n\n"
            "1. Найдите сообщение, где вы **добавили** этого члена семьи (через `/add_member`).\n"
            "2. **Ответьте (Reply)** на это сообщение командой: `/set_photo Имя Фамилия`\n"
            "3. **Ответьте (Reply)** на вашу же команду `/set_photo...` **самой фотографией!**\n\n"
            "_Это сложно, но безопасно. Введите `/set_photo Имя Фамилия`, а затем ответьте на это сообщение фотографией._",
            parse_mode='Markdown'
        )

    # 🎯 НОВАЯ ФУНКЦИЯ: Проверяет права
    def is_admin_chat(self, chat_id):
        """Проверяет, совпадает ли chat_id с ADMIN_CHAT_ID из Config."""
        return str(chat_id) == str(Config.ADMIN_CHAT_ID)

    async def handle_photo_reply(self, update, context):
        """Обрабатывает фотографию, отправленную в ответ на команду /set_photo."""
        
        if not update.message.reply_to_message:
            return # Игнорируем фото, если это не ответ

        # 1. Пытаемся получить текст из исходного сообщения (команды /set_photo)
        original_message = update.message.reply_to_message.text
        if not original_message or not original_message.startswith('/set_photo'):
            return # Игнорируем, если фото не отвечает на команду /set_photo

        args = original_message.split()[1:] # Имя Фамилия - берем все, что после /set_photo

        if len(args) < 2:
            return await update.message.reply_text(
                "❌ **Не удалось определить имя.** Используйте формат `/set_photo Имя Фамилия`",
                parse_mode='Markdown'
            )

        name_to_find = " ".join(args).strip()
        
        # 2. Получаем ID фотографии (берем самую большую версию)
        photo_file_id = update.message.photo[-1].file_id

        db = SessionLocal()
        try:
            # 3. Ищем члена семьи и обновляем ID фото
            member = db.query(FamilyMember).filter(
                FamilyMember.name == name_to_find
            ).first()

            if member:
                member.photo_file_id = photo_file_id
                db.commit()
                await update.message.reply_text(
                    f"📸 Фотография для **{member.name}** успешно сохранена и привязана!",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    f"❌ Член семьи с именем **{name_to_find}** не найден.",
                    parse_mode='Markdown'
                )

        except Exception as e:
            db.rollback()
            await update.message.reply_text(f"❌ Произошла ошибка при сохранении фото: {e}")
        finally:
            db.close()

    async def start(self, update, context):
        await update.message.reply_text(
            "👋 Привет! Я Family Bot KK! Я напоминаю о важных семейных датах и событиях.\n\n"
            
            "📅 **Список команд:**\n"
            
            "**События и список:**\n"
            "• `/today` — Посмотреть **события на сегодня** 🎂\n"
            "• `/list` — Показать **список всех членов семьи** 👥\n"
            
            "**Управление данными:**\n"
            "• `/add_member Имя Фамилия ДД.ММ.ГГГГ` — **Добавить** члена семьи ➕\n"
            "• `/remove_member Имя Фамилия` — **Удалить** члена семьи 🗑️\n"
            
            "**Тест:**\n"
            "• `/test_notify` — Проверить работу уведомлений 🔔\n\n"
            
            "_⚡ Автоматические уведомления приходят ежедневно в 9:00 UTC!_"
        ,
            parse_mode='Markdown' 
        )

    async def today(self, update, context):
        await self.send_today_events(update.message.chat_id)

    async def test_notify(self, update, context):
        await update.message.reply_text("🔔 Тестирую уведомления...")
        await self.send_today_events(update.message.chat_id)

    async def remove_member(self, update, context):
        """Удаляет члена семьи из базы данных по имени и фамилии."""
        # 🛑 НОВАЯ ПРОВЕРКА ПРАВ
        if not self.is_admin_chat(update.message.chat_id):
            return await update.message.reply_text(
                "❌ **Доступ запрещен!** Только администратор может удалять членов семьи.",
                parse_mode='Markdown'
            )
        # 🛑 КОНЕЦ ПРОВЕРКИ

        args = context.args
        db = SessionLocal()

        # 1. Проверка аргументов (ожидаем минимум 2: Имя и Фамилия)
        if len(args) < 2:
            return await update.message.reply_text(
                "❌ **Неверный формат команды!**\n\n"
                "Используйте формат:\n"
                "`/remove_member Имя Фамилия`\n\n"
                "Пример:\n"
                "`/remove_member Иван Сидоров`",
                parse_mode='Markdown'
            )

        # 2. Объединяем аргументы в полное имя для поиска
        name_to_remove = " ".join(args).strip()

        try:
            # 3. Ищем члена семьи по полному имени
            member = db.query(FamilyMember).filter(
                FamilyMember.name == name_to_remove
            ).first()

            if member:
                # 4. Удаляем, если нашли
                db.delete(member)
                db.commit()
                await update.message.reply_text(
                    f"🗑️ **{member.name}** успешно удален(а) из семьи.",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    f"❌ Член семьи с именем **{name_to_remove}** не найден в базе.",
                    parse_mode='Markdown'
                )

        except Exception as e:
            db.rollback()
            await update.message.reply_text(f"❌ Произошла ошибка при удалении: {e}")
        finally:
            db.close()

    async def add_member(self, update, context):
        """Добавляет нового члена семьи в базу данных, парся аргументы."""
        # 🛑 НОВАЯ ПРОВЕРКА ПРАВ
        if not self.is_admin_chat(update.message.chat_id):
            return await update.message.reply_text(
                "❌ **Доступ запрещен!** Только администратор может добавлять членов семьи.",
                parse_mode='Markdown'
            )
        # 🛑 КОНЕЦ ПРОВЕРКИ
        
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
                    age_num = service.calculate_age(member.birth_date)
                    # Вызываем функцию для правильного склонения
                    age_str = pluralize_years(age_num) 
                    message += f"• {member.name} - {member.birth_date.strftime('%d.%m.%Y')} ({age_str})\n"
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
                
                # Если у члена семьи есть ID фотографии, отправляем фото
                if member.photo_file_id:
                    await self.application.bot.send_photo(
                        chat_id=chat_id, 
                        photo=member.photo_file_id, 
                        caption=message, # Сообщение будет подписью к фото
                        parse_mode='Markdown'
                    )
                else:
                    # Иначе отправляем просто сообщение
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
