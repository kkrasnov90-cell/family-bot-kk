import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Считываем переменную. Если она не найдена (вернет None),
#    мы прерываем выполнение, а не передаем None в create_engine.
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
	# Важно: Вызываем исключение, чтобы увидеть явную ошибку в логах Railway,
	# если переменная не была установлена (чего не должно быть, т.к. мы ее настроили).
	raise ValueError("FATAL ERROR: DATABASE_URL не найдена в окружении.")

# 2. Используем считанную переменную для создания движка.
engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()
