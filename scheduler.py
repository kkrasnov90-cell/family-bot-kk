import schedule
import time
import threading
from datetime import datetime
from sqlalchemy.orm import Session
from telegram.ext import ExtBot
from telegram.constants import ParseMode # <-- Добавляем этот импорт

# Предполагаем, что NotificationService и create_session находятся в других файлах
from services.notification_service import NotificationService 
from database.session import create_session 


class NotificationScheduler: # <-- Переименуем класс в NotificationScheduler для ясности
    def __init__(self, bot: ExtBot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id # ID чата, куда отправлять уведомления

    async def send_daily_notification(self):
        """Получает события на сегодня и отправляет соответствующие уведомления."""
        
        print(f"🔔 [{datetime.now().strftime('%H:%M')}] Проверяем события...")
        
        try:
            # 1. Инициализация сессии и сервиса
            session: Session = create_session()
            notification_service = NotificationService(db=session)
            
            # 2. Получение всех событий на сегодня
            birthdays, events, death_anniversaries = notification_service.get_today_events()

            # --- Обработка Дней Рождения ---
            for member in birthdays:
                message = notification_service.format_birthday_message(member)
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )

            # --- 🎯 КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Обработка других событий (Свадьбы, т.д.) ---
            for event in events:
                event_message = notification_service.format_event_message(event)
                
                # Получаем ID фото из объекта события
                photo_id = notification_service.get_event_photo_id(event) 

                if photo_id:
                    # Отправка ФОТО с подписью (Caption)
                    await self.bot.send_photo(
                        chat_id=self.chat_id, 
                        photo=photo_id,
                        caption=event_message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    # Отправка только текста
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=event_message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
            # --- Обработка Годовщин Смерти ---
            for member in death_anniversaries:
                message = notification_service.format_death_anniversary_message(member)
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )

            session.close()
            print("✅ Ежедневная проверка выполнена")
            
        except Exception as e:
            print(f"❌ Ошибка при отправке уведомлений: {e}")
            
    # Примечание: Функция run должна быть адаптирована для асинхронной работы, 
    # если вы используете Application.run_polling/webhook

    # ... (Остальная часть класса run, где вызывается schedule.run_pending() )
