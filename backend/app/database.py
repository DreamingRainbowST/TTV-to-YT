from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine_kwargs = {"connect_args": connect_args, "future": True}
if settings.database_url == "sqlite:///:memory:":
    engine_kwargs["poolclass"] = StaticPool
engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def _migrate_upload_jobs() -> None:
    inspector = inspect(engine)
    if "upload_jobs" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("upload_jobs")}
    migrations = {
        "youtube_upload_url": "ALTER TABLE upload_jobs ADD COLUMN youtube_upload_url TEXT",
        "youtube_playlist_id": "ALTER TABLE upload_jobs ADD COLUMN youtube_playlist_id VARCHAR(128)",
        "youtube_playlist_title": "ALTER TABLE upload_jobs ADD COLUMN youtube_playlist_title TEXT",
        "youtube_playlist_item_id": "ALTER TABLE upload_jobs ADD COLUMN youtube_playlist_item_id VARCHAR(128)",
    }

    with engine.begin() as connection:
        for column_name, statement in migrations.items():
            if column_name not in columns:
                connection.execute(text(statement))


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_upload_jobs()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
