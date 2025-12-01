import os
from bot.main import FamilyBot

if __name__ == "__main__":
    bot = FamilyBot()

    # Проверяем, где запускается бот
    if os.getenv("RAILWAY_ENVIRONMENT"):  # Railway автоматически выставляет эту переменную
        bot.application.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", 8080)),  # Railway задаёт PORT
            url_path=bot.token,
            webhook_url=f"https://{os.getenv('RAILWAY_URL')}/{bot.token}"  # Railway URL из переменной окружения
        )
    else:
        # Локально в PyCharm → Polling
        bot.application.run_polling()
