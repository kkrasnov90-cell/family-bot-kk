from datetime import datetime, date
from sqlalchemy import extract
from sqlalchemy.orm import Session
from database.models import FamilyMember, FamilyEvent, EventType


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def get_today_events(self):
        """Получаем события на сегодня"""
        today = date.today()

        # 🎂 Дни рождения сегодня
        birthdays = self.db.query(FamilyMember).filter(
            extract('month', FamilyMember.birth_date) == today.month,
            extract('day', FamilyMember.birth_date) == today.day
        ).all()

        # 🎉 События сегодня
        events = self.db.query(FamilyEvent).filter(
            extract('month', FamilyEvent.event_date) == today.month,
            extract('day', FamilyEvent.event_date) == today.day,
            FamilyEvent.recurring == True
        ).all()

        return birthdays, events

    def calculate_age(self, birth_date):
        """Вычисляем возраст"""
        today = date.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    def calculate_years_passed(self, event_date):
        """Вычисляем сколько лет прошло"""
        today = date.today()
        return today.year - event_date.year

    def format_birthday_message(self, member):
        """Форматируем сообщение о дне рождения"""
        age = self.calculate_age(member.birth_date)
        return f"🎉 Сегодня день рождения {member.name}!\nЕму исполняется {age} лет! 🎂"

    def format_event_message(self, event):
        """Форматируем сообщение о событии"""
        years = self.calculate_years_passed(event.event_date)

        if event.event_type == EventType.ANNIVERSARY:
            return f"💖 {event.title}!\nИсполнилось {years} лет! 💕\n{event.description}"
        elif event.event_type == EventType.MEMORIAL:
            return f"🕯️ {event.title}\n{event.description}"

        return f"📅 {event.title}\n{event.description}"