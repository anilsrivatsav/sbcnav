from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Integer
from database import SessionLocal, engine, is_sqlite_fallback
from models import Base, DataChangeLog, Earning, EarningLink, Station, Unit, Work, WorkLink
from api_utils import envelope, exception_response, filter_search, paginate, sort_items
from services import (
    audit_fields,
    earnings_sort_map,
    get_stats,
    hash_row,
    list_earnings,
    list_stations,
    list_units,
    list_works,
    parse_earnings,
    parse_stations,
    parse_units,
    parse_works,
    row_to_dict,
    split_scopes,
    station_sort_map,
    unit_sort_map,
    upsert_many,
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


@app.get("/api/activity")
def activity(limit: int = 50):
    session = SessionLocal()
    try:
        rows = session.query(DataChangeLog).order_by(DataChangeLog.created_at.desc()).limit(min(limit, 200)).all()
        return envelope([row_to_dict(row) for row in rows], "ok")
    finally:
        session.close()


def _clean_payload(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if value != ""}


def _log_change(session, resource: str, record_key: str | None, action: str, source: str, details: str | None = None) -> None:
    session.add(DataChangeLog(resource=resource, record_key=record_key, action=action, source=source, details=details, created_at=datetime.now(timezone.utc)))


def _csv_from_payload(payload: dict) -> str:
    csv_text = payload.get("csv_text")
    url = payload.get("url")
    if csv_text:
        return csv_text
    if url:
        response = requests.get(url, timeout=90)
        response.raise_for_status()
        return response.text
    raise HTTPException(status_code=422, detail="csv_text or url is required")


def _parse_import(resource: str, csv_text: str) -> tuple[list[dict], str]:
    if resource == "stations":
        return parse_stations(csv_text), "station_code"
    if resource == "units":
        return parse_units(csv_text), "unit_no"
    if resource == "earnings":
        return parse_earnings(csv_text), "receipt_key"
    if resource == "works":
        return parse_works(csv_text), "project_id"
    raise HTTPException(status_code=404, detail="Unknown import resource")


def _validate_import(resource: str, rows: list[dict], key: str) -> dict:
    errors = []
    seen = set()
    for index, row in enumerate(rows, start=2):
        value = row.get(key)
        if not value:
            errors.append({"row": index, "field": key, "message": f"{key} is required"})
        elif value in seen:
            errors.append({"row": index, "field": key, "message": f"Duplicate {key} in import"})
        seen.add(value)
    return {"resource": resource, "rows": len(rows), "valid": not errors, "errors": errors[:100]}


def _apply_import(resource: str, rows: list[dict]) -> int:
    now = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
        with session.begin():
            if resource == "stations":
                station_rows = [{**row, **audit_fields(now), "source_hash": hash_row("station", row)} for row in rows]
                count = upsert_many(session, Station, station_rows, [Station.station_code], [c.name for c in Station.__table__.columns if c.name not in {"station_code", "created_at", "first_seen_at"}])
                _log_change(session, resource, None, "import", "csv", f"{count} rows")
                return count
            if resource == "units":
                unit_rows = [{**row, **audit_fields(now), "source_hash": hash_row("unit", row)} for row in rows]
                count = upsert_many(session, Unit, unit_rows, [Unit.unit_no], [c.name for c in Unit.__table__.columns if c.name not in {"unit_no", "created_at", "first_seen_at"}])
                _log_change(session, resource, None, "import", "csv", f"{count} rows")
                return count
            if resource == "works":
                work_rows = [{**row, **audit_fields(now), "source_hash": hash_row("work", row)} for row in rows]
                count = upsert_many(session, Work, work_rows, [Work.project_id], [c.name for c in Work.__table__.columns if c.name not in {"work_key", "project_id", "created_at", "first_seen_at"}])
                for project_id in [row["project_id"] for row in rows if row.get("project_id")]:
                    work = session.query(Work).filter(Work.project_id == project_id).one_or_none()
                    if work:
                        _replace_work_links(session, work)
                _log_change(session, resource, None, "import", "csv", f"{count} rows")
                return count
            if resource == "earnings":
                earning_rows = [{**row, **audit_fields(now), "source_hash": hash_row("earning", row)} for row in rows]
                count = upsert_many(session, Earning, earning_rows, [Earning.receipt_key], [c.name for c in Earning.__table__.columns if c.name not in {"earning_key", "receipt_key", "created_at", "first_seen_at"}])
                for receipt_key in [row["receipt_key"] for row in rows if row.get("receipt_key")]:
                    earning = session.query(Earning).filter(Earning.receipt_key == receipt_key).one_or_none()
                    if earning:
                        _replace_earning_link(session, earning)
                _log_change(session, resource, None, "import", "csv", f"{count} rows")
                return count
        raise HTTPException(status_code=404, detail="Unknown import resource")
    finally:
        session.close()


def _assign_columns(obj, payload: dict, *, skip: set[str]) -> None:
    columns = {column.name: column for column in obj.__table__.columns}
    for key, value in _clean_payload(payload).items():
        if key in columns and key not in skip:
            if isinstance(columns[key].type, Integer) and value is not None:
                value = int(value)
            setattr(obj, key, value)
    now = datetime.now(timezone.utc)
    if "updated_at" in columns:
        obj.updated_at = now
    if "last_seen_at" in columns:
        obj.last_seen_at = now
    if "is_active" in columns and getattr(obj, "is_active", None) is None:
        obj.is_active = True


def _station_codes(session) -> set[str]:
    return {code for (code,) in session.query(Station.station_code).all()}


def _unit_codes(session) -> set[str]:
    return {unit_no for (unit_no,) in session.query(Unit.unit_no).all()}


def _replace_work_links(session, work: Work) -> None:
    session.query(WorkLink).filter(WorkLink.project_id == work.project_id).delete()
    station_codes = _station_codes(session)
    scopes = split_scopes(work.block_section_station or "")
    links = []
    if not scopes:
        links.append(WorkLink(project_id=work.project_id, scope_type="Other", scope_value=work.block_section_station, station_code=None, match_status="Unparsed"))
    for scope in scopes:
        if scope["scope_type"] == "Station":
            code = scope["station_code"]
            links.append(WorkLink(project_id=work.project_id, scope_type="Station", scope_value=scope["scope_value"], station_code=code, match_status="Matched" if code in station_codes else "Missing station"))
        else:
            links.append(WorkLink(project_id=work.project_id, scope_type=scope["scope_type"], scope_value=scope["scope_value"], station_code=None, match_status=scope["scope_type"]))
    session.add_all(links)


def _replace_earning_link(session, earning: Earning) -> None:
    session.query(EarningLink).filter(EarningLink.receipt_key == earning.receipt_key).delete()
    unit_codes = _unit_codes(session)
    session.add(EarningLink(
        receipt_key=earning.receipt_key,
        unit_no=earning.unit_no,
        station_code=earning.station_code,
        match_status="Matched" if earning.unit_no in unit_codes else "Missing unit",
    ))


def _create_row(model, payload: dict, required_key: str):
    payload = _clean_payload(payload)
    if not payload.get(required_key):
        raise HTTPException(status_code=422, detail=f"{required_key} is required")
    now = datetime.now(timezone.utc)
    columns = {column.name for column in model.__table__.columns}
    if "created_at" in columns:
        payload.setdefault("created_at", now)
    if "updated_at" in columns:
        payload.setdefault("updated_at", now)
    if "first_seen_at" in columns:
        payload.setdefault("first_seen_at", now)
    if "last_seen_at" in columns:
        payload.setdefault("last_seen_at", now)
    if "is_active" in columns:
        payload.setdefault("is_active", True)
    if "source_hash" in columns:
        payload.setdefault("source_hash", hash_row(model.__tablename__, payload))
    allowed = {key: value for key, value in payload.items() if key in columns}
    for key, value in list(allowed.items()):
        column = model.__table__.columns[key]
        if isinstance(column.type, Integer) and value is not None:
            allowed[key] = int(value)
    return model(**allowed)


@app.post("/api/import/{resource}/validate")
def validate_import(resource: str, payload: dict):
    try:
        rows, key = _parse_import(resource, _csv_from_payload(payload))
        return envelope(_validate_import(resource, rows, key), "validated")
    except requests.RequestException as exc:
        raise HTTPException(status_code=400, detail=f"Unable to fetch import URL: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/import/{resource}")
def import_resource(resource: str, payload: dict):
    try:
        rows, key = _parse_import(resource, _csv_from_payload(payload))
        validation = _validate_import(resource, rows, key)
        if not validation["valid"]:
            raise HTTPException(status_code=422, detail=validation)
        count = _apply_import(resource, rows)
        return envelope({"resource": resource, "rows": len(rows), "upserted": count}, "imported")
    except requests.RequestException as exc:
        raise HTTPException(status_code=400, detail=f"Unable to fetch import URL: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/stations", status_code=201)
def create_station(payload: dict):
    session = SessionLocal()
    try:
        with session.begin():
            if session.get(Station, payload.get("station_code")):
                raise HTTPException(status_code=409, detail="Station already exists")
            station = _create_row(Station, payload, "station_code")
            session.add(station)
            _log_change(session, "stations", station.station_code, "create", "manual")
        return envelope(row_to_dict(station), "station created")
    finally:
        session.close()


@app.put("/api/stations/{station_code}")
def update_station(station_code: str, payload: dict):
    session = SessionLocal()
    try:
        with session.begin():
            station = session.get(Station, station_code)
            if not station:
                raise HTTPException(status_code=404, detail="Station not found")
            _assign_columns(station, payload, skip={"station_code", "created_at", "first_seen_at"})
            _log_change(session, "stations", station.station_code, "update", "manual")
        return envelope(row_to_dict(station), "station updated")
    finally:
        session.close()


@app.delete("/api/stations/{station_code}")
def delete_station(station_code: str):
    session = SessionLocal()
    try:
        with session.begin():
            station = session.get(Station, station_code)
            if not station:
                raise HTTPException(status_code=404, detail="Station not found")
            session.delete(station)
            _log_change(session, "stations", station_code, "delete", "manual")
        return envelope({"station_code": station_code}, "station deleted")
    finally:
        session.close()


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


@app.post("/api/units", status_code=201)
def create_unit(payload: dict):
    session = SessionLocal()
    try:
        with session.begin():
            if session.get(Unit, payload.get("unit_no")):
                raise HTTPException(status_code=409, detail="Unit already exists")
            unit = _create_row(Unit, payload, "unit_no")
            session.add(unit)
            _log_change(session, "units", unit.unit_no, "create", "manual")
        return envelope(row_to_dict(unit), "unit created")
    finally:
        session.close()


@app.put("/api/units/{unit_no}")
def update_unit(unit_no: str, payload: dict):
    session = SessionLocal()
    try:
        with session.begin():
            unit = session.get(Unit, unit_no)
            if not unit:
                raise HTTPException(status_code=404, detail="Unit not found")
            _assign_columns(unit, payload, skip={"unit_no", "created_at", "first_seen_at"})
            _log_change(session, "units", unit.unit_no, "update", "manual")
        return envelope(row_to_dict(unit), "unit updated")
    finally:
        session.close()


@app.delete("/api/units/{unit_no}")
def delete_unit(unit_no: str):
    session = SessionLocal()
    try:
        with session.begin():
            unit = session.get(Unit, unit_no)
            if not unit:
                raise HTTPException(status_code=404, detail="Unit not found")
            session.query(EarningLink).filter(EarningLink.unit_no == unit_no).update({"unit_no": None, "match_status": "Missing unit"})
            session.delete(unit)
            _log_change(session, "units", unit_no, "delete", "manual")
        return envelope({"unit_no": unit_no}, "unit deleted")
    finally:
        session.close()


@app.get("/api/works")
def works(q: str | None = None, scope_type: str | None = None, station_code: str | None = None, page: int = 1, page_size: int = 25, sort_by: str | None = None, sort_order: str = "asc", search: str | None = None):
    items = filter_search(list_works(q=q, scope_type=scope_type, station_code=station_code), search or q)
    items = sort_items(items, sort_by if sort_by in work_sort_map() else None, sort_order)
    page_data = paginate(items, page, page_size)
    return envelope({"items": page_data.items, "pagination": {"total": page_data.total, "page": page_data.page, "page_size": page_data.page_size}}, "ok")


@app.post("/api/works", status_code=201)
def create_work(payload: dict):
    session = SessionLocal()
    try:
        with session.begin():
            if session.query(Work).filter(Work.project_id == payload.get("project_id")).one_or_none():
                raise HTTPException(status_code=409, detail="Work already exists")
            work = _create_row(Work, payload, "project_id")
            session.add(work)
            session.flush()
            _replace_work_links(session, work)
            _log_change(session, "works", work.project_id, "create", "manual")
        return envelope(row_to_dict(work), "work created")
    finally:
        session.close()


@app.put("/api/works/{project_id}")
def update_work(project_id: str, payload: dict):
    session = SessionLocal()
    try:
        with session.begin():
            work = session.query(Work).filter(Work.project_id == project_id).one_or_none()
            if not work:
                raise HTTPException(status_code=404, detail="Work not found")
            _assign_columns(work, payload, skip={"work_key", "project_id", "created_at", "first_seen_at"})
            session.flush()
            _replace_work_links(session, work)
            _log_change(session, "works", work.project_id, "update", "manual")
        return envelope(row_to_dict(work), "work updated")
    finally:
        session.close()


@app.delete("/api/works/{project_id}")
def delete_work(project_id: str):
    session = SessionLocal()
    try:
        with session.begin():
            work = session.query(Work).filter(Work.project_id == project_id).one_or_none()
            if not work:
                raise HTTPException(status_code=404, detail="Work not found")
            session.query(WorkLink).filter(WorkLink.project_id == project_id).delete()
            session.delete(work)
            _log_change(session, "works", project_id, "delete", "manual")
        return envelope({"project_id": project_id}, "work deleted")
    finally:
        session.close()


@app.get("/api/earnings")
def earnings(q: str | None = None, unit_no: str | None = None, station_code: str | None = None, page: int = 1, page_size: int = 25, sort_by: str | None = None, sort_order: str = "asc", search: str | None = None):
    items = filter_search(list_earnings(q=q, unit_no=unit_no, station_code=station_code), search or q)
    items = sort_items(items, sort_by if sort_by in earnings_sort_map() else None, sort_order)
    page_data = paginate(items, page, page_size)
    return envelope({"items": page_data.items, "pagination": {"total": page_data.total, "page": page_data.page, "page_size": page_data.page_size}}, "ok")


@app.post("/api/earnings", status_code=201)
def create_earning(payload: dict):
    session = SessionLocal()
    try:
        with session.begin():
            payload = _clean_payload(payload)
            payload.setdefault("receipt_key", hash_row("earning", payload))
            if session.query(Earning).filter(Earning.receipt_key == payload["receipt_key"]).one_or_none():
                raise HTTPException(status_code=409, detail="Earning already exists")
            earning = _create_row(Earning, payload, "receipt_key")
            session.add(earning)
            session.flush()
            _replace_earning_link(session, earning)
            _log_change(session, "earnings", earning.receipt_key, "create", "manual")
        return envelope(row_to_dict(earning), "earning created")
    finally:
        session.close()


@app.put("/api/earnings/{receipt_key}")
def update_earning(receipt_key: str, payload: dict):
    session = SessionLocal()
    try:
        with session.begin():
            earning = session.query(Earning).filter(Earning.receipt_key == receipt_key).one_or_none()
            if not earning:
                raise HTTPException(status_code=404, detail="Earning not found")
            _assign_columns(earning, payload, skip={"earning_key", "receipt_key", "created_at", "first_seen_at"})
            session.flush()
            _replace_earning_link(session, earning)
            _log_change(session, "earnings", earning.receipt_key, "update", "manual")
        return envelope(row_to_dict(earning), "earning updated")
    finally:
        session.close()


@app.delete("/api/earnings/{receipt_key}")
def delete_earning(receipt_key: str):
    session = SessionLocal()
    try:
        with session.begin():
            earning = session.query(Earning).filter(Earning.receipt_key == receipt_key).one_or_none()
            if not earning:
                raise HTTPException(status_code=404, detail="Earning not found")
            session.query(EarningLink).filter(EarningLink.receipt_key == receipt_key).delete()
            session.delete(earning)
            _log_change(session, "earnings", receipt_key, "delete", "manual")
        return envelope({"receipt_key": receipt_key}, "earning deleted")
    finally:
        session.close()
