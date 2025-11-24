from datetime import datetime, date
from sqlalchemy import extract
from sqlalchemy.orm import Session
from database.models import FamilyMember, FamilyEvent, EventType


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def get_today_events(self):
        """
        Получаем события на сегодня:
        - Дни рождения (только для живых).
        - Другие повторяющиеся события.
        - Годовщины смерти.
        """
        today = date.today()

        
        # 🎂 Дни рождения сегодня (для всех, и живых, и ушедших)
        birthdays = self.db.query(FamilyMember).filter(
            extract('month', FamilyMember.birth_date) == today.month,
            extract('day', FamilyMember.birth_date) == today.day
        ).all()

        # 🎉 Другие повторяющиеся события сегодня
        events = self.db.query(FamilyEvent).filter(
            extract('month', FamilyEvent.event_date) == today.month,
            extract('day', FamilyEvent.event_date) == today.day,
            FamilyEvent.recurring == True
        ).all()

        # 🕯️ Годовщины смерти сегодня
        death_anniversaries = self.db.query(FamilyMember).filter(
            FamilyMember.death_date != None,  # Фильтр: только умершие
            extract('month', FamilyMember.death_date) == today.month,
            extract('day', FamilyMember.death_date) == today.day
        ).all()

        # <--- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Теперь возвращаем три списка
        return birthdays, events, death_anniversaries 

    def calculate_age(self, birth_date):
        """Вычисляем возраст"""
        today = date.today()
        # Возраст члена семьи, который жив
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    def calculate_years_passed(self, event_date):
        """Вычисляем сколько лет прошло"""
        today = date.today()
        # Возраст события или количество лет со дня смерти
        return today.year - event_date.year

    def format_birthday_message(self, member):
        """Форматируем сообщение о дне рождения (с учетом статуса)"""
        age = self.calculate_age(member.birth_date)
        
        if member.death_date:
            # Если человек умер, это сообщение о памяти
            return (
                f"🕯️ Сегодня был бы день рождения **{member.name}**!\n"
                f"Мы помним и любим его. Ему исполнилось бы {age} лет. 🙏"
            )
        else:
            # Если человек жив, это сообщение о празднике
            return f"🎉 Сегодня день рождения **{member.name}**!\nЕму исполняется {age} лет! 🎂"

    def format_event_message(self, event):
        """Форматируем сообщение о событии"""
        years = self.calculate_years_passed(event.event_date)

        if event.event_type == EventType.ANNIVERSARY:
            return f"💖 {event.title}!\nИсполнилось {years} лет! 💕\n{event.description}"
        elif event.event_type == EventType.MEMORIAL:
            return f"🕯️ {event.title}\n{event.description}"

        return f"📅 {event.title}\n{event.description}"

    # <--- НОВАЯ ФУНКЦИЯ: Форматирование сообщения о годовщине смерти
    def format_death_anniversary_message(self, member):
        """Форматируем сообщение о годовщине смерти"""
        # death_date уже гарантированно не None
        years_passed = self.calculate_years_passed(member.death_date)
        
        return (
            f"🕯️ Сегодня {years_passed}-я годовщина смерти {member.name}.\n"
            f"Дата смерти: {member.death_date.strftime('%d.%m.%Y')}. "
            f"Помянем. 🙏"
        )
