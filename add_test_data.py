from database.connection import SessionLocal
from database.models import FamilyMember, FamilyEvent, EventType
from datetime import date


def add_test_data():
    """Добавляем реальные данные семьи"""
    db = SessionLocal()

    try:
        print("🔄 Добавляем реальные данные семьи...")

        # 👥 Члены семьи
        members = [
            FamilyMember(name="Кирилл Краснов", birth_date=date(1990, 4, 11)),
            FamilyMember(name="Екатерина Краснова", birth_date=date(1991, 6, 30)),
            FamilyMember(name="Ксения Краснова", birth_date=date(2019, 5, 26)),
        ]

        # 🎉 События
        events = [
            FamilyEvent(
                title="Годовщина свадьбы Кирилла и Екатерины",
                event_date=date(2017, 7, 27),
                event_type=EventType.ANNIVERSARY,
                description="Ура! Поздравляем с годовщиной свадьбы! 💖",
                recurring=True
            )
        ]

        # 🗄️ Сохраняем в базу
        db.add_all(members)
        db.add_all(events)
        db.commit()

        print("✅ Реальные данные добавлены!")
        print("👥 Члены семьи:")
        print("   - Кирилл Краснов (11.04.1990)")
        print("   - Екатерина Краснова (30.06.1991)")
        print("   - Ксения Краснова (26.05.2019)")
        print("🎉 Событие: Годовщина свадьбы 27.07.2017")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    add_test_data()