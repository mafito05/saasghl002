# database/connection.py (Con Timeouts)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_URL")

# Añadimos argumentos de conexión para evitar bloqueos
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "options": "-c statement_timeout=5000" # Timeout de 5 segundos
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()