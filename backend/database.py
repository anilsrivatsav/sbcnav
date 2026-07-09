from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    sqlite_path = Path(__file__).resolve().with_name("rail_dashboard.db")
    return f"sqlite+pysqlite:///{sqlite_path}"


def make_engine():
    url = get_database_url()
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False}, pool_pre_ping=True)
    return create_engine(url, pool_pre_ping=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def is_sqlite_fallback() -> bool:
    return get_database_url().startswith("sqlite")


class Base(DeclarativeBase):
    pass
