from database.connection import engine, Base
from database.models import FamilyMember, FamilyEvent


def create_tables():
    """Создает все таблицы в базе данных"""
    print("🔄 Создание таблиц в базе данных...")

    # 🎯 Создаем все таблицы из моделей
    Base.metadata.create_all(bind=engine)

    print("✅ Таблицы успешно созданы!")
    print("📊 Созданные таблицы:")
    print("   - family_members")
    print("   - family_events")


if __name__ == "__main__":
    create_tables()