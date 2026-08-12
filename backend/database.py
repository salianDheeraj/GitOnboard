import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from backend.config import settings

def get_database_url() -> str:
    url = os.getenv("DATABASE_URL") or settings.database_url
    if "postgres" in url and "@postgres:" in url:
        url = url.replace("@postgres:", "@localhost:")
    if url.startswith("postgresql://") and "psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://")
    return url

SQLALCHEMY_DATABASE_URL = get_database_url()

def build_engine():
    try:
        eng = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
        with eng.connect() as conn:
            pass
        return eng
    except Exception:
        fallback_url = "sqlite:///./gitonboard.db"
        return create_engine(fallback_url, connect_args={"check_same_thread": False})

engine = build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
