from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from src.core.config import get_settings
from src.core.logging import logger

settings = get_settings()

# Engine configuration tailored to database dialect
engine_kwargs = {}
if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
        }
    )

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# Session factory for generating request-scoped database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Declarative Base for ORM Models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session per request and guarantees cleanup."""
    db: Session = SessionLocal()
    try:
        yield db
    except Exception as exc:
        logger.error(f"Database session encountered an unhandled exception: {exc}")
        db.rollback()
        raise
    finally:
        db.close()
