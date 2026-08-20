"""数据库引擎与会话。"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _record):
    """SQLite 并发与完整性设置。"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    settings.ensure_dirs()
    from . import models  # noqa: F401  确保模型已注册

    Base.metadata.create_all(engine)
    _migrate_missing_columns()


def _migrate_missing_columns() -> None:
    """开发期轻量迁移：为已存在的表补充新增列（SQLite）。"""
    import sqlalchemy as sa

    additions = {
        "environments": {
            "connector_url": "TEXT",
            "connector_token": "TEXT",
            "ssh_host": "TEXT",
            "ssh_port": "INTEGER",
            "ssh_user": "TEXT",
            "ssh_password": "TEXT",
            "ssh_key_path": "TEXT",
        },
    }
    with engine.begin() as conn:
        for table, cols in additions.items():
            existing = {row[1] for row in conn.execute(sa.text(f"PRAGMA table_info({table})"))}
            for col, ctype in cols.items():
                if col not in existing:
                    conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {col} {ctype}"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
