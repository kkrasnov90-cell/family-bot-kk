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
        """
        Добавляет нового члена семьи в базу данных, парся аргументы.
        Формат: /add_member Имя Фамилия ДД.ММ.ГГГГ [ДД.ММ.ГГГГ]
        Последняя дата (если есть) - дата смерти.
        """
        # 🛑 ПРОВЕРКА ПРАВ
        if not self.is_admin_chat(update.message.chat_id):
            return await update.message.reply_text(
                "❌ **Доступ запрещен!** Только администратор может добавлять членов семьи.",
                parse_mode=ParseMode.MARKDOWN
            )
        # 🛑 КОНЕЦ ПРОВЕРКИ
        
        args = context.args
        db = SessionLocal()

        # Проверка на 3 или 4 аргумента (Имя Фамилия ДР [ДС])
        if len(args) < 3 or len(args) > 4:
            return await update.message.reply_text(
                "❌ **Неверный формат команды!**\n\n"
                "Используйте один из форматов:\n"
                "1. **Для живого:**\n `/add_member Имя Фамилия ДД.ММ.ГГГГ (ДР)`\n\n"
                "2. **Для ушедшего:**\n `/add_member Имя Фамилия ДД.ММ.ГГГГ (ДР) ДД.ММ.ГГГГ (ДС)`\n\n"
                "Пример:\n"
                "`/add_member Иван Сидоров 15.03.1990 01.01.2020`",
                parse_mode=ParseMode.MARKDOWN
            )

        name = f"{args[0]} {args[1]}" 
        birth_date_str = args[2]
        death_date_str = args[3] if len(args) == 4 else None
        
        birth_date = None
        death_date = None

        try:
            # 1. Парсинг даты рождения
            birth_date = datetime.strptime(birth_date_str, '%d.%m.%Y').date()
            
            # 2. Парсинг даты смерти (если есть)
            if death_date_str:
                death_date = datetime.strptime(death_date_str, '%d.%m.%Y').date()
            
            new_member = FamilyMember(
                name=name, 
                birth_date=birth_date, 
                death_date=death_date # <--- Добавляем новое поле
            )
            db.add(new_member)
            db.commit()
            
            status = "🎉 **(Живой)**" if death_date is None else "🕯️ **(Ушедший)**"
            # ✅ ИСПРАВЛЕНИЕ 2: Убран лишний атрибут death_date
            death_info = f"\nДата смерти: {death_date.strftime('%d.%m.%Y')}" if death_date else "" 
            
            await update.message.reply_text(
                f"{status} **{name}** успешно добавлен(а) в семью!\n"
                f"Дата рождения: {birth_date.strftime('%d.%m.%Y')}{death_info}",
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
                    
                    # Добавляем информацию о дате смерти в список
                    death_info = f" (ушел {member.death_date.strftime('%d.%m.%Y')})" if member.death_date else ""
                    
                    message += f"• {member.name} - {member.birth_date.strftime('%d.%m.%Y')} ({age_str}){death_info}\n"
                else:
                    message += f"• {member.name}\n"

            await update.message.reply_text(message)

        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при получении данных: {e}")
        finally:
            db.close()

    # --- ЛОГИКА УВЕДОМЛЕНИЙ И ПЛАНИРОВЩИК ---

    async def send_today_events(self, chat_id):
        db = SessionLocal()
        try:
            service = NotificationService(db)
            # 🎯 КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Добавили death_anniversaries
            birthdays, events, death_anniversaries = service.get_today_events()

            # Проверяем все три списка
            if not birthdays and not events and not death_anniversaries:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text="📅 Сегодня нет знаменательных дат"
                )
                return

            # 1. Отправка уведомлений о днях рождения (и живых, и ушедших)
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
                    await self.application.bot.send_message(
                        chat_id=chat_id, 
                        text=message, 
                        parse_mode=ParseMode.MARKDOWN # Добавляем Markdown для форматирования
                    )
                    
                await asyncio.sleep(0.5)

            # 2. Отправка уведомлений о других событиях
            for event in events:
    message = service.format_event_message(event)
    
    # 🎯 КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Пытаемся получить photo_id для события
    photo_id = service.get_event_photo_id(event) 

    if photo_id:
        # Отправка ФОТО с подписью (Caption)
        await self.application.bot.send_photo(
            chat_id=chat_id, 
            photo=photo_id,
            caption=message,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # Отправка только текста
        await self.application.bot.send_message(
            chat_id=chat_id, 
            text=message, 
            parse_mode=ParseMode.MARKDOWN
        )
        
    await asyncio.sleep(0.5)
                
            # 3. Отправка уведомлений о годовщинах смерти
            for member in death_anniversaries:
                message = service.format_death_anniversary_message(member)
                
                await self.application.bot.send_message(
                    chat_id=chat_id, 
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"❌ Ошибка при отправке уведомления в чат {chat_id}: {e}")
            # Добавим отправку сообщения об ошибке, если бот смог подключиться
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Ошибка при получении данных для уведомления"
                )
            except Exception:
                pass # Пропускаем, если даже отправка сообщения об ошибке не сработала
        finally:
            db.close()

    def schedule_daily_notifications(self):
        """Настраивает ежедневное уведомление в 9:00 UTC с помощью AsyncIOScheduler."""
        # ✅ ИСПРАВЛЕНИЕ 3: Инициализируем AsyncIOScheduler
        scheduler = AsyncIOScheduler() 

        scheduler.add_job(
            self.send_daily_reminder,
            'cron',
            hour=9, # 9:00 UTC
            minute=0
        )
        print("✅ Планировщик ежедневных уведомлений настроен.")
        return scheduler

    async def send_daily_reminder(self):
        """Обертка для send_today_events для использования в планировщике."""
        target_chat_id = Config.ADMIN_CHAT_ID
        if target_chat_id:
            print(f"⏰ Отправка ежедневного уведомления в чат {target_chat_id}...")
            # Поскольку это уже асинхронная функция, await здесь корректен
            await self.send_today_events(target_chat_id) 
        else:
            print("❌ ADMIN_CHAT_ID не установлен, ежедневное уведомление пропущено.")

    # --- ЗАПУСК БОТА ---

    def run(self):
        """Запускаем бота через Long Polling и активируем планировщик."""
        
        # 1. Настраиваем планировщик и получаем объект scheduler
        scheduler = self.schedule_daily_notifications() 
        
        # ✅ ИСПРАВЛЕНИЕ 4: Используем post_init для установки команд
        self.application.post_init = self.set_commands

        # 2. Привязываем планировщик к Application (JobQueue) и запускаем его
        self.application.job_queue.scheduler = scheduler
        self.application.job_queue.scheduler.start()
        print("✅ Планировщик ежедневных уведомлений запущен.")

        # 3. Запускаем основной цикл Telegram (Long Polling)
        print("📡 Запуск бота через Long Polling...")
        self.application.run_polling()


if __name__ == "__main__":
    bot = FamilyBot()
    bot.run()
