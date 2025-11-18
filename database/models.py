from sqlalchemy import Column, Integer, String, Date, Text, Boolean, JSON, Enum, func
from datetime import datetime
import enum
from .connection import Base


class EventType(enum.Enum):
    """Типы событий для нашего бота"""
    BIRTHDAY = "birthday"  # День рождения
    ANNIVERSARY = "anniversary"  # Годовщина (свадьба и т.д.)
    MEMORIAL = "memorial"  # Памятная дата
    OTHER = "other"  # Другое событие


class FamilyMember(Base):
    """Модель члена семьи"""
    __tablename__ = "family_members"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # Имя члена семьи
    birth_date = Column(Date, nullable=False)  # Дата рождения
    telegram_id = Column(String(50), nullable=True)  # ID в Telegram (опционально)
    created_at = Column(Date, default=func.now())  # 🎯 ИСПРАВЛЕНО!


class FamilyEvent(Base):
    """Модель семейного события"""
    __tablename__ = "family_events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)  # Название события
    event_date = Column(Date, nullable=False)  # Дата события
    event_type = Column(Enum(EventType), nullable=False)  # Тип события
    description = Column(Text)  # Описание
    photo_ids = Column(JSON)  # Список ID фото
    recurring = Column(Boolean, default=True)  # Повторять ежегодно
    created_at = Column(Date, default=func.now())  # 🎯 ИСПРАВЛЕНО!