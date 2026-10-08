import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# PostgreSQL connection settings.
# Keep the password outside the source code.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/agentic_medical_ai",
)


# SQLAlchemy engine.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


# Database session factory.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db():
    """
    Provide a database session and close it after use.
    """
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()