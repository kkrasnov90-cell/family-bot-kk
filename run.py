from bot.main import FamilyBot

if __name__ == "__main__":
    bot = FamilyBot()
    bot.application.run_polling()