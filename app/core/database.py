from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.core.config import settings
from app.models.models import Base

# Prepare database URL with correct dialect for psycopg v3
# If using standard postgresql+psycopg:// scheme, convert to postgresql+psycopg for psycopg v3
database_url = settings.DATABASE_URL
if database_url.startswith("postgresql+psycopg://") and "+psycopg" not in database_url:
    # Convert old postgresql+psycopg:// to postgresql+psycopg://
    database_url = database_url.replace("postgresql+psycopg://", "postgresql+psycopg://", 1)

# Create database engine
engine = create_engine(
    database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database - create all tables"""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
