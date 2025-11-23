import sys
import os
from datetime import date, datetime 
import secrets
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from apscheduler.schedulers.background import BackgroundScheduler 
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

    async def set_commands(self):
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
            "1. Найдите сообщение, где вы **добавили** этого члена семьи (через `/add_member`).\n"
            "2. **Ответьте (Reply)** на это сообщение командой: `/set_photo Имя Фамилия`\n"
            "3. **Ответьте (Reply)** на вашу же команду `/set_photo...` **самой фотографией!**\n\n"
            "_Это сложно, но безопасно. Введите `/set_photo Имя Фамилия`, а затем ответьте на это сообщение фотографией._",
            parse_mode=ParseMode.MARKDOWN
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
        # 🛑 ПРОВЕРКА ПРАВ
        if not self.is_admin_chat(update.message.chat_id):
            return await update.message.reply_text(
                "❌ **Доступ запрещен!** Только администратор может удалять членов семьи.",
                parse_mode=ParseMode.MARKDOWN
            )
        # 🛑 КОНЕЦ ПРОВЕРКИ

        args = context.args
        db = SessionLocal()

        if len(args) < 2:
            return await update.message.reply_text(
                "❌ **Неверный формат команды!**\n\n"
                "Используйте формат:\n"
                "`/remove_member Имя Фамилия`\n\n"
                "Пример:\n"
                "`/remove_member Иван Сидоров`",
                parse_mode=ParseMode.MARKDOWN
            )

        name_to_remove = " ".join(args).strip()

        try:
            member = db.query(FamilyMember).filter(
                FamilyMember.name == name_to_remove
            ).first()

            if member:
                db.delete(member)
                db.commit()
                await update.message.reply_text(
                    f"🗑️ **{member.name}** успешно удален(а) из семьи.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    f"❌ Член семьи с именем **{name_to_remove}** не найден в базе.",
                    parse_mode=ParseMode.MARKDOWN
                )

        except Exception as e:
            db.rollback()
            await update.message.reply_text(f"❌ Произошла ошибка при удалении: {e}")
        finally:
            db.close()

    async def add_member(self, update, context):
        """Добавляет нового члена семьи в базу данных, парся аргументы."""
        # 🛑 ПРОВЕРКА ПРАВ
        if not self.is_admin_chat(update.message.chat_id):
            return await update.message.reply_text(
                "❌ **Доступ запрещен!** Только администратор может добавлять членов семьи.",
                parse_mode=ParseMode.MARKDOWN
            )
        # 🛑 КОНЕЦ ПРОВЕРКИ
        
        args = context.args
        db = SessionLocal()

        if len(args) != 3:
            return await update.message.reply_text(
                "❌ **Неверный формат команды!**\n\n"
                "Используйте формат:\n"
                "`/add_member Имя Фамилия ДД.ММ.ГГГГ`\n\n"
                "Пример:\n"
                "`/add_member Иван Сидоров 15.03.1990`",
                parse_mode=ParseMode.MARKDOWN
            )

        name = f"{args[0]} {args[1]}" 
        date_str = args[2]            

        try:
            birth_date = datetime.strptime(date_str, '%d.%m.%Y').date()
            
            new_member = FamilyMember(name=name, birth_date=birth_date)
            db.add(new_member)
            db.commit()
            
            await update.message.reply_text(
                f"🎉 **{name}** успешно добавлен(а) в семью!\n"
                f"Дата рождения: {birth_date.strftime('%d.%m.%Y')}",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except ValueError:
            await update.message.reply_text(
                "❌ **Ошибка:** Неправильный формат даты.\n"
                "Дата должна быть в формате **ДД.ММ.ГГГГ** (например, 15.03.1990).",
                parse_mode=ParseMode.MARKDOWN
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
                
                if member.photo_file_id:
                    await self.application.bot.send_photo(
                        chat_id=chat_id, 
                        photo=member.photo_file_id, 
                        caption=message, 
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await self.application.bot.send_message(chat_id=chat_id, text=message)
                    
                await asyncio.sleep(0.5)

            for event in events:
                message = service.format_event_message(event)
                await self.application.bot.send_message(chat_id=chat_id, text=message)
                await asyncio.sleep(0.5)

        except Exception as e:
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
        target_chat_id = Config.ADMIN_CHAT_ID
        if target_chat_id:
            print(f"⏰ Отправка ежедневного уведомления в чат {target_chat_id}...")
            await self.send_today_events(target_chat_id)
        else:
            print("❌ ADMIN_CHAT_ID не установлен, ежедневное уведомление пропущено.")

    # --- ЗАПУСК БОТА ---

    def run(self):
        """Запускаем бота через Long Polling и активируем планировщик."""
        
        # 1. Запускаем планировщик, который будет работать в фоновом режиме
        self.schedule_daily_notifications()  

        # 2. Устанавливаем команды перед запуском (через loop)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.set_commands()) 

        # 3. Запускаем основной цикл Telegram (Long Polling)
        print("📡 Запуск бота через Long Polling...")
        self.application.run_polling()


if __name__ == "__main__":
    bot = FamilyBot()
    bot.run()
