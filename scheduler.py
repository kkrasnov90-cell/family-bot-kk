import schedule
import time
import requests
import threading
from datetime import datetime


class SimpleScheduler:
    def __init__(self, bot_url):
        self.bot_url = bot_url

    def send_daily_notification(self):
        """Отправляет ежедневное уведомление"""
        print(f"🔔 [{datetime.now().strftime('%H:%M')}] Проверяем события...")
        try:
            # 🎯 Здесь будет логика отправки уведомлений
            # Пока просто логируем
            print("✅ Ежедневная проверка выполнена")
        except Exception as e:
            print(f"❌ Ошибка: {e}")

    def run(self):
        """Запускает планировщик"""
        print("⏰ Простой планировщик запущен")

        # 🕘 Настраиваем расписание
        schedule.every().day.at("09:00").do(self.send_daily_notification)
        schedule.every().day.at("21:00").do(self.send_daily_notification)  # Тест вечером

        print("📅 Расписание:")
        print("   - Ежедневно в 09:00 - утренние уведомления")
        print("   - Ежедневно в 21:00 - тестовые уведомления")

        # 🎯 Бесконечный цикл проверки расписания
        while True:
            schedule.run_pending()
            time.sleep(60)  # Проверяем каждую минуту


if __name__ == "__main__":
    scheduler = SimpleScheduler("http://localhost:8000")
    scheduler.run()