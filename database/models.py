from sqlalchemy import Column, Integer, String, Date, Text, Boolean, JSON, Enum, func
from sqlalchemy.orm import Mapped, mapped_column # <--- ДОБАВЛЕНО
from datetime import date, datetime # <--- ИСПРАВЛЕНО: добавлена Mapped, date, datetime
import enum
from .connection import Base

# class EventType(enum.Enum):
#     """Типы событий для нашего бота"""
#     BIRTHDAY = "birthday"  # День рождения
#     ANNIVERSARY = "anniversary"  # Годовщина (свадьба и т.д.)
#     MEMORIAL = "memorial"  # Памятная дата
#     OTHER = "other"  # Другое событие
class EventTypeV2(enum.Enum): # <--- НОВОЕ ИМЯ
    """Типы событий для нашего бота"""
    BIRTHDAY = "birthday"  
    ANNIVERSARY = "anniversary"  
    MEMORIAL = "memorial"  
    OTHER = "other"

class FamilyMember(Base):
    __tablename__ = 'family_members'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    birth_date: Mapped[date] = mapped_column(Date)
    
    # НОВОЕ ПОЛЕ: Для хранения ID файла фотографии в Telegram
    photo_file_id: Mapped[str | None] = mapped_column(String, nullable=True) 

    def __repr__(self) -> str:
        return f"FamilyMember(id={self.id!r}, name={self.name!r})"


class FamilyEvent(Base):
    """Модель семейного события"""
    __tablename__ = "family_events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)  # Название события
    event_date = Column(Date, nullable=False)  # Дата события
    # event_type = Column(Enum(EventType), nullable=False)  # Тип события
    event_type = Column(Enum(EventTypeV2), nullable=False) # <--- ИСПОЛЬЗУЕМ НОВЫЙ ТИП
    description = Column(Text)  # Описание
    photo_ids = Column(JSON)  # Список ID фото
    recurring = Column(Boolean, default=True)  # Повторять ежегодно
    created_at = Column(Date, default=func.now())  # 🎯 ИСПРАВЛЕНО!
