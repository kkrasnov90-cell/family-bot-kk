import os
from dotenv import load_dotenv

# 🎯 Загружаем переменные из .env файла
load_dotenv()

class Config:
    """Класс для хранения конфигурации приложения"""
    # 🔐 Токен бота из .env
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    # 🗄️ URL базы данных из .env
    DATABASE_URL = os.getenv("DATABASE_URL")

    # 👤 ID администратора для уведомлений
    ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

    # ⏰ Время отправки уведомлений (9:00 утра)
    NOTIFICATION_TIME =  "09:00"
