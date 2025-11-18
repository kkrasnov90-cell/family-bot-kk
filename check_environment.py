import psycopg2
from config import Config


def test_connection():
    print("🔍 Тестируем подключение к PostgreSQL...")

    try:
        # Пытаемся подключиться к базе
        conn = psycopg2.connect(Config.DATABASE_URL)
        print("✅ Подключение к PostgreSQL успешно!")

        # Проверяем существует ли база данных
        cursor = conn.cursor()
        cursor.execute("SELECT datname FROM pg_database WHERE datname = 'family_bot_kk'")
        result = cursor.fetchone()

        if result:
            print("✅ База данных 'family_bot_kk' существует")
        else:
            print("❌ База данных 'family_bot_kk' не существует")
            print("Создайте базу через: CREATE DATABASE family_bot_kk;")

        conn.close()

    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        print("\n🔧 Возможные решения:")
        print("1. Проверьте что PostgreSQL запущен")
        print("2. Проверьте правильность пароля")
        print("3. Создайте базу данных: CREATE DATABASE family_bot_kk;")


if __name__ == "__main__":
    test_connection()