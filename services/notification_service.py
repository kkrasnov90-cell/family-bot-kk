from datetime import datetime, date
from sqlalchemy import extract
from sqlalchemy.orm import Session
from database.models import FamilyMember, FamilyEvent, EventType

# 🎯 ИСПРАВЛЕНИЕ 1: Добавляем функцию для правильного склонения слова "год"
def pluralize_years(years: int) -> str:
    """Возвращает число и правильно склоненное слово 'год'/'года'/'лет'."""
    if years % 100 in (11, 12, 13, 14):
        return f"{years} лет"
    if years % 10 == 1:
        return f"{years} год"
    if years % 10 in (2, 3, 4):
        return f"{years} года"
    return f"{years} лет"


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
            extract('day', FamilyEvent.event_date) == today.day
            # 💡 Примечание: Убрал фильтр FamilyEvent.recurring == True, 
            # так как по логике FamilyEvent все события должны быть повторяющимися (годовщины)
        ).all()

        # 🕯️ Годовщины смерти сегодня
        death_anniversaries = self.db.query(FamilyMember).filter(
            FamilyMember.death_date != None,  # Фильтр: только умершие
            extract('month', FamilyMember.death_date) == today.month,
            extract('day', FamilyMember.death_date) == today.day
        ).all()

        return birthdays, events, death_anniversaries  

    def calculate_age(self, birth_date):
        """Вычисляем возраст (или возраст, который был бы)"""
        today = date.today()
        # Возраст члена семьи, который жив
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    def calculate_years_passed(self, event_date):
        """Вычисляем сколько лет прошло (простое вычитание года)"""
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

    def format_event_message(self, event: FamilyEvent) -> str:
        """Форматирует сообщение об уведомлении о годовщине события."""
        
        # 🎯 ИСПРАВЛЕНИЕ 2: Используем calculate_years_passed вместо calculate_age
        years_passed = self.calculate_years_passed(event.event_date) 
        years_str = pluralize_years(years_passed)
        
        # 2. Формирование улучшенного сообщения (как вы просили)
        message = (
            f"🎉 **Сегодня {years_str}** со **знаменательной** даты: **{event.title}**! \n" 
            f"Событие **состоялось** **{event.event_date.strftime('%d.%m.%Y')}**."
        )
        return message
        
    def format_death_anniversary_message(self, member):
        """Форматируем сообщение о годовщине смерти"""
        # death_date уже гарантированно не None
        years_passed = self.calculate_years_passed(member.death_date)
        
        # 🎯 ИСПРАВЛЕНИЕ 3: Используем pluralize_years для красивого вывода
        years_str = pluralize_years(years_passed)
        
        return (
            f"🕯️ Сегодня {years_str} со дня смерти **{member.name}**.\n"
            f"Дата смерти: {member.death_date.strftime('%d.%m.%Y')}. "
            f"Помянем. 🙏"
        )
