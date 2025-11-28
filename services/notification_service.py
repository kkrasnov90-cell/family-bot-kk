import json
from datetime import datetime, date
from sqlalchemy import extract
from sqlalchemy.orm import Session
# 1. НОВЫЙ ИМПОРТ
import pymorphy3 

# Убедитесь, что импорты ниже верны для ваших моделей
from database.models import FamilyMember, FamilyEvent, EventType

# 🎯 ФУНКЦИЯ ДЛЯ ПРАВИЛЬНОГО СКЛОНЕНИЯ
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
        # 2. ИНИЦИАЛИЗАЦИЯ PYMORPHY3
        self.morph = pymorphy3.MorphAnalyzer()

    # 3. НОВЫЙ МЕТОД СКЛОНЕНИЯ
    def get_genitive_name(self, name: str) -> str:
        """Склоняет полное имя (Имя Фамилия) в Родительный падеж (кого? чего?)."""
        words = name.split()
        
        # Склоняем каждое слово в Родительный падеж
        declined_words = []
        for word in words:
            parsed_word = self.morph.parse(word)[0]
            # 'gent' - это Родительный падеж (Genitive)
            declined_word = parsed_word.inflect({'gent'})
            
            # Если склонение прошло успешно, используем его, иначе оставляем слово как есть
            if declined_word:
                # Капитализируем первое слово, чтобы гарантировать правильный регистр
                declined_words.append(declined_word.word.capitalize())
            else:
                declined_words.append(word)
                
        return " ".join(declined_words)


    def get_today_events(self):
        # ... (метод get_today_events остается без изменений)
        """
        Получаем события на сегодня:
        - Дни рождения (для всех, и живых, и ушедших).
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
        ).all()

        # 🕯️ Годовщины смерти сегодня
        death_anniversaries = self.db.query(FamilyMember).filter(
            FamilyMember.death_date != None, 
            extract('month', FamilyMember.death_date) == today.month,
            extract('day', FamilyMember.death_date) == today.day
        ).all()

        return birthdays, events, death_anniversaries

    def calculate_age(self, birth_date):
        """Вычисляем возраст (или возраст, который был бы)"""
        today = date.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    def calculate_years_passed(self, event_date):
        """Вычисляем сколько лет прошло (простое вычитание года)"""
        today = date.today()
        return today.year - event_date.year

    def format_birthday_message(self, member):
        """
        Форматируем сообщение о дне рождения (с учетом статуса и пола) 
        используя склонение.
        """
        age = self.calculate_age(member.birth_date)
        age_str = pluralize_years(age)
        
        # 4. ИСПОЛЬЗУЕМ СКЛОНЕНИЕ: Получаем "Кирилла Краснова"
        declined_name = self.get_genitive_name(member.name)
        
        # Определение местоимений
        if member.gender == 'F':
            # Женщина
            pronoun_age = "Ей"
            pronoun_case_2 = "ее" 
        else: 
            # Мужчина или пол не указан (дефолт 'M')
            pronoun_age = "Ему"
            pronoun_case_2 = "его" 

        if member.death_date:
            # Формат для ушедших
            return (
                f"🕯️ Сегодня был бы день рождения **{declined_name}**!\n" # <--- СКЛОНЕНИЕ
                f"Мы помним и любим {pronoun_case_2}. {pronoun_age} исполнилось бы {age_str}. 🙏"
            )
        else:
            # Формат для живых
            return (
                f"🎉 Сегодня день рождения **{declined_name}**!\n" # <--- СКЛОНЕНИЕ
                f"{pronoun_age} исполняется {age_str}! 🎂"
            )

    # ... (Остальные методы format_event_message, format_death_anniversary_message и get_event_photo_id остаются без изменений)
    def format_event_message(self, event: FamilyEvent) -> str:
        """Форматирует сообщение об уведомлении о годовщине события."""
        
        years_passed = self.calculate_years_passed(event.event_date)
        years_str = pluralize_years(years_passed)
        
        message = (
            f"🎉 **Сегодня {years_str}** со **знаменательной** даты: **{event.title}**! \n" 
            f"Событие **состоялось** **{event.event_date.strftime('%d.%m.%Y')}**."
        )
        return message
        
    def format_death_anniversary_message(self, member):
        """Форматируем сообщение о годовщине смерти (с учетом пола)"""
        years_passed = self.calculate_years_passed(member.death_date)
        years_str = pluralize_years(years_passed)
        
        # 🎯 НОВОЕ ИСПРАВЛЕНИЕ: Определение местоимения
        if member.gender == 'F':
            pronoun_case_1 = "Её" # Её нет с нами
            pronoun_case_2 = "Ушла" # Ушла из жизни
        else:
            pronoun_case_1 = "Его"
            pronoun_case_2 = "Ушел"
            
        return (
            f"🕯️ Сегодня {years_str} со дня ухода из жизни **{member.name}**.\n"
            f"{pronoun_case_1} нет с нами. {pronoun_case_2} из жизни {member.death_date.strftime('%d.%m.%Y')}. "
            f"Светлая память. 🙏"
        )

    # 🚀 ИСПРАВЛЕННЫЙ МЕТОД ДЛЯ ОБРАБОТКИ СПИСКОВ И СТРОК
    def get_event_photo_id(self, event: FamilyEvent) -> str | None:
        """
        Извлекает первый ID фотографии из поля photo_ids события, 
        обрабатывая случай, когда photo_ids — список или строка.
        """
        if not event.photo_ids:
            return None
            
        photo_ids = event.photo_ids
        
        # 1. Если photo_ids уже является списком
        if isinstance(photo_ids, list) and photo_ids:
            if isinstance(photo_ids[0], str):
                return photo_ids[0]

        # 2. Если photo_ids является строкой, пытаемся распарсить или вернуть как есть
        if isinstance(photo_ids, str):
            try:
                # Убираем внешние кавычки, если есть, и заменяем одинарные на двойные
                cleaned_ids = photo_ids.strip().replace("'", "\"")
                photo_list = json.loads(cleaned_ids)
                
                # Если успешно распарсили список, возвращаем первый элемент (строку)
                if photo_list and isinstance(photo_list, list) and isinstance(photo_list[0], str):
                    return photo_list[0]
                
            except (json.JSONDecodeError, IndexError, TypeError):
                # Если парсинг не удался, возвращаем исходную строку.
                return photo_ids.strip()
                
        return None
