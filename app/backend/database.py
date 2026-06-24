from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .settings import OUTPUT_ROOT

DB_PATH = OUTPUT_ROOT / "jobfiller.db"

OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_job_columns()
    _harden_local_storage()


def _harden_local_storage() -> None:
    try:
        OUTPUT_ROOT.chmod(0o700)
        if DB_PATH.exists():
            DB_PATH.chmod(0o600)
    except OSError:
        pass


def _ensure_job_columns() -> None:
    from sqlalchemy import text

    with engine.connect() as connection:
        existing = connection.execute(text("PRAGMA table_info(jobs)")).all()
    existing_columns = {str(row[1]) for row in existing}
    required_columns = {
        "materials": "ALTER TABLE jobs ADD COLUMN materials TEXT DEFAULT ''",
        "manual_questions": "ALTER TABLE jobs ADD COLUMN manual_questions TEXT DEFAULT ''",
        "salary": "ALTER TABLE jobs ADD COLUMN salary VARCHAR(200) DEFAULT ''",
    }
    for column, sql in required_columns.items():
        if column not in existing_columns:
            with engine.begin() as connection:
                connection.execute(text(sql))
                existing_columns.add(column)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
