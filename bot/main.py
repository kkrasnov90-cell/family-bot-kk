import sys
import os
from datetime import date, datetime
import secrets
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

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
                db.add(FamilyMember(name=name, birth_date=bday, gender='M'))
            db.commit()
            print("✅ Семья добавлена в базу (инициализация).")
        else:
            print("ℹ️ Семья уже существует")
    except Exception as e:
        print(f"❌ Ошибка инициализации seed-данных: {e}. Убедитесь, что models.py обновлен.")
    finally:
        db.close()

seed_family()

# --- 🚀 КОНЕЦ ИНИЦИАЛИЗАЦИИ ---

class FamilyBot:
    def __init__(self):
        self.request_config = HTTPXRequest(read_timeout=60.0)

        # создаём Application напрямую
        self.application = ApplicationBuilder() \
            .token(Config.BOT_TOKEN) \
            .request(self.request_config) \
            .build()

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
        self.application.add_handler(CommandHandler("add_event", self.add_event))
        self.application.add_handler(CommandHandler("list", self.list_members))
        self.application.add_handler(CommandHandler("set_photo", self.set_photo_command))
        
        # 🎯 НОВАЯ КОМАНДА ДЛЯ ФОТО СОБЫТИЙ
        self.application.add_handler(CommandHandler("set_event_photo", self.set_event_photo_command))

        # 🎯 ПОСТОЯННАЯ АДМИН-КОМАНДА /file_id
        self.application.add_handler(CommandHandler("file_id", self.file_id_command))

        # Обработчик ответов на фото
        self.application.add_handler(MessageHandler(
            filters.PHOTO & filters.REPLY, self.handle_photo_reply
        ))

    async def set_commands(self, application):
        """Устанавливает список команд в меню Telegram."""
        commands = [
            ("start", "👋 Приветствие и цели бота"),
            ("today", "📅 События на сегодня"),
            ("add_event", "➕ Добавить семейное событие (админ)"),
            ("list", "👥 Показать всех членов семьи"),
            ("add_member", "➕ Добавить члена семьи (админ)"),
            ("remove_member", "🗑️ Удалить члена семьи (админ)"),
            ("set_photo", "📸 Установить фото члена семьи (админ)"),
            ("set_event_photo", "🖼️ Установить фото события (админ)"),
            ("test_notify", "🔔 Проверить уведомления"),
            ("file_id", "🔑 Получить ID файла (админ)"),
        ]

        await self.application.bot.set_my_commands(commands)
        print("✅ Меню команд Telegram успешно установлено.")


    # --- ХЕНДЛЕРЫ КОМАНД ---

    async def start(self, update, context):
        GREETING_PHOTO_ID = getattr(Config, 'GREETING_PHOTO_ID', None)
        message_text = (
            "**👋 Привет! Я Цифровой Хранитель Семейной Памяти.**\n\n"
            "Моя задача — хранить в памяти всё, что важно для вашей семьи, и делиться этим с вами в нужный момент.\n\n"
            "Наше положение на земле поистине удивительно. Каждый появляется на ней на короткий миг, без понятной цели , хотя некоторым удается цель придумать . Но с точки зрения обыденной жизни, очевидно одно: мы живем для других людей и более всего для тех, от чьих улыбок и благополучия зависит наше собственное счастье! \n\n"
            "**🌟 Как я работаю?**\n"
            "Я работаю автоматически и тихо, отправляя уведомления **каждый день в 12:00**:\n"
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
        if not self.is_admin_chat(update.message.chat_id):
            return await update.message.reply_text("❌ **Доступ запрещен!** Эта команда только для администратора.", parse_mode=ParseMode.MARKDOWN)

        replied_message = update.message.reply_to_message
        if not replied_message:
            return await update.message.reply_text("❌ **Используйте команду как ответ на медиафайл**", parse_mode=ParseMode.MARKDOWN)

        file_id = None
        file_type = None

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

        if file_id:
            message = f"✅ **File ID для {file_type}**:\n```\n{file_id}\n```"
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            print(f"\n\n--- ⚠️ FILE ID ({file_type}): {file_id} ⚠️ ---\n\n")
        else:
            await update.message.reply_text("❌ **Медиафайл не найден!**", parse_mode=ParseMode.MARKDOWN)


    async def set_photo_command(self, update, context):
        """Инструктирует пользователя, как установить фотографию для члена семьи."""
        await update.message.reply_text(
            "📸 Чтобы установить фотографию для члена семьи:\n\n"
            "1. Найдите сообщение, где вы <b>добавили</b> этого члена семьи (через <code>/add_member</code>).\n"
            "2. <b>Ответьте (Reply)</b> на это сообщение командой: <code>/set_photo Имя Фамилия</code>\n"
            "3. <b>Ответьте (Reply)</b> на вашу же команду <code>/set_photo...</code> <b>самой фотографией!</b>",
            parse_mode=ParseMode.HTML
        )

    async def set_event_photo_command(self, update, context):
        """Инструктирует пользователя, как установить фотографию для события."""
        if not self.is_admin_chat(update.message.chat_id):
            return await update.message.reply_text("❌ **Доступ запрещен!** Эта команда только для администратора.", parse_mode=ParseMode.MARKDOWN)

        await update.message.reply_text(
            "📸 Чтобы установить фотографию для **события**:\n\n"
            "1. **Ответьте (Reply)** на *любое* сообщение командой: <code>/set_event_photo Название События</code>\n"
            "2. **Ответьте (Reply)** на вашу же команду <code>/set_event_photo...</code> **самой фотографией!**\n\n"
            "**Важно:** Название должно совпадать с названием события, которое вы ввели при его создании.",
            parse_mode=ParseMode.HTML
        )

    async def handle_photo_reply(self, update, context):
        """Обрабатывает фотографию, отправленную в ответ на команду /set_photo ИЛИ /set_event_photo."""
        if not self.is_admin_chat(update.message.chat_id): return
        if not update.message.reply_to_message: return

        original_message = update.message.reply_to_message.text
        if not original_message: return
        
        photo_file_id = update.message.photo[-1].file_id
        db = SessionLocal()

        try:
            if original_message.startswith('/set_photo'):
                # --- ЛОГИКА ДЛЯ ЧЛЕНА СЕМЬИ (FamilyMember) ---
                args = original_message.split()[1:]
                if len(args) < 2:
                    return await update.message.reply_text("❌ **Не удалось определить имя члена семьи.**", parse_mode=ParseMode.MARKDOWN)

                name_to_find = " ".join(args).strip()
                member = db.query(FamilyMember).filter(FamilyMember.name == name_to_find).first()
                
                if member:
                    member.photo_file_id = photo_file_id
                    db.commit()
                    await update.message.reply_text(f"📸 Фотография для **{member.name}** успешно сохранена и привязана!", parse_mode=ParseMode.MARKDOWN)
                else:
                    await update.message.reply_text(f"❌ Член семьи с именем **{name_to_find}** не найден.", parse_mode=ParseMode.MARKDOWN)

            elif original_message.startswith('/set_event_photo'):
                # --- ЛОГИКА ДЛЯ СОБЫТИЯ (FamilyEvent) ---
                args = original_message.split()[1:]
                if not args:
                    return await update.message.reply_text("❌ **Не удалось определить название события.**", parse_mode=ParseMode.MARKDOWN)
                
                title_to_find = " ".join(args).strip().strip('"\'') # Учитываем кавычки
                
                event = db.query(FamilyEvent).filter(FamilyEvent.title == title_to_find).first()
                
                if event:
                    # Добавляем ID в массив photo_ids, если его нет
                    if event.photo_ids is None:
                        event.photo_ids = []
                    
                    if photo_file_id not in event.photo_ids:
                        event.photo_ids.append(photo_file_id)
                        db.commit()
                        await update.message.reply_text(f"📸 Фотография успешно добавлена к событию **\"{event.title}\"**!", parse_mode=ParseMode.MARKDOWN)
                    else:
                        await update.message.reply_text(f"⚠️ Эта фотография уже привязана к событию **\"{event.title}\"**.", parse_mode=ParseMode.MARKDOWN)
                else:
                    await update.message.reply_text(f"❌ Событие с названием **\"{title_to_find}\"** не найдено.", parse_mode=ParseMode.MARKDOWN)
            else:
                 # Игнорировать другие ответы на фото
                 return

        except Exception as e:
            db.rollback()
            await update.message.reply_text(f"❌ Произошла ошибка при сохранении фото: {e}")
        finally:
            db.close()


    async def remove_member(self, update, context):
        """Удаляет члена семьи из базы данных по имени и фамилии."""
        if not self.is_admin_chat(update.message.chat_id):
             return await update.message.reply_text("❌ **Доступ запрещен!** Только администратор может удалять членов семьи.", parse_mode=ParseMode.MARKDOWN)

        args = context.args
        db = SessionLocal()

        if len(args) < 2:
            return await update.message.reply_text("❌ **Неверный формат команды!** Используйте `/remove_member Имя Фамилия`", parse_mode=ParseMode.MARKDOWN)

        name_to_remove = " ".join(args).strip()

        try:
            member = db.query(FamilyMember).filter(FamilyMember.name == name_to_remove).first()
            if member:
                db.delete(member)
                db.commit()
                await update.message.reply_text(f"🗑️ **{member.name}** успешно удален(а) из семьи.", parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text(f"❌ Член семьи с именем **{name_to_remove}** не найден в базе.", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            db.rollback()
            await update.message.reply_text(f"❌ Произошла ошибка при удалении: {e}")
        finally:
            db.close()

    async def add_member(self, update, context):
        """
        Добавляет нового члена семьи в базу данных.
        Формат: /add_member Имя Фамилия M/F ДД.ММ.ГГГГ [ДД.ММ.ГГГГ]
        """
        if not self.is_admin_chat(update.message.chat_id):
            return await update.message.reply_text("❌ **Доступ запрещен!** Только администратор может добавлять членов семьи.", parse_mode=ParseMode.MARKDOWN)

        args = context.args
        db = SessionLocal()

        # 🎯 Ожидаем 4 или 5 аргументов (Имя, Фамилия, Пол, ДР, [ДС])
        if len(args) < 4 or len(args) > 5:
            return await update.message.reply_text(
                "❌ **Неверный формат команды!**\n\n"
                "Используйте один из форматов:\n"
                "1. **Для живого:**\n `/add_member Имя Фамилия M/F ДД.ММ.ГГГГ`\n\n"
                "2. **Для ушедшего:**\n `/add_member Имя Фамилия M/F ДД.ММ.ГГГГ ДД.ММ.ГГГГ`\n\n"
                "**M** - Мужчина, **F** - Женщина.\n"
                "Пример: `/add_member Юлия Фоминых F 27.11.1989`",
                parse_mode=ParseMode.MARKDOWN
            )

        name = f"{args[0]} {args[1]}"
        gender = args[2].upper()  # Получаем и переводим в верхний регистр (M или F)
        birth_date_str = args[3]
        death_date_str = args[4] if len(args) == 5 else None

        # Проверка корректности пола
        if gender not in ['M', 'F']:
             return await update.message.reply_text(
                "❌ **Ошибка:** Пол должен быть указан как **M** (Мужчина) или **F** (Женщина).",
                parse_mode=ParseMode.MARKDOWN
            )

        birth_date = None
        death_date = None

        try:
            # Парсинг дат
            birth_date = datetime.strptime(birth_date_str, '%d.%m.%Y').date()
            if death_date_str: death_date = datetime.strptime(death_date_str, '%d.%m.%Y').date()

            # Добавляем пол в модель
            new_member = FamilyMember(
                name=name,
                birth_date=birth_date,
                death_date=death_date,
                gender=gender # <--- ПЕРЕДАЕМ ПОЛ
            )
            db.add(new_member)
            db.commit()

            status = "🎉 **(Живой)**" if death_date is None else "🕯️ **(Ушедший)**"
            death_info = f"\nДата смерти: {death_date.strftime('%d.%m.%Y')}" if death_date else ""

            await update.message.reply_text(
                f"{status} **{name}** успешно добавлен(а) в семью!\n"
                f"Пол: **{gender}**\n"
                f"Дата рождения: {birth_date.strftime('%d.%m.%Y')}{death_info}",
                parse_mode=ParseMode.MARKDOWN
            )

        except ValueError:
            await update.message.reply_text("❌ **Ошибка:** Неправильный формат даты. Дата должна быть в формате **ДД.ММ.ГГГГ**.", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            db.rollback()
            await update.message.reply_text(f"❌ Произошла ошибка при сохранении: {e}")
        finally:
            db.close()

    async def add_event(self, update, context):
        """
        Добавляет новое семейное событие.
        Формат: /add_event "Название события" ТИП ДД.ММ.ГГГГ [Описание]
        """
        if not self.is_admin_chat(update.message.chat_id):
            return await update.message.reply_text("❌ **Доступ запрещен!** Только администратор может добавлять события.", parse_mode=ParseMode.MARKDOWN)

        args = context.args
        db = SessionLocal()

        # Ожидаем минимум 3 аргумента: Название, ТИП и Дата.
        if len(args) < 3:
            return await update.message.reply_text(
                "❌ **Неверный формат команды!**\n\n"
                "Используйте формат:\n"
                "`/add_event \"Название события\" ТИП ДД.ММ.ГГГГ [Описание]`\n\n"
                "**ТИП** должен быть одним из: **ANNIVERSARY, HOLIDAY, CUSTOM**.\n\n"
                "Пример: `/add_event \"Годовщина свадьбы\" ANNIVERSARY 15.07.2010 Наша первая важная дата`",
                parse_mode=ParseMode.MARKDOWN
            )

        # 1. Ищем дату в формате ДД.ММ.ГГГГ
        date_index = -1
        event_date_str = None
        for i, arg in enumerate(args):
            # Проверяем, выглядит ли аргумент как ДД.ММ.ГГГГ
            if len(arg) == 10 and arg.replace('.', '').isdigit() and arg.count('.') == 2:
                event_date_str = arg
                date_index = i
                break
        
        if event_date_str is None:
            return await update.message.reply_text(
                "❌ **Ошибка парсинга:** Не удалось найти дату в формате **ДД.ММ.ГГГГ** в команде.",
                parse_mode=ParseMode.MARKDOWN
            )

        # 2. Формируем Описание (все после даты)
        description = " ".join(args[date_index+1:])
        
        # 3. Название и ТИП (все до даты)
        pre_date_args = args[:date_index]
        
        if len(pre_date_args) < 2:
             return await update.message.reply_text(
                "❌ **Неверный формат!** Не хватает Названия или ТИПА события перед датой.",
                parse_mode=ParseMode.MARKDOWN
            )

        # Тип события - последний аргумент перед датой
        event_type = pre_date_args[-1].upper() 
        title_parts = pre_date_args[:-1]
        title = " ".join(title_parts).strip().strip('"\'')
        
        # Проверка на допустимые типы событий (должны соответствовать модели)
        ALLOWED_TYPES = ['ANNIVERSARY', 'HOLIDAY', 'CUSTOM']
        if event_type not in ALLOWED_TYPES:
             return await update.message.reply_text(
                f"❌ **Ошибка:** Тип события **{event_type}** не разрешен. Используйте один из: **{', '.join(ALLOWED_TYPES)}**.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        # 4. Проверка названия
        if not title:
             return await update.message.reply_text(
                "❌ **Неверный формат!** Название события не может быть пустым.",
                parse_mode=ParseMode.MARKDOWN
            )

        try:
            event_date = datetime.strptime(event_date_str, '%d.%m.%Y').date()

            # 🎯 ИСПРАВЛЕНИЕ: Используем event_date, event_type И добавляем photo_ids=[]
            new_event = FamilyEvent(
                title=title,
                event_date=event_date,
                event_type=event_type, 
                description=description,
                photo_ids=[] # Инициализируем пустым массивом для возможности дальнейшего добавления фото
            )
            db.add(new_event)
            db.commit()

            description_info = f"\nОписание: _{description}_" if description else ""

            await update.message.reply_text(
                f"🗓️ **Событие** \"{title}\" ({event_type}) успешно добавлено!\n"
                f"Дата: **{event_date.strftime('%d.%m.%Y')}**{description_info}",
                parse_mode=ParseMode.MARKDOWN
            )

        except ValueError:
            await update.message.reply_text("❌ **Ошибка:** Неправильный формат даты. Дата должна быть в формате **ДД.ММ.ГГГГ**.", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            db.rollback()
            await update.message.reply_text(f"❌ Произошла ошибка при сохранении события: {e}")
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

                    death_info = f" (ушел {member.death_date.strftime('%d.%m.%Y')})" if member.death_date else ""
                    gender_info = f" ({member.gender})" if member.gender else ""

                    message += f"• {member.name}{gender_info} - {member.birth_date.strftime('%d.%m.%Y')} ({age_str}){death_info}\n"
                else:
                    message += f"• {member.name}\n"

            await update.message.reply_text(message)

        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при получении данных: {e}")
        finally:
            db.close()

    # --- ЛОГИКА УВЕДОМЛЕНИЙ И ПЛАНИРОВЩИК ---

    async def today(self, update, context):
        """Обработчик команды /today. Немедленно запускает отправку событий."""
        await self.send_today_events(update.message.chat_id)

    async def test_notify(self, update, context):
        await update.message.reply_text("🔔 Тестирую уведомления...")
        await self.send_today_events(update.message.chat_id)

    async def send_today_events(self, chat_id):
        db = SessionLocal()
        try:
            service = NotificationService(db)
            birthdays, events, death_anniversaries = service.get_today_events()

            # Логирование для сервера (чисто)
            if birthdays or events or death_anniversaries:
                 print(f"INFO: Обнаружены события на сегодня: ДР={len(birthdays)}, События={len(events)}, Смерти={len(death_anniversaries)}")

            # Проверяем все три списка
            if not birthdays and not events and not death_anniversaries:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text="📅 Сегодня нет знаменательных дат"
                )
                return

            # --- 1. Отправка дней рождения (Birthdays) ---
            for member in birthdays:
                # 🟢 ШАГ 1: ОТПРАВКА АНИМАЦИИ (ТОРТ)
                try:
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text="🎂", # Это запускает полноэкранную анимацию!
                    )
                except Exception as e:
                    print(f"❌ Предупреждение: Не удалось отправить эмодзи-анимацию: {e}")

                # 🟢 ШАГ 2: ОТПРАВКА ИНФОРМАЦИОННОГО СООБЩЕНИЯ
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
                        parse_mode=ParseMode.MARKDOWN
                    )
                await asyncio.sleep(0.5)

            # --- 2. Отправка других событий (Events) ---
            for event in events:
                message = service.format_event_message(event)
                photo_id = service.get_event_photo_id(event)

                if isinstance(photo_id, str) and photo_id.strip():
                    await self.application.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo_id,
                        caption=message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                await asyncio.sleep(0.5)

            # --- 3. Отправка годовщин смерти (Death Anniversaries) ---
            for member in death_anniversaries:
                # message генерируется в service и содержит Её/Его
                message = service.format_death_anniversary_message(member)

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
                        parse_mode=ParseMode.MARKDOWN
                    )
                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"❌ Ошибка при отправке уведомления в чат {chat_id}: {e}")
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Ошибка при получении данных для уведомления"
                )
            except Exception:
                pass
        finally:
            db.close()

    def schedule_daily_notifications(self):
        """Настраивает ежедневное уведомление в 9:00 UTC с помощью AsyncIOScheduler."""
        scheduler = AsyncIOScheduler()

        scheduler.add_job(
            self.send_daily_reminder,
            'cron',
            hour=9,
            minute=0
        )
        print("✅ Планировщик ежедневных уведомлений настроен.")
        return scheduler

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

        scheduler = self.schedule_daily_notifications()

        self.application.post_init = self.set_commands

        self.application.job_queue.scheduler = scheduler
        self.application.job_queue.scheduler.start()
        print("✅ Планировщик ежедневных уведомлений запущен.")

        print("📡 Запуск бота через Long Polling...")
        self.application.run_polling()


if __name__ == "__main__":
    bot = FamilyBot()
    bot.run()
