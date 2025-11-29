# Файл: database/models.py

from sqlalchemy import Column, Integer, String, Date, Text, Boolean, JSON, Enum, func
from sqlalchemy.orm import Mapped, mapped_column 
from datetime import date, datetime 
import enum
from .connection import Base
from sqlalchemy import Column, Integer, String, Date, Boolean

class EventType(enum.Enum):
    """Типы событий для нашего бота"""
    BIRTHDAY = "birthday"     # День рождения
    ANNIVERSARY = "anniversary"   # Годовщина (свадьба и т.д.)
    MEMORIAL = "memorial"     # Памятная дата
    OTHER = "other"       # Другое событие


class FamilyMember(Base):
    """Модель для хранения членов семьи"""
    __tablename__ = 'family_members'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    birth_date: Mapped[date] = mapped_column(Date)
    
    # 🕊️ НОВОЕ ПОЛЕ: Дата смерти
    death_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # Поле для хранения ID файла фотографии в Telegram
    photo_file_id: Mapped[str | None] = mapped_column(String, nullable=True) 
    # 🎯 НОВОЕ ПОЛЕ: Пол (M/F)
    gender = Column(String(1), nullable=True, default='M')

    def __repr__(self) -> str:
        return f"FamilyMember(id={self.id!r}, name={self.name!r})"


class FamilyEvent(Base):
    """Модель семейного события"""
    __tablename__ = "family_events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)  # Название события
    event_date = Column(Date, nullable=False)  # Дата события
    
    # ✅ КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ: Принудительно используем ENUM 'eventtypev2'
    event_type = Column(
        Enum(
            EventType, 
            name='eventtypev2', # Ссылка на существующий, правильный ENUM
            create_type=False # Предотвращает попытку создания
        ), 
        nullable=False
    )
    
    description = Column(Text)  # Описание
    photo_ids = Column(JSON)  # Список ID фото (ВОЗВРАЩЕНО)
    recurring = Column(Boolean, default=True)  # Повторять ежегодно (ВОЗВРАЩЕНО)
    created_at = Column(Date, default=func.now())  # Дата создания записи (ВОЗВРАЩЕНО)
