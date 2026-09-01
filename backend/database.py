from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def load_local_env() -> None:
    env_path = Path(__file__).resolve().with_name(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def get_database_url() -> str:
    load_local_env()
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    if os.getenv("ALLOW_SQLITE_FALLBACK") == "1":
        sqlite_path = Path(__file__).resolve().with_name("rail_dashboard.db")
        return f"sqlite+pysqlite:///{sqlite_path}"
    raise RuntimeError("DATABASE_URL is required. Configure PostgreSQL before starting the backend.")


def make_engine():
    url = get_database_url()
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False}, pool_pre_ping=True)
    # SBCNAV uses Supabase's transaction pooler in production. Keep a small,
    # warm client-side pool so normal requests do not repeatedly pay the
    # Mumbai-to-database connection setup cost, while staying well within the
    # limits of the shared PgBouncer pool and the Oracle micro VM.
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "3")),
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "20")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE_SECONDS", "300")),
        pool_use_lifo=True,
        connect_args={
            "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "10")),
            "application_name": os.getenv("DB_APPLICATION_NAME", "sbcnav-fastapi"),
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        },
    )


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def is_sqlite_fallback() -> bool:
    return get_database_url().startswith("sqlite")


class Base(DeclarativeBase):
    pass
