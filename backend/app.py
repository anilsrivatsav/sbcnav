from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import SessionLocal, engine, is_sqlite_fallback
from models import Base
from api_utils import envelope, exception_response, filter_search, paginate, sort_items
from services import (
    earnings_sort_map,
    get_stats,
    list_earnings,
    list_stations,
    list_units,
    list_works,
    rebuild_db,
    station_sort_map,
    unit_sort_map,
    work_sort_map,
)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rail_dashboard.api")


app = FastAPI(title="Rail Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000", 
        "http://localhost:3000", 
        "http://127.0.0.1:5173",
      # Vercel
        "https://sbcnav.vercel.app",   # your production domain (if used)
        "https://sbcnav-38t2-2doxwtr6h-anil-b-hs-projects.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    try:
        response = await call_next(request)
        logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
        return response
    except Exception as exc:
        return exception_response(exc)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content=envelope(None, exc.detail, False))

@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)

    if is_sqlite_fallback():
        logger.info("SQLite fallback detected; local cache available.")
    else:
        logger.info("API startup complete.")


@app.get("/api/health")
def health() -> dict[str, object]:
    return envelope({"status": "ok"}, "ok")


@app.post("/api/sync")
def sync() -> dict[str, object]:
    try:
        return envelope(rebuild_db(), "synchronized")
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/stats")
def stats():
    return envelope(get_stats(), "ok")


@app.get("/api/stations")
def stations(q: str | None = None, category: str | None = None, page: int = 1, page_size: int = 25, sort_by: str | None = None, sort_order: str = "asc", search: str | None = None):
    items = filter_search(list_stations(q=q, category=category), search or q)
    items = sort_items(items, sort_by if sort_by in station_sort_map() else None, sort_order)
    page_data = paginate(items, page, page_size)
    return envelope({"items": page_data.items, "pagination": {"total": page_data.total, "page": page_data.page, "page_size": page_data.page_size}}, "ok")


@app.get("/api/units")
def units(q: str | None = None, station_code: str | None = None, page: int = 1, page_size: int = 25, sort_by: str | None = None, sort_order: str = "asc", search: str | None = None):
    items = filter_search(list_units(q=q, station_code=station_code), search or q)
    items = sort_items(items, sort_by if sort_by in unit_sort_map() else None, sort_order)
    page_data = paginate(items, page, page_size)
    return envelope({"items": page_data.items, "pagination": {"total": page_data.total, "page": page_data.page, "page_size": page_data.page_size}}, "ok")


@app.get("/api/works")
def works(q: str | None = None, scope_type: str | None = None, station_code: str | None = None, page: int = 1, page_size: int = 25, sort_by: str | None = None, sort_order: str = "asc", search: str | None = None):
    items = filter_search(list_works(q=q, scope_type=scope_type, station_code=station_code), search or q)
    items = sort_items(items, sort_by if sort_by in work_sort_map() else None, sort_order)
    page_data = paginate(items, page, page_size)
    return envelope({"items": page_data.items, "pagination": {"total": page_data.total, "page": page_data.page, "page_size": page_data.page_size}}, "ok")


@app.get("/api/earnings")
def earnings(q: str | None = None, unit_no: str | None = None, station_code: str | None = None, page: int = 1, page_size: int = 25, sort_by: str | None = None, sort_order: str = "asc", search: str | None = None):
    items = filter_search(list_earnings(q=q, unit_no=unit_no, station_code=station_code), search or q)
    items = sort_items(items, sort_by if sort_by in earnings_sort_map() else None, sort_order)
    page_data = paginate(items, page, page_size)
    return envelope({"items": page_data.items, "pagination": {"total": page_data.total, "page": page_data.page, "page_size": page_data.page_size}}, "ok")
