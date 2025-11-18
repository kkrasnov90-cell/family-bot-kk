from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import Config

# 🎯 Создаем движок для подключения к PostgreSQL
engine = create_engine(Config.DATABASE_URL)

# 🎯 Создаем фабрику сессий для работы с БД
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 🎯 Базовый класс для моделей данных
Base = declarative_base()

def get_db():
    """Функция для получения сессии базы данных"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        