import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from backend.config import settings

# Support both the legacy DATABASE_URL env var and the config-backed database URL.
# Docker Compose still injects DATABASE_URL, while local development uses settings.database_url.
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL") or settings.database_url
if SQLALCHEMY_DATABASE_URL.startswith("postgresql://") and "psycopg2" not in SQLALCHEMY_DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
