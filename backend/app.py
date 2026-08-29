from __future__ import annotations

import logging
import os
import re
import csv
import io
import json
import asyncio
import time
from uuid import uuid4
from datetime import date, datetime, timedelta, timezone

import requests
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from sqlalchemy import Integer, extract, func
from ai_service import query_ai
from database import SessionLocal, engine, is_sqlite_fallback
from models import (
    AmenityNorm,
    Base,
    CateringSyncRun,
    CommercialContract,
    CommercialContractPayment,
    CommercialContractStationLink,
    DataChangeLog,
    ReportPreset,
    ReportRun,
    Earning,
    EarningLink,
    PassengerAmenityWork,
    PlatformExtensionSummary,
    PlatformDetail,
    Station,
    StationMonthlyMetric,
    StationInfra,
    StationPlatformExtensionStatus,
    TrolleyPath,
    Unit,
    WheelChairAvailability,
    Work,
    WorkProgressUpdate,
    WorkProgressPhoto,
    WorkExpenditureUpdate,
    WorkLink,
)
from import_catering_workbook import (
    apply_import as apply_catering_import,
    load_source as load_catering_source,
    reconcile as reconcile_catering_source,
    verify as verify_catering_import,
)
from api_utils import envelope, exception_response, filter_search, paginate, sort_items
from inspection_router import router as inspection_router
from services import (
    audit_fields,
    earnings_sort_map,
    commercial_contract_sort_map,
    get_reports,
    get_commercial_contract_detail,
    get_commercial_contract_reports,
    get_contract_alerts,
    get_action_centre,
    get_data_centre_status,
    get_passenger_amenity_reports,
    get_station_detail,
    get_stats,
    get_work_monitoring,
    hash_row,
    is_available_unit,
    list_earnings,
    list_commercial_contracts,
    list_passenger_amenities,
    list_stations,
    list_units,
    list_works,
    parse_earnings,
    parse_commercial_contract_workbook,
    parse_amenity_norms,
    parse_combined_accessibility,
    parse_fob_works,
    parse_pf_extension_works,
    parse_platform_extension_workbook,
    parse_platform_details,
    parse_stations,
    parse_station_infra,
    parse_trolley_paths,
    parse_units,
    parse_wheel_chairs,
    parse_works,
    parse_works_xlsx,
    passenger_amenity_sort_map,
    row_to_dict,
    split_scopes,
    station_sort_map,
    unit_sort_map,
    upsert_many,
    work_sort_map,
)
from contract_registry import (
    backfill_legacy_contracts,
    get_registry_contract,
    import_eauction_workbook,
    list_registry_contracts,
    registry_summary,
)
from data_quality import check_postgres_consistency, resolve_postgres_inconsistency

try:
    import redis
except ImportError:  # pragma: no cover - optional locally; Render installs it from requirements
    redis = None
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rail_dashboard.api")

BOOTSTRAP_CACHE_KEY = "sbcnav:dashboard-bootstrap:v1"
BOOTSTRAP_CACHE_TTL = int(os.getenv("DASHBOARD_CACHE_TTL_SECONDS", "60"))
_bootstrap_memory_cache: dict[str, tuple[float, dict]] = {}
_redis_client = None
if redis and os.getenv("REDIS_URL"):
    try:
        _redis_client = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
        _redis_client.ping()
        logger.info("Dashboard bootstrap Redis cache enabled")
    except Exception as exc:
        _redis_client = None
        logger.warning("Redis cache unavailable; using process memory cache: %s", exc)


def _invalidate_bootstrap_cache() -> None:
    _bootstrap_memory_cache.clear()
    if _redis_client:
        try:
            _redis_client.delete(BOOTSTRAP_CACHE_KEY)
        except Exception:
            logger.warning("Unable to invalidate Redis dashboard cache", exc_info=True)


def _bootstrap_cache_get() -> dict | None:
    if _redis_client:
        try:
            cached = _redis_client.get(BOOTSTRAP_CACHE_KEY)
            return json.loads(cached) if cached else None
        except Exception:
            logger.warning("Unable to read Redis dashboard cache", exc_info=True)
    entry = _bootstrap_memory_cache.get(BOOTSTRAP_CACHE_KEY)
    if entry and entry[0] > time.time():
        return entry[1]
    return None


def _bootstrap_cache_set(payload: dict) -> None:
    if _redis_client:
        try:
            _redis_client.setex(BOOTSTRAP_CACHE_KEY, BOOTSTRAP_CACHE_TTL, json.dumps(payload, default=str))
            return
        except Exception:
            logger.warning("Unable to write Redis dashboard cache", exc_info=True)
    _bootstrap_memory_cache[BOOTSTRAP_CACHE_KEY] = (time.time() + BOOTSTRAP_CACHE_TTL, payload)

PA_INFRA_SPREADSHEET_ID = "1UdRgQQPEkak1fUTuVH7jIn5R4sE3szAhM4VZJOdFIOU"
SANCTIONED_WORKS_SPREADSHEET_ID = "1rJbfhcnEVuGMwGkT8yBObb9Bk5Hx0uU224EGxfplGRc"
SANCTIONED_WORKS_GID = "590791228"
CATERING_SPREADSHEET_ID = os.getenv("CATERING_SPREADSHEET_ID", "1JSlf6FOZMlSrb2wiAcb0LTk2BZYDPzvC98gNLfUDR-0")
DEFAULT_PF_EXTENSION_WORKBOOK = r"C:\Users\CMI PA\Downloads\FOB & PF Extn Works (1).xlsx"
PA_INFRA_TABS = {
    "norms": {"gid": "596063365", "model": AmenityNorm, "parser": parse_amenity_norms, "conflict": ["category", "amenity", "norm"], "skip": {"norm_key"}},
    "infra": {"gid": "652681143", "model": StationInfra, "parser": parse_station_infra, "conflict": ["station_code"], "skip": {"infra_key"}},
    "platforms": {"gid": "244744816", "model": PlatformDetail, "parser": parse_platform_details, "conflict": ["station_code", "platform"], "skip": {"platform_key"}},
    "wheelchairs": {"gid": "658113254", "model": WheelChairAvailability, "parser": parse_wheel_chairs, "conflict": ["station_code"], "skip": {"wheel_chair_key"}},
    "trolley": {"gid": "977860642", "model": TrolleyPath, "parser": parse_trolley_paths, "conflict": ["station_code"], "skip": {"trolley_path_key"}},
    "fob_works": {"gid": "1044004842", "model": PassengerAmenityWork, "parser": parse_fob_works, "conflict": ["work_type", "station_code", "work_name"], "skip": {"pa_work_key"}},
    "pf_extension": {"gid": "149152202", "model": PassengerAmenityWork, "parser": lambda text: parse_pf_extension_works(text, "PF Extension"), "conflict": ["work_type", "station_code", "work_name"], "skip": {"pa_work_key"}},
    "has": {"gid": "1583406196", "model": PassengerAmenityWork, "parser": lambda text: parse_pf_extension_works(text, "HAS"), "conflict": ["work_type", "station_code", "work_name"], "skip": {"pa_work_key"}},
    "combined_accessibility": {"gid": "467658571", "model": StationPlatformExtensionStatus, "parser": parse_combined_accessibility, "conflict": ["station_code"], "skip": {"status_key"}},
}
PA_STATION_CODE_ALIASES = {"GNBH": "GNB"}


DEFAULT_CORS_ORIGINS = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "https://sbcnav-38t2.vercel.app",
    "https://sbcnav.vercel.app",
    "https://sbcnav-38t2-2doxwtr6h-anil-b-hs-projects.vercel.app",
]
configured_cors_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

app = FastAPI(title="Rail Dashboard API")
app.include_router(inspection_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_cors_origins or DEFAULT_CORS_ORIGINS,
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX") or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    try:
        response = await call_next(request)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/"):
            _invalidate_bootstrap_cache()
        logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
        return response
    except Exception as exc:
        return exception_response(exc)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content=envelope(None, exc.detail, False))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=envelope({"errors": exc.errors()}, "Validation failed", False))


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    app.state.report_worker = asyncio.create_task(_scheduled_report_worker())

    if is_sqlite_fallback():
        logger.info("SQLite fallback detected; local cache available.")
    else:
        logger.info("API startup complete.")


@app.on_event("shutdown")
async def shutdown() -> None:
    worker = getattr(app.state, "report_worker", None)
    if worker:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


@app.get("/api/health")
def health() -> dict[str, object]:
    return envelope({"status": "ok", "schema_version": "0029_uts_prs_station_metrics"}, "ok")


@app.get("/api/activity")
def activity(limit: int = 50):
    session = SessionLocal()
    try:
        rows = session.query(DataChangeLog).order_by(DataChangeLog.created_at.desc()).limit(min(limit, 200)).all()
        return envelope([row_to_dict(row) for row in rows], "ok")
    finally:
        session.close()


def _catering_export_url() -> str:
    return f"https://docs.google.com/spreadsheets/d/{CATERING_SPREADSHEET_ID}/export?format=xlsx"


def _record_failed_catering_sync(started_at: datetime, message: str) -> None:
    session = SessionLocal()
    try:
        with session.begin():
            session.add(CateringSyncRun(
                source_spreadsheet_id=CATERING_SPREADSHEET_ID,
                status="failed",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=message[:4000],
            ))
    except Exception:
        logger.exception("Unable to record failed catering sync")
    finally:
        session.close()


@app.get("/api/catering/sync-history")
def catering_sync_history(limit: int = 10):
    session = SessionLocal()
    try:
        rows = (
            session.query(CateringSyncRun)
            .order_by(CateringSyncRun.started_at.desc())
            .limit(max(1, min(limit, 50)))
            .all()
        )
        return envelope([row_to_dict(row) for row in rows], "ok")
    finally:
        session.close()


@app.post("/api/catering/sync")
def sync_catering_from_google_sheet(dry_run: bool = False):
    started_at = datetime.now(timezone.utc)
    try:
        response = requests.get(_catering_export_url(), timeout=120)
        response.raise_for_status()
        if len(response.content) < 1000 or not response.content.startswith(b"PK"):
            raise ValueError("Google Sheets did not return a valid XLSX workbook")

        units, raw_earnings, notes = load_catering_source(response.content)
        earnings, report = reconcile_catering_source(units, raw_earnings)
        report["source"].update(notes)
        report["source"]["spreadsheet_id"] = CATERING_SPREADSHEET_ID
        report["source"]["tabs"] = ["UNITS BASE DATA", "EARNINGS BASE DATA"]
        report["mode"] = "dry-run" if dry_run else "apply"
        if not dry_run:
            apply_catering_import(
                "Google Sheets BASE DATA",
                units,
                earnings,
                report,
                spreadsheet_id=CATERING_SPREADSHEET_ID,
            )
            verify_catering_import(report)
        return envelope(report, "Catering data validated" if dry_run else "Catering data synchronized")
    except requests.RequestException as exc:
        message = f"Unable to download catering Google Sheet: {exc}"
        _record_failed_catering_sync(started_at, message)
        raise HTTPException(status_code=502, detail=message) from exc
    except (ValueError, RuntimeError) as exc:
        message = str(exc)
        _record_failed_catering_sync(started_at, message)
        raise HTTPException(status_code=422, detail=message) from exc
    except Exception as exc:
        logger.exception("Catering synchronization failed")
        message = f"Catering synchronization failed: {exc}"
        _record_failed_catering_sync(started_at, message)
        raise HTTPException(status_code=500, detail=message) from exc


@app.post("/api/ai/query")
def ai_query(payload: dict):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object")
    question = str(payload.get("question") or "").strip()
    context = payload.get("context") or {}
    if context is None:
        context = {}
    if not isinstance(context, dict):
        raise HTTPException(status_code=422, detail="context must be an object")
    if not question:
        raise HTTPException(status_code=422, detail="question is required")
    if len(question) > 2000:
        raise HTTPException(status_code=422, detail="question must be 2000 characters or fewer")
    try:
        return envelope(query_ai(question, context), "ok")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("AI query failed")
        raise HTTPException(status_code=500, detail=f"AI query failed: {exc}") from exc


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


def _import_preview(resource: str, rows: list[dict], key: str) -> dict:
    """Return a non-mutating reconciliation preview for CSV imports."""
    models = {
        "stations": Station,
        "units": Unit,
        "earnings": Earning,
        "works": Work,
    }
    model = models[resource]
    hash_names = {
        "stations": "station",
        "units": "unit",
        "earnings": "earning",
        "works": "work",
    }
    source = {}
    duplicate_keys = []
    for row in rows:
        value = str(row.get(key) or "").strip()
        if not value:
            continue
        if value in source:
            duplicate_keys.append(value)
            continue
        source[value] = row

    session = SessionLocal()
    try:
        existing_rows = session.query(model).all()
        existing = {
            str(getattr(row, key)): row
            for row in existing_rows
            if getattr(row, key, None)
        }
        added = sorted(set(source) - set(existing))
        removed = sorted(set(existing) - set(source))
        changed = sorted(
            value
            for value, row in source.items()
            if value in existing
            and getattr(existing[value], "source_hash", None) != hash_row(hash_names[resource], row)
        )
        unmatched = []
        if resource == "units":
            station_codes = {row[0] for row in session.query(Station.station_code).all()}
            unmatched = [
                {"row": index + 2, "key": row.get(key), "reason": "station not found"}
                for index, row in enumerate(rows)
                if row.get("station_code") and row.get("station_code") not in station_codes
            ]
        elif resource == "earnings":
            unit_codes = {row[0] for row in session.query(Unit.unit_no).all()}
            station_codes = {row[0] for row in session.query(Station.station_code).all()}
            unmatched = [
                {"row": index + 2, "key": row.get(key), "reason": reason}
                for index, row in enumerate(rows)
                for reason in (
                    "unit not found" if row.get("unit_no") and row.get("unit_no") not in unit_codes else None,
                    "station not found" if row.get("station_code") and row.get("station_code") not in station_codes else None,
                )
                if reason
            ]
        elif resource == "works":
            unmatched = [
                {"row": index + 2, "key": row.get(key), "reason": "no station or recognized scope"}
                for index, row in enumerate(rows)
                if not row.get("station_code") and not row.get("block_section_station") and not row.get("section")
            ]
        return {
            "source_count": len(rows),
            "postgres_count": len(existing),
            "removal_policy": "Existing PostgreSQL rows are preserved; removed keys are preview-only.",
            "added": {"count": len(added), "keys": added[:100]},
            "changed": {"count": len(changed), "keys": changed[:100]},
            "removed": {"count": len(removed), "keys": removed[:100]},
            "duplicates": {"count": len(duplicate_keys), "keys": sorted(set(duplicate_keys))[:100]},
            "unmatched": {"count": len(unmatched), "rows": unmatched[:100]},
        }
    finally:
        session.close()


def _apply_import(resource: str, rows: list[dict]) -> int:
    now = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
        with session.begin():
            if resource == "stations":
                station_rows = [{**row, **audit_fields(now), "source_hash": hash_row("station", row)} for row in rows]
                count = upsert_many(session, Station, station_rows, [Station.station_code], [c.name for c in Station.__table__.columns if c.name not in {"station_code", "created_at", "first_seen_at", "abss_flag", "redevelopment_flag"}])
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
                # Imports do not carry the derived duplicate counter. Keep the
                # database invariant intact when an existing earning is
                # re-imported as well as when it is inserted for the first time.
                earning_rows = [
                    {
                        **{key: (None if value == "" else value) for key, value in row.items()},
                        "duplicate_count": 1,
                        **audit_fields(now),
                        "source_hash": hash_row("earning", row),
                    }
                    for row in rows
                ]
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


def _replace_all_works(rows: list[dict]) -> int:
    now = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
        with session.begin():
            existing_tdc = {
                row.project_id: row.tdc
                for row in session.query(Work).all()
                if row.project_id and row.tdc
            }
            work_rows = [
                {
                    **row,
                    "tdc": row.get("tdc") or existing_tdc.get(row.get("project_id")),
                    **audit_fields(now),
                    "source_hash": hash_row("work", row),
                }
                for row in rows
            ]
            progress_history = [
                {
                    "project_id": row.project_id,
                    "update_date": row.update_date,
                    "progress_percent": row.progress_percent,
                    "status": row.status,
                    "physical_progress": row.physical_progress,
                    "financial_progress": row.financial_progress,
                    "expenditure_upto_date": row.expenditure_upto_date,
                    "tdc": row.tdc,
                    "remarks": row.remarks,
                    "source": row.source,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
                for row in session.query(WorkProgressUpdate).all()
            ]
            session.query(WorkLink).delete(synchronize_session=False)
            session.query(Work).delete(synchronize_session=False)
            session.add_all(Work(**row) for row in work_rows)
            session.flush()
            valid_projects = {row["project_id"] for row in work_rows}
            session.add_all(
                WorkProgressUpdate(**row)
                for row in progress_history
                if row["project_id"] in valid_projects
            )
            session.flush()
            for work in session.query(Work).all():
                _replace_work_links(session, work)
            _log_change(session, "works", None, "replace_import", "google_sheet", f"{len(work_rows)} rows")
        return len(work_rows)
    finally:
        session.close()


def _works_import_diff(rows: list[dict]) -> dict:
    """Compare a parsed source register with PostgreSQL without changing data."""
    source_by_project: dict[str, dict] = {}
    duplicate_project_ids: list[str] = []
    missing_project_rows: list[int] = []
    for index, row in enumerate(rows, start=1):
        project_id = str(row.get("project_id") or "").strip()
        if not project_id:
            missing_project_rows.append(index)
            continue
        if project_id in source_by_project:
            duplicate_project_ids.append(project_id)
            continue
        source_by_project[project_id] = row

    session = SessionLocal()
    try:
        existing = {
            str(row.project_id): row
            for row in session.query(Work).all()
            if row.project_id
        }
        added = sorted(set(source_by_project) - set(existing))
        removed = sorted(set(existing) - set(source_by_project))
        changed = sorted(
            project_id
            for project_id, row in source_by_project.items()
            if project_id in existing
            and existing[project_id].source_hash != hash_row("work", row)
        )
        validation_errors = []
        if missing_project_rows:
            validation_errors.append(f"Missing Project ID in source rows: {missing_project_rows[:20]}")
        if duplicate_project_ids:
            validation_errors.append(f"Duplicate Project IDs: {sorted(set(duplicate_project_ids))[:20]}")
        return {
            "source_count": len(rows),
            "unique_source_count": len(source_by_project),
            "postgres_count": len(existing),
            "added": {"count": len(added), "project_ids": added[:100]},
            "changed": {"count": len(changed), "project_ids": changed[:100]},
            "removed": {"count": len(removed), "project_ids": removed[:100]},
            "validation": {
                "valid": not validation_errors and bool(source_by_project),
                "errors": validation_errors,
            },
        }

    finally:
        session.close()


def _apply_commercial_contract_import(parsed: dict[str, list[dict]]) -> dict:
    now = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
        with session.begin():
            contract_rows = [
                {**row, **audit_fields(now), "source_hash": hash_row("commercial_contract", row)}
                for row in parsed.get("contracts", [])
            ]
            contract_count = upsert_many(
                session,
                CommercialContract,
                contract_rows,
                [CommercialContract.contract_name],
                [column.name for column in CommercialContract.__table__.columns if column.name not in {"contract_key", "contract_name", "created_at", "first_seen_at"}],
            )

            contracts_by_name = {
                contract.contract_name: contract.contract_key
                for contract in session.query(CommercialContract).filter(CommercialContract.contract_name.in_([row["contract_name"] for row in contract_rows])).all()
            }
            contract_keys = list(contracts_by_name.values())
            if contract_keys:
                session.query(CommercialContractStationLink).filter(CommercialContractStationLink.contract_key.in_(contract_keys)).delete(synchronize_session=False)
                session.query(CommercialContractPayment).filter(CommercialContractPayment.contract_key.in_(contract_keys)).delete(synchronize_session=False)

            link_rows = []
            for row in parsed.get("links", []):
                contract_key = contracts_by_name.get(row.get("contract_name"))
                if not contract_key:
                    continue
                link_rows.append({
                    "contract_key": contract_key,
                    "station_code": row.get("station_code"),
                    "raw_station_value": row.get("raw_station_value"),
                    "match_type": row.get("match_type"),
                    "match_status": row.get("match_status"),
                })
            session.add_all(CommercialContractStationLink(**row) for row in link_rows)

            payment_rows = []
            for row in parsed.get("payments", []):
                contract_key = contracts_by_name.get(row.get("contract_name"))
                if not contract_key:
                    continue
                payment_payload = {
                    "contract_key": contract_key,
                    "payment_month": row.get("payment_month"),
                    "source_column": row.get("source_column"),
                    "amount_due": row.get("amount_due"),
                    "amount_paid": row.get("amount_paid"),
                    "payment_status": row.get("payment_status"),
                    **audit_fields(now),
                    "source_hash": hash_row("commercial_contract_payment", row),
                }
                payment_rows.append(payment_payload)
            session.add_all(CommercialContractPayment(**row) for row in payment_rows if row.get("payment_month"))

            _log_change(session, "commercial_contracts", None, "import", "xlsx", f"{contract_count} contracts, {len(link_rows)} links, {len(payment_rows)} payments")
        return {
            "contracts": len(contract_rows),
            "upserted": contract_count,
            "station_links": len(link_rows),
            "payments": len(payment_rows),
        }
    finally:
        session.close()


def _pa_export_url(gid: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{PA_INFRA_SPREADSHEET_ID}/export?format=csv&gid={gid}"


def _sanctioned_works_export_url() -> str:
    # XLSX preserves the complete worksheet, including rows hidden by a Google
    # Sheets filter and numeric cells. The CSV view is not a full-register import.
    return f"https://docs.google.com/spreadsheets/d/{SANCTIONED_WORKS_SPREADSHEET_ID}/export?format=xlsx"


def _pa_station_code_set(session) -> set[str]:
    station_rows = session.query(Station.station_code).filter(
        Station.is_active.is_(True),
        func.lower(func.trim(Station.categorisation)).notin_(("", "test", "non-commercial")),
    ).all()
    return {str(code or "").strip().upper() for (code,) in station_rows}


def _canonical_pa_station_rows(session, rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Keep import rows linked to the active 132-station commercial register."""
    if not any("station_code" in row for row in rows):
        return rows, []
    valid_codes = _pa_station_code_set(session)
    canonical = []
    rejected = []
    for source_row in rows:
        row = dict(source_row)
        source_code = str(row.get("station_code") or "").strip().upper()
        station_code = PA_STATION_CODE_ALIASES.get(source_code, source_code)
        if not station_code or station_code not in valid_codes:
            rejected.append(source_code or "<blank>")
            continue
        row["station_code"] = station_code
        canonical.append(row)
    return canonical, sorted(set(rejected))


def _apply_pa_rows(session, tab_key: str, rows: list[dict]) -> tuple[int, int, list[str]]:
    config = PA_INFRA_TABS[tab_key]
    model = config["model"]
    now = datetime.now(timezone.utc)
    rows, rejected = _canonical_pa_station_rows(session, rows)
    if hasattr(model, "station_code"):
        valid_codes = _pa_station_code_set(session)
        if valid_codes:
            session.query(model).filter(
                model.station_code.is_not(None),
                ~model.station_code.in_(valid_codes),
                model.is_active.is_(True),
            ).update({model.is_active: False, model.updated_at: now}, synchronize_session=False)
    prepared = [{**row, **audit_fields(now), "source_hash": hash_row(f"pa_{tab_key}", row)} for row in rows]
    conflict_cols = [getattr(model, name) for name in config["conflict"]]
    skip = set(config["skip"]) | set(config["conflict"]) | {"created_at", "first_seen_at"}
    update_cols = [column.name for column in model.__table__.columns if column.name not in skip]
    return upsert_many(session, model, prepared, conflict_cols, update_cols), len(rows), rejected


def _import_passenger_amenity_tabs(tab: str = "all") -> dict:
    selected = PA_INFRA_TABS.keys() if tab == "all" else [tab]
    unknown = [item for item in selected if item not in PA_INFRA_TABS]
    if unknown:
        raise HTTPException(status_code=404, detail=f"Unknown passenger amenity tab: {unknown[0]}")
    results = {}
    session = SessionLocal()
    try:
        with session.begin():
            for tab_key in selected:
                config = PA_INFRA_TABS[tab_key]
                response = requests.get(_pa_export_url(config["gid"]), timeout=90)
                response.raise_for_status()
                rows = config["parser"](response.text)
                count, accepted_count, rejected = _apply_pa_rows(session, tab_key, rows)
                results[tab_key] = {"rows": accepted_count, "upserted": count, "rejected_station_codes": rejected}
            _log_change(session, "passenger_amenities", None, "import", "google_sheet", str(results))
        return results
    finally:
        session.close()


def _preview_passenger_amenity_tabs(tab: str = "all") -> dict:
    """Fetch PA source tabs and report a non-mutating reconciliation preview."""
    def key_value(value) -> str:
        return str(value or "").strip().casefold()

    selected = list(PA_INFRA_TABS.keys()) if tab == "all" else [tab]
    unknown = [item for item in selected if item not in PA_INFRA_TABS]
    if unknown:
        raise HTTPException(status_code=404, detail=f"Unknown passenger amenity tab: {unknown[0]}")

    session = SessionLocal()
    try:
        previews = {}
        for tab_key in selected:
            config = PA_INFRA_TABS[tab_key]
            response = requests.get(_pa_export_url(config["gid"]), timeout=90)
            response.raise_for_status()
            rows = config["parser"](response.text)
            rows, rejected = _canonical_pa_station_rows(session, rows)
            model = config["model"]
            conflict_names = config["conflict"]

            existing_rows = session.query(model).filter(model.is_active.is_(True)).all()
            existing = {
                tuple(key_value(getattr(item, name, None)) for name in conflict_names): item
                for item in existing_rows
            }
            source = {
                tuple(key_value(row.get(name)) for name in conflict_names): row
                for row in rows
            }
            added_keys = [key for key in source if key not in existing]
            removed_keys = [key for key in existing if key not in source]
            changed_keys = [
                key for key, row in source.items()
                if key in existing and hash_row(f"pa_{tab_key}", row) != getattr(existing[key], "source_hash", None)
            ]
            previews[tab_key] = {
                "source_count": len(rows),
                "postgres_count": len(existing_rows),
                "added": {"count": len(added_keys), "sample": [list(key) for key in added_keys[:10]]},
                "changed": {"count": len(changed_keys), "sample": [list(key) for key in changed_keys[:10]]},
                "removed": {"count": len(removed_keys), "sample": [list(key) for key in removed_keys[:10]]},
                "unmatched": {"count": len(rejected), "sample": rejected[:10]},
                "validation": {"valid": not rejected, "errors": [f"Rejected non-canonical station codes: {', '.join(rejected)}"] if rejected else []},
            }
        return {"tabs": previews, "source": "google_sheet", "mode": "preview"}
    finally:
        session.close()


def _import_pf_extension_workbook(path: str) -> dict:
    parsed = parse_platform_extension_workbook(path)
    now = datetime.now(timezone.utc)
    summary_rows = [
        {**row, **audit_fields(now), "source_hash": hash_row("pf_extension_summary", row)}
        for row in parsed["summaries"]
    ]
    session = SessionLocal()
    try:
        with session.begin():
            canonical_statuses, rejected = _canonical_pa_station_rows(session, parsed["statuses"])
            status_rows = [
                {**row, **audit_fields(now), "source_hash": hash_row("pf_extension_status", row)}
                for row in canonical_statuses
            ]
            valid_codes = _pa_station_code_set(session)
            session.query(StationPlatformExtensionStatus).filter(
                ~StationPlatformExtensionStatus.station_code.in_(valid_codes),
                StationPlatformExtensionStatus.is_active.is_(True),
            ).update({
                StationPlatformExtensionStatus.is_active: False,
                StationPlatformExtensionStatus.updated_at: now,
            }, synchronize_session=False)
            summary_count = upsert_many(
                session,
                PlatformExtensionSummary,
                summary_rows,
                [PlatformExtensionSummary.summary_type, PlatformExtensionSummary.category],
                [column.name for column in PlatformExtensionSummary.__table__.columns if column.name not in {"summary_key", "summary_type", "category", "created_at", "first_seen_at"}],
            )
            status_count = upsert_many(
                session,
                StationPlatformExtensionStatus,
                status_rows,
                [StationPlatformExtensionStatus.station_code],
                [column.name for column in StationPlatformExtensionStatus.__table__.columns if column.name not in {"status_key", "station_code", "created_at", "first_seen_at"}],
            )
            _log_change(session, "passenger_amenities", None, "import_pf_extension", "xlsx", f"{summary_count} summaries, {status_count} station statuses")
        return {
            "summary_rows": len(summary_rows),
            "summary_upserted": summary_count,
            "station_status_rows": len(status_rows),
            "station_status_upserted": status_count,
            "rejected_station_codes": rejected,
        }
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


def _ensure_station_placeholder(session, station_code: str, station_codes: set[str]) -> None:
    code = (station_code or "").strip().upper()
    if not code or code in station_codes:
        return
    now = datetime.now(timezone.utc)
    payload = {
        "station_code": code,
        "station_name": f"{code} (missing station master)",
        "source_hash": hash_row("station_placeholder", {"station_code": code}),
        **audit_fields(now),
    }
    session.add(Station(**payload))
    session.flush()
    station_codes.add(code)


def _infer_work_station_codes(session, work: Work, existing_codes: set[str]) -> set[str]:
    short_name = work.short_name_of_work or ""
    work_location_text = short_name
    if " - " in short_name:
        work_location_text = short_name.rsplit(" - ", 1)[1]
    text = work_location_text
    normalized = text.upper()
    found: set[str] = set()
    stations = session.query(Station.station_code, Station.station_name).all()
    for code, name in stations:
        code_text = (code or "").upper().strip()
        if code_text and code_text not in existing_codes and re.search(rf"(?<![A-Z0-9]){re.escape(code_text)}(?![A-Z0-9])", normalized):
            found.add(code_text)
            continue
        name_text = (name or "").upper().strip()
        if len(name_text) >= 5 and code_text not in existing_codes and name_text in normalized:
            found.add(code_text)
    return found


def _unit_codes(session) -> set[str]:
    return {unit_no for (unit_no,) in session.query(Unit.unit_no).all()}


def _replace_work_links(session, work: Work) -> None:
    session.query(WorkLink).filter(WorkLink.project_id == work.project_id).delete()
    station_codes = _station_codes(session)
    scopes = split_scopes(work.block_section_station or "", station_codes)
    links = []
    linked_station_codes = {scope["station_code"] for scope in scopes if scope.get("scope_type") == "Station" and scope.get("station_code")}
    inferred_station_codes = _infer_work_station_codes(session, work, linked_station_codes)
    scopes.extend({"scope_type": "Station", "scope_value": code, "station_code": code} for code in sorted(inferred_station_codes))
    if not scopes:
        links.append(WorkLink(project_id=work.project_id, scope_type="Other", scope_value=work.block_section_station, station_code=None, match_status="Unparsed"))
    for scope in scopes:
        if scope["scope_type"] == "Station":
            code = scope["station_code"]
            was_missing = code not in station_codes
            _ensure_station_placeholder(session, code, station_codes)
            links.append(WorkLink(project_id=work.project_id, scope_type="Station", scope_value=scope["scope_value"], station_code=code, match_status="Missing station master" if was_missing else "Matched"))
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
        validation = _validate_import(resource, rows, key)
        preview = _import_preview(resource, rows, key)
        return envelope({**validation, "preview": preview}, "validated")
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


@app.get("/api/data-centre")
def data_centre():
    return envelope(get_data_centre_status(), "data centre status ready")


@app.get("/api/data-quality/check")
def data_quality_check():
    return envelope(check_postgres_consistency(), "PostgreSQL consistency check complete")


@app.post("/api/data-quality/resolve")
def data_quality_resolve(payload: dict):
    try:
        result = resolve_postgres_inconsistency(
            resolution=str(payload.get("resolution") or ""),
            table_name=payload.get("table"),
            column_name=payload.get("column"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _invalidate_bootstrap_cache()
    return envelope(result, "PostgreSQL inconsistency resolved")


@app.get("/api/action-centre")
def action_centre(station_code: str | None = None, limit: int = 200):
    return envelope(get_action_centre(station_code=station_code, limit=limit), "action centre ready")


@app.get("/api/reports")
def reports():
    return envelope(get_reports(), "ok")


def _bootstrap_page(items: list[dict], sort_key: str | None = None) -> dict:
    rows = list(items or [])
    if sort_key:
        rows.sort(key=lambda row: str(row.get(sort_key) or "").lower())
    return {"items": rows, "pagination": {"total": len(rows), "page": 1, "page_size": len(rows)}}


@app.get("/api/dashboard-bootstrap")
def dashboard_bootstrap(refresh: bool = False):
    """Return the complete PostgreSQL read model in one cacheable response.

    Google Sheets/workbook imports are deliberately not called here. They remain
    explicit Settings actions; this endpoint only reads PostgreSQL and caches the
    assembled response for fast dashboard startup.
    """
    if not refresh:
        cached = _bootstrap_cache_get()
        if cached:
            return envelope({**cached, "cache": "hit"}, "dashboard bootstrap cache hit")

    work_monitoring_data = get_work_monitoring()
    works_rows = work_monitoring_data.get("items") or list_works()
    passenger_amenities = {
        "summary": list_passenger_amenities(kind="summary"),
        "infra": list_passenger_amenities(kind="infra"),
        "platforms": list_passenger_amenities(kind="platforms"),
        "wheelchairs": list_passenger_amenities(kind="wheelchairs"),
        "trolley": list_passenger_amenities(kind="trolley"),
        "works": list_passenger_amenities(kind="pa_works"),
        "pfExtension": list_passenger_amenities(kind="pf_extension"),
        "norms": list_passenger_amenities(kind="norms"),
    }
    payload = {
        "stats": get_stats(),
        "dataCentre": get_data_centre_status(),
        "actionCentre": get_action_centre(limit=500),
        "stations": _bootstrap_page(list_stations(), "station_name"),
        "units": _bootstrap_page(list_units(), "unit_no"),
        "earnings": _bootstrap_page(list_earnings(), "date_of_receipt"),
        "works": _bootstrap_page(works_rows, "project_id"),
        "workMonitoring": {**work_monitoring_data, "items": works_rows},
        "commercialContracts": _bootstrap_page(list_commercial_contracts(), "contract_name"),
        "commercialContractReports": get_commercial_contract_reports(),
        "contractAlerts": get_contract_alerts(),
        "registryContracts": _bootstrap_page(list_registry_contracts(), "contract_name"),
        "reports": get_reports(),
        "passengerAmenities": {
            "summary": _bootstrap_page(passenger_amenities["summary"], "station_code"),
            "infra": _bootstrap_page(passenger_amenities["infra"], "station_code"),
            "platforms": _bootstrap_page(passenger_amenities["platforms"], "station_code"),
            "wheelchairs": _bootstrap_page(passenger_amenities["wheelchairs"], "station_code"),
            "trolley": _bootstrap_page(passenger_amenities["trolley"], "station_code"),
            "works": _bootstrap_page(passenger_amenities["works"], "station_code"),
            "pfExtension": _bootstrap_page(passenger_amenities["pfExtension"], "station_code"),
            "norms": _bootstrap_page(passenger_amenities["norms"], "category"),
            "reports": get_passenger_amenity_reports(passenger_amenities),
        },
    }
    _bootstrap_cache_set(payload)
    return envelope({**payload, "cache": "miss"}, "dashboard bootstrap ready")


def _report_preset_dict(row: ReportPreset) -> dict:
    try:
        filters = json.loads(row.filters_json or "{}")
    except json.JSONDecodeError:
        filters = {}
    return {
        "preset_id": row.preset_id,
        "name": row.name,
        "report_tab": row.report_tab,
        "filters": filters,
        "schedule": row.schedule,
        "is_active": row.is_active,
        "created_by": row.created_by,
        "next_run_at": row.next_run_at.isoformat() if row.next_run_at else None,
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _report_run_dict(row: ReportRun) -> dict:
    return {
        "run_id": row.run_id,
        "preset_id": row.preset_id,
        "status": row.status,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "row_count": row.row_count,
        "error_message": row.error_message,
    }


def _next_report_run(schedule: str | None, now: datetime) -> datetime | None:
    if schedule == "weekly":
        return now + timedelta(days=7)
    if schedule == "monthly":
        return now + timedelta(days=30)
    return None


def _execute_report_preset(preset_id: str) -> dict | None:
    session = SessionLocal()
    try:
        preset = session.get(ReportPreset, preset_id)
        if not preset or not preset.is_active:
            return None
        run = ReportRun(run_id=str(uuid4()), preset_id=preset_id, status="running", generated_at=datetime.now(timezone.utc))
        session.add(run)
        session.commit()
        run_id = run.run_id
    finally:
        session.close()

    try:
        report = get_reports()
        payload = json.dumps(report, default=str)
        session = SessionLocal()
        try:
            with session.begin():
                run = session.get(ReportRun, run_id)
                preset = session.get(ReportPreset, preset_id)
                if run:
                    run.status = "completed"
                    run.report_json = payload
                    run.row_count = len(report.get("license_fee_alerts", {}).get("rows", []))
                if preset:
                    preset.last_run_at = datetime.now(timezone.utc)
                    preset.next_run_at = _next_report_run(preset.schedule, preset.last_run_at)
            return _report_run_dict(run)
        finally:
            session.close()
    except Exception as exc:
        logger.exception("Scheduled report failed for preset %s", preset_id)
        session = SessionLocal()
        try:
            with session.begin():
                run = session.get(ReportRun, run_id)
                if run:
                    run.status = "failed"
                    run.error_message = str(exc)
            return _report_run_dict(run) if run else None
        finally:
            session.close()


async def _scheduled_report_worker() -> None:
    while True:
        await asyncio.sleep(60)
        session = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            preset_ids = [row.preset_id for row in session.query(ReportPreset).filter(
                ReportPreset.is_active.is_(True),
                ReportPreset.schedule.isnot(None),
                ReportPreset.next_run_at.isnot(None),
                ReportPreset.next_run_at <= now,
            ).limit(5).all()]
        finally:
            session.close()
        for preset_id in preset_ids:
            await asyncio.to_thread(_execute_report_preset, preset_id)


@app.get("/api/report-presets")
def report_presets():
    session = SessionLocal()
    try:
        rows = session.query(ReportPreset).filter(ReportPreset.is_active.is_(True)).order_by(ReportPreset.updated_at.desc()).all()
        return envelope([_report_preset_dict(row) for row in rows], "ok")
    finally:
        session.close()


@app.post("/api/report-presets", status_code=201)
def save_report_preset(payload: dict):
    name = str(payload.get("name") or "").strip()
    report_tab = str(payload.get("report_tab") or "overview").strip()
    filters = payload.get("filters") or {}
    schedule = payload.get("schedule")
    if not name or len(name) > 128:
        raise HTTPException(status_code=422, detail="Preset name is required and must be 128 characters or fewer")
    if not isinstance(filters, dict):
        raise HTTPException(status_code=422, detail="filters must be an object")
    if schedule not in {None, "", "weekly", "monthly"}:
        raise HTTPException(status_code=422, detail="schedule must be weekly, monthly, or empty")
    session = SessionLocal()
    try:
        with session.begin():
            row = session.query(ReportPreset).filter(ReportPreset.name == name).one_or_none()
            if not row:
                row = ReportPreset(preset_id=str(uuid4()), name=name, report_tab=report_tab, filters_json=json.dumps(filters), schedule=schedule or None)
                session.add(row)
            else:
                row.report_tab = report_tab
                row.filters_json = json.dumps(filters)
                row.schedule = schedule or None
                row.is_active = True
            row.next_run_at = _next_report_run(row.schedule, datetime.now(timezone.utc)) if row.schedule else None
        return envelope(_report_preset_dict(row), "report preset saved")
    finally:
        session.close()


@app.delete("/api/report-presets/{preset_id}")
def delete_report_preset(preset_id: str):
    session = SessionLocal()
    try:
        with session.begin():
            row = session.get(ReportPreset, preset_id)
            if not row:
                raise HTTPException(status_code=404, detail="Report preset not found")
            row.is_active = False
        return envelope({"preset_id": preset_id}, "report preset deleted")
    finally:
        session.close()


@app.get("/api/report-presets/{preset_id}/runs")
def report_preset_runs(preset_id: str, limit: int = 20):
    session = SessionLocal()
    try:
        if not session.get(ReportPreset, preset_id):
            raise HTTPException(status_code=404, detail="Report preset not found")
        rows = session.query(ReportRun).filter(ReportRun.preset_id == preset_id).order_by(ReportRun.generated_at.desc()).limit(min(max(limit, 1), 100)).all()
        return envelope([_report_run_dict(row) for row in rows], "ok")
    finally:
        session.close()


@app.post("/api/report-presets/{preset_id}/run")
def run_report_preset(preset_id: str):
    result = _execute_report_preset(preset_id)
    if not result:
        raise HTTPException(status_code=404, detail="Active report preset not found")
    return envelope(result, "report generated")


@app.get("/api/commercial-contracts")
def commercial_contracts(q: str | None = None, station_code: str | None = None, policy: str | None = None, sub_category: str | None = None, allocation_code: str | None = None, page: int = 1, page_size: int = 25, sort_by: str | None = None, sort_order: str = "asc", search: str | None = None):
    items = filter_search(list_commercial_contracts(q=q, station_code=station_code, policy=policy, sub_category=sub_category, allocation_code=allocation_code), search or q)
    items = sort_items(items, sort_by if sort_by in commercial_contract_sort_map() else None, sort_order)
    page_data = paginate(items, page, page_size)
    return envelope({"items": page_data.items, "pagination": {"total": page_data.total, "page": page_data.page, "page_size": page_data.page_size}}, "ok")


@app.get("/api/contracts")
def registry_contracts(status: str = "all", search: str | None = None, asset_type: str | None = None, page: int = 1, page_size: int = 50):
    rows = list_registry_contracts(status=status, search=search, asset_type=asset_type)
    page_data = paginate(rows, page, page_size)
    return envelope({"items": page_data.items, "pagination": {"total": page_data.total, "page": page_data.page, "page_size": page_data.page_size}}, "ok")


@app.get("/api/contracts/summary")
def registry_contract_summary():
    return envelope(registry_summary(), "ok")


@app.post("/api/contracts/import")
async def registry_contract_import(path: str | None = None, file: UploadFile | None = File(default=None)):
    if file:
        content = await file.read()
        result = import_eauction_workbook(content, file.filename)
        result.update(backfill_legacy_contracts())
        return envelope(result, "contracts imported")
    if path:
        result = import_eauction_workbook(path, path)
        result.update(backfill_legacy_contracts())
        return envelope(result, "contracts imported")
    raise HTTPException(status_code=422, detail="Excel file upload or path is required")


@app.get("/api/commercial-contracts/reports")
def commercial_contract_reports():
    return envelope(get_commercial_contract_reports(), "ok")


@app.get("/api/contracts/alerts")
def contract_alerts(station_code: str | None = None):
    return envelope(get_contract_alerts(station_code=station_code), "ok")


@app.get("/api/contracts/{contract_id}")
def registry_contract_detail(contract_id: int):
    row = get_registry_contract(contract_id)
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found")
    return envelope(row, "ok")


@app.get("/api/commercial-contracts/{contract_key}")
def commercial_contract_detail(contract_key: int):
    detail = get_commercial_contract_detail(contract_key)
    if not detail:
        raise HTTPException(status_code=404, detail="Commercial contract not found")
    return envelope(detail, "ok")


@app.get("/api/commercial-contracts/{contract_key}/statement")
def commercial_contract_statement(contract_key: int):
    """Download a complete contract payment statement as CSV."""
    detail = get_commercial_contract_detail(contract_key)
    if not detail:
        raise HTTPException(status_code=404, detail="Commercial contract not found")
    contract = detail["contract"]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Contract Name", "Policy", "Sub Category", "Licensee", "Station",
        "Payment Month", "Source Column", "Amount Due", "Amount Paid",
        "Outstanding", "Payment Status",
    ])
    links = detail.get("station_links") or [{}]
    payments = detail.get("payments") or [{}]
    for link in links:
        for payment in payments:
            due = int(payment.get("amount_due") or 0)
            paid = int(payment.get("amount_paid") or 0)
            writer.writerow([
                contract.get("contract_name"),
                contract.get("policy"),
                contract.get("sub_category"),
                contract.get("licensee_name"),
                link.get("station_code") or contract.get("raw_station_value"),
                payment.get("payment_month"),
                payment.get("source_column"),
                due,
                paid,
                max(0, due - paid),
                payment.get("payment_status"),
            ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="contract-{contract_key}-statement.csv"'},
    )


@app.post("/api/commercial-contracts/import")
async def import_commercial_contracts(path: str | None = None, file: UploadFile | None = File(default=None)):
    try:
        if file:
            content = await file.read()
            parsed = parse_commercial_contract_workbook(content)
        elif path:
            parsed = parse_commercial_contract_workbook(path)
        else:
            raise HTTPException(status_code=422, detail="Excel file upload or path is required")
        return envelope(_apply_commercial_contract_import(parsed), "commercial contracts imported")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Workbook not found: {path}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/commercial-contracts", status_code=201)
def create_commercial_contract(payload: dict):
    session = SessionLocal()
    try:
        with session.begin():
            if session.query(CommercialContract).filter(CommercialContract.contract_name == payload.get("contract_name")).one_or_none():
                raise HTTPException(status_code=409, detail="Commercial contract already exists")
            contract = _create_row(CommercialContract, payload, "contract_name")
            session.add(contract)
            _log_change(session, "commercial_contracts", contract.contract_name, "create", "manual")
        return envelope(row_to_dict(contract), "commercial contract created")
    finally:
        session.close()


@app.put("/api/commercial-contracts/{contract_key}")
def update_commercial_contract(contract_key: int, payload: dict):
    session = SessionLocal()
    try:
        with session.begin():
            contract = session.get(CommercialContract, contract_key)
            if not contract:
                raise HTTPException(status_code=404, detail="Commercial contract not found")
            _assign_columns(contract, payload, skip={"contract_key", "created_at", "first_seen_at"})
            _log_change(session, "commercial_contracts", str(contract.contract_key), "update", "manual")
        return envelope(row_to_dict(contract), "commercial contract updated")
    finally:
        session.close()


@app.delete("/api/commercial-contracts/{contract_key}")
def delete_commercial_contract(contract_key: int):
    session = SessionLocal()
    try:
        with session.begin():
            contract = session.get(CommercialContract, contract_key)
            if not contract:
                raise HTTPException(status_code=404, detail="Commercial contract not found")
            session.query(CommercialContractStationLink).filter(CommercialContractStationLink.contract_key == contract_key).delete()
            session.query(CommercialContractPayment).filter(CommercialContractPayment.contract_key == contract_key).delete()
            session.delete(contract)
            _log_change(session, "commercial_contracts", str(contract_key), "delete", "manual")
        return envelope({"contract_key": contract_key}, "commercial contract deleted")
    finally:
        session.close()


@app.get("/api/passenger-amenities")
def passenger_amenities(kind: str = "summary", q: str | None = None, station_code: str | None = None, page: int = 1, page_size: int = 25, sort_by: str | None = None, sort_order: str = "asc", search: str | None = None):
    items = filter_search(list_passenger_amenities(kind=kind, q=q, station_code=station_code), search or q)
    items = sort_items(items, sort_by if sort_by in passenger_amenity_sort_map() else None, sort_order)
    page_data = paginate(items, page, page_size)
    return envelope({"items": page_data.items, "pagination": {"total": page_data.total, "page": page_data.page, "page_size": page_data.page_size}}, "ok")


@app.get("/api/passenger-amenities/reports")
def passenger_amenity_reports():
    return envelope(get_passenger_amenity_reports(), "ok")


@app.post("/api/passenger-amenities/preview")
def preview_passenger_amenities(payload: dict | None = None):
    try:
        return envelope(_preview_passenger_amenity_tabs((payload or {}).get("tab", "all")), "passenger amenity preview ready")
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Unable to fetch PA Infra Google Sheet: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/passenger-amenities/import")
def import_passenger_amenities(payload: dict | None = None):
    tab = (payload or {}).get("tab", "all")
    try:
        return envelope(_import_passenger_amenity_tabs(tab), "passenger amenity data imported")
    except requests.RequestException as exc:
        raise HTTPException(status_code=400, detail=f"Unable to fetch PA Infra Google Sheet: {exc}") from exc


@app.post("/api/passenger-amenities/import-pf-extension")
def import_pf_extension(payload: dict | None = None):
    path = (payload or {}).get("path") or DEFAULT_PF_EXTENSION_WORKBOOK
    try:
        return envelope(_import_pf_extension_workbook(path), "platform extension workbook imported")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Workbook not found: {path}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/stations")
def stations(q: str | None = None, category: str | None = None, page: int = 1, page_size: int = 25, sort_by: str | None = None, sort_order: str = "asc", search: str | None = None):
    items = filter_search(list_stations(q=q, category=category), search or q)
    items = sort_items(items, sort_by if sort_by in station_sort_map() else None, sort_order)
    page_data = paginate(items, page, page_size)
    return envelope({"items": page_data.items, "pagination": {"total": page_data.total, "page": page_data.page, "page_size": page_data.page_size}}, "ok")


@app.get("/api/stations/{station_code}/detail")
def station_detail(station_code: str):
    detail = get_station_detail(station_code)
    if not detail:
        raise HTTPException(status_code=404, detail="Station not found")
    return envelope(detail, "ok")


def _metric_month(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:7], "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="month must be YYYY-MM") from exc


@app.get("/api/station-metrics")
def station_metrics(station_code: str | None = None, year: int | None = None, month: int | None = None):
    session = SessionLocal()
    try:
        query = session.query(StationMonthlyMetric)
        if station_code:
            query = query.filter(StationMonthlyMetric.station_code == station_code.strip().upper())
        if year:
            query = query.filter(StationMonthlyMetric.metric_month >= date(year, 1, 1), StationMonthlyMetric.metric_month < date(year + 1, 1, 1))
        if month:
            if month < 1 or month > 12:
                raise HTTPException(status_code=422, detail="month must be between 1 and 12")
            query = query.filter(extract("month", StationMonthlyMetric.metric_month) == month)
        rows = query.order_by(StationMonthlyMetric.metric_month.desc(), StationMonthlyMetric.station_code).all()
        return envelope({"items": [row_to_dict(row) for row in rows], "years": sorted({row.metric_month.year for row in rows}, reverse=True)}, "ok")
    finally:
        session.close()


@app.post("/api/station-metrics/bulk")
def bulk_station_metrics(payload: dict):
    """Upsert one month of metrics for many stations in one transaction."""
    default_month = payload.get("month")
    require_complete = bool(payload.get("require_complete"))
    required_metric_fields = ("passenger_footfall", "uts_tickets", "uts_earnings", "prs_tickets", "prs_earnings")
    rows = payload.get("rows") or []
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=422, detail="rows must contain at least one station metric")
    session = SessionLocal()
    try:
        station_codes = {code for (code,) in session.query(Station.station_code).all()}
        errors = []
        prepared = []
        seen_codes = set()
        for index, item in enumerate(rows, start=2):
            item = item or {}
            code = str(item.get("station_code") or "").strip().upper()
            month_value = item.get("month") or item.get("metric_month") or default_month
            if not code or code not in station_codes:
                errors.append({"row": index, "station_code": code, "error": "Station code not found"})
                continue
            if code in seen_codes:
                errors.append({"row": index, "station_code": code, "error": "Duplicate station code"})
                continue
            seen_codes.add(code)
            if not month_value:
                errors.append({"row": index, "station_code": code, "error": "Month is required as YYYY-MM"})
                continue
            try:
                metric_month = _metric_month(str(month_value))
            except HTTPException as exc:
                errors.append({"row": index, "station_code": code, "error": exc.detail})
                continue
            if require_complete and default_month and metric_month != _metric_month(str(default_month)):
                errors.append({"row": index, "station_code": code, "error": "Every row must use the selected reporting month"})
                continue
            if require_complete and any(item.get(field) in (None, "") for field in required_metric_fields):
                errors.append({"row": index, "station_code": code, "error": "Footfall and all UTS/PRS ticket and earnings values are required"})
                continue
            invalid_fields = []
            for field in required_metric_fields:
                if item.get(field) in (None, ""):
                    continue
                try:
                    value = float(item[field])
                    if value < 0 or (field in ("passenger_footfall", "uts_tickets", "prs_tickets") and not value.is_integer()):
                        invalid_fields.append(field)
                except (TypeError, ValueError):
                    invalid_fields.append(field)
            if invalid_fields:
                errors.append({"row": index, "station_code": code, "error": f"Invalid non-negative numeric value: {', '.join(invalid_fields)}"})
                continue
            prepared.append((code, metric_month, item))
        if require_complete:
            missing_codes = sorted(station_codes - seen_codes)
            if missing_codes:
                errors.append({"row": None, "station_code": None, "error": f"Monthly master is missing {len(missing_codes)} station(s)", "missing_station_codes": missing_codes})
        if errors:
            raise HTTPException(status_code=422, detail={"message": "Bulk upload contains invalid rows", "errors": errors})
        created = 0
        updated = 0
        for code, metric_month, item in prepared:
            row = session.query(StationMonthlyMetric).filter_by(station_code=code, metric_month=metric_month).one_or_none()
            if row is None:
                row = StationMonthlyMetric(station_code=code, metric_month=metric_month)
                session.add(row)
                created += 1
            else:
                updated += 1
            for field in (
                "passenger_footfall", "uts_tickets", "uts_earnings",
                "prs_tickets", "prs_earnings", "tickets_issued", "earnings",
                "source", "remarks",
            ):
                if field in item and item[field] != "":
                    setattr(row, field, item[field])
        session.commit()
        return envelope({"created": created, "updated": updated, "processed": len(prepared)}, "station metrics bulk upload complete")
    finally:
        session.close()


@app.put("/api/stations/{station_code}/metrics/{month_value}")
def save_station_metric(station_code: str, month_value: str, payload: dict):
    code = station_code.strip().upper()
    metric_month = _metric_month(month_value)
    session = SessionLocal()
    try:
        with session.begin():
            if not session.get(Station, code):
                raise HTTPException(status_code=404, detail="Station not found")
            row = session.query(StationMonthlyMetric).filter_by(station_code=code, metric_month=metric_month).one_or_none()
            if not row:
                row = StationMonthlyMetric(station_code=code, metric_month=metric_month)
                session.add(row)
            for field in (
                "passenger_footfall", "uts_tickets", "uts_earnings",
                "prs_tickets", "prs_earnings", "tickets_issued", "earnings",
                "source", "remarks",
            ):
                if field in payload:
                    setattr(row, field, payload[field])
        return envelope(row_to_dict(row), "station monthly metric saved")
    finally:
        session.close()


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
            _apply_unit_availability(session, unit)
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
            _apply_unit_availability(session, unit)
            _log_change(session, "units", unit.unit_no, "update", "manual")
        return envelope(row_to_dict(unit), "unit updated")
    finally:
        session.close()


def _apply_unit_availability(session, unit: Unit) -> None:
    available = is_available_unit(unit)
    if available:
        if not unit.remarks and unit.unit_status and unit.unit_status != "Available":
            unit.remarks = unit.unit_status
        unit.unit_status = "Available"
    scope = "tender_emd" if available else "unit"
    session.query(Earning).filter(Earning.unit_no == unit.unit_no).update(
        {"earning_scope": scope},
        synchronize_session=False,
    )


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


@app.get("/api/works/monitoring")
def work_monitoring(q: str | None = None, section: str | None = None, allocation: str | None = None, year: str | None = None, work_type: str | None = None, page: int = 1, page_size: int = 50):
    report = get_work_monitoring(q=q, section=section, allocation=allocation, year=year, work_type=work_type)
    page_data = paginate(report["items"], page, page_size)
    return envelope({**report, "items": page_data.items, "pagination": {"total": page_data.total, "page": page_data.page, "page_size": page_data.page_size}}, "ok")


def _progress_payload(payload: dict, project_id: str) -> dict:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Progress update must be an object")
    update_date = str(payload.get("update_date") or "").strip()
    if not update_date:
        raise HTTPException(status_code=422, detail="update_date is required for a progress update")
    progress = payload.get("progress_percent")
    if progress not in (None, ""):
        try:
            progress = int(float(progress))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="progress_percent must be a number") from exc
        if progress < 0 or progress > 100:
            raise HTTPException(status_code=422, detail="progress_percent must be between 0 and 100")
    expenditure = payload.get("expenditure_upto_date")
    if expenditure not in (None, ""):
        try:
            expenditure = int(float(expenditure))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="expenditure_upto_date must be a number") from exc
        if expenditure < 0:
            raise HTTPException(status_code=422, detail="expenditure_upto_date cannot be negative")
    return {
        "project_id": project_id,
        "update_date": update_date,
        "progress_percent": progress,
        "status": str(payload.get("status") or "").strip() or None,
        "physical_progress": payload.get("physical_progress"),
        "financial_progress": payload.get("financial_progress"),
        "expenditure_upto_date": expenditure,
        "tdc": payload.get("tdc"),
        "remarks": payload.get("remarks"),
        "source": str(payload.get("source") or "manual").strip(),
    }


def _expenditure_payload(payload: dict, project_id: str) -> dict:
    update_date = str(payload.get("update_date") or "").strip()
    if not update_date:
        raise HTTPException(status_code=422, detail="update_date is required for an expenditure update")
    values = {}
    for key in ("period_expenditure", "cumulative_expenditure"):
        raw = payload.get(key)
        if raw in (None, ""):
            values[key] = None
            continue
        try:
            parsed = int(float(raw))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"{key} must be a number") from exc
        if parsed < 0:
            raise HTTPException(status_code=422, detail=f"{key} cannot be negative")
        values[key] = parsed
    if values["period_expenditure"] is None and values["cumulative_expenditure"] is None:
        raise HTTPException(status_code=422, detail="period_expenditure or cumulative_expenditure is required")
    return {
        "project_id": project_id,
        "update_date": update_date,
        **values,
        "source": str(payload.get("source") or "manual").strip(),
        "reference": str(payload.get("reference") or "").strip() or None,
        "remarks": str(payload.get("remarks") or "").strip() or None,
    }


@app.get("/api/works/{project_id}/progress")
def work_progress(project_id: str):
    session = SessionLocal()
    try:
        work = session.query(Work).filter(Work.project_id == project_id).one_or_none()
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")
        rows = (
            session.query(WorkProgressUpdate)
            .filter(WorkProgressUpdate.project_id == project_id)
            .order_by(WorkProgressUpdate.update_date.desc(), WorkProgressUpdate.progress_id.desc())
            .all()
        )
        photo_rows = session.query(WorkProgressPhoto).filter(WorkProgressPhoto.project_id == project_id).order_by(WorkProgressPhoto.created_at.desc()).all()
        photos_by_progress: dict[int, list[dict]] = {}
        for photo in photo_rows:
            photos_by_progress.setdefault(photo.progress_id or 0, []).append({
                "photo_id": photo.photo_id,
                "project_id": photo.project_id,
                "progress_id": photo.progress_id,
                "mime_type": photo.mime_type,
                "caption": photo.caption,
                "captured_at": photo.captured_at.isoformat() if photo.captured_at else None,
                "created_at": photo.created_at.isoformat() if photo.created_at else None,
                "download_url": f"/api/works/{project_id}/progress/photos/{photo.photo_id}",
            })
        items = []
        for row in rows:
            item = row_to_dict(row)
            item["photos"] = photos_by_progress.get(row.progress_id, [])
            items.append(item)
        return envelope({"project_id": project_id, "items": items, "photos": [photo for values in photos_by_progress.values() for photo in values]}, "ok")
    finally:
        session.close()


@app.get("/api/works/{project_id}/expenditure")
def work_expenditure(project_id: str):
    session = SessionLocal()
    try:
        if not session.query(Work).filter(Work.project_id == project_id).one_or_none():
            raise HTTPException(status_code=404, detail="Work not found")
        rows = session.query(WorkExpenditureUpdate).filter(WorkExpenditureUpdate.project_id == project_id).order_by(WorkExpenditureUpdate.update_date.desc(), WorkExpenditureUpdate.expenditure_id.desc()).all()
        return envelope({"project_id": project_id, "items": [row_to_dict(row) for row in rows]}, "ok")
    finally:
        session.close()


@app.post("/api/works/{project_id}/expenditure")
def add_work_expenditure(project_id: str, payload: dict):
    session = SessionLocal()
    try:
        with session.begin():
            work = session.query(Work).filter(Work.project_id == project_id).one_or_none()
            if not work:
                raise HTTPException(status_code=404, detail="Work not found")
            values = _expenditure_payload(payload, project_id)
            row = session.query(WorkExpenditureUpdate).filter(
                WorkExpenditureUpdate.project_id == project_id,
                WorkExpenditureUpdate.update_date == values["update_date"],
            ).one_or_none()
            if row:
                for key, value in values.items():
                    if key != "project_id":
                        setattr(row, key, value)
                row.updated_at = datetime.now(timezone.utc)
            else:
                row = WorkExpenditureUpdate(**values)
                session.add(row)
            if values["cumulative_expenditure"] is not None:
                work.expenditure_upto_date = values["cumulative_expenditure"]
            work.updated_at = datetime.now(timezone.utc)
            session.flush()
            _log_change(session, "works", project_id, "expenditure_update", values["update_date"])
        return envelope(row_to_dict(row), "work expenditure saved")
    finally:
        session.close()


@app.post("/api/works/{project_id}/progress")
def add_work_progress(project_id: str, payload: dict):
    session = SessionLocal()
    try:
        with session.begin():
            work = session.query(Work).filter(Work.project_id == project_id).one_or_none()
            if not work:
                raise HTTPException(status_code=404, detail="Work not found")
            values = _progress_payload(payload, project_id)
            row = (
                session.query(WorkProgressUpdate)
                .filter(
                    WorkProgressUpdate.project_id == project_id,
                    WorkProgressUpdate.update_date == values["update_date"],
                )
                .one_or_none()
            )
            if row:
                for key, value in values.items():
                    if key != "project_id":
                        setattr(row, key, value)
                row.updated_at = datetime.now(timezone.utc)
            else:
                row = WorkProgressUpdate(**values)
                session.add(row)
            if values["status"]:
                work.status = values["status"]
            if values["progress_percent"] is not None:
                work.physical_progress = f"{values['progress_percent']}%"
            if values["expenditure_upto_date"] is not None:
                work.expenditure_upto_date = values["expenditure_upto_date"]
            work.updated_at = datetime.now(timezone.utc)
            session.flush()
            _log_change(session, "works", project_id, "progress_update", f"{values['update_date']} / {values['progress_percent']}")
        return envelope(row_to_dict(row), "work progress saved")
    finally:
        session.close()


@app.post("/api/works/{project_id}/progress/{progress_id}/photos", status_code=201)
async def upload_work_progress_photo(project_id: str, progress_id: int, file: UploadFile = File(...), caption: str | None = None):
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=422, detail="Only JPEG, PNG, or WebP progress photos are supported")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Progress photo is empty")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Progress photo must be 10 MB or smaller")
    session = SessionLocal()
    try:
        progress = session.query(WorkProgressUpdate).filter(
            WorkProgressUpdate.progress_id == progress_id,
            WorkProgressUpdate.project_id == project_id,
        ).one_or_none()
        if not progress:
            raise HTTPException(status_code=404, detail="Progress update not found")
        photo = WorkProgressPhoto(
            photo_id=str(uuid4()),
            project_id=project_id,
            progress_id=progress_id,
            mime_type=file.content_type,
            content=content,
            caption=(caption or "").strip() or None,
            captured_at=datetime.now(timezone.utc),
        )
        session.add(photo)
        session.commit()
        return envelope({
            "photo_id": photo.photo_id,
            "project_id": project_id,
            "progress_id": progress_id,
            "caption": photo.caption,
            "mime_type": photo.mime_type,
            "download_url": f"/api/works/{project_id}/progress/photos/{photo.photo_id}",
        }, "progress photo saved")
    finally:
        session.close()


@app.get("/api/works/{project_id}/progress/photos/{photo_id}")
def download_work_progress_photo(project_id: str, photo_id: str):
    session = SessionLocal()
    try:
        photo = session.query(WorkProgressPhoto).filter(
            WorkProgressPhoto.photo_id == photo_id,
            WorkProgressPhoto.project_id == project_id,
        ).one_or_none()
        if not photo:
            raise HTTPException(status_code=404, detail="Progress photo not found")
        return Response(content=photo.content, media_type=photo.mime_type, headers={"Content-Disposition": f'inline; filename="{photo.photo_id}"'})
    finally:
        session.close()


@app.post("/api/works/import-sanctioned/preview")
def preview_sanctioned_works():
    try:
        response = requests.get(_sanctioned_works_export_url(), timeout=90)
        response.raise_for_status()
        rows = parse_works_xlsx(response.content)
        diff = _works_import_diff(rows)
        return envelope(diff, "sanctioned works preview ready")
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Unable to fetch sanctioned works sheet: {exc}") from exc


@app.post("/api/works/import-sanctioned")
def import_sanctioned_works(dry_run: bool = False):
    try:
        response = requests.get(_sanctioned_works_export_url(), timeout=90)
        response.raise_for_status()
        rows = parse_works_xlsx(response.content)
        diff = _works_import_diff(rows)
        if not diff["validation"]["valid"]:
            raise HTTPException(status_code=422, detail=diff)
        if dry_run:
            return envelope({**diff, "mode": "dry-run"}, "sanctioned works validated")
        count = _replace_all_works(rows)
        return envelope({**diff, "rows": len(rows), "upserted": count, "mode": "apply"}, "sanctioned works imported")
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Unable to fetch sanctioned works sheet: {exc}") from exc


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
def earnings(q: str | None = None, unit_no: str | None = None, station_code: str | None = None, include_tender_emd: bool = False, page: int = 1, page_size: int = 25, sort_by: str | None = None, sort_order: str = "asc", search: str | None = None):
    items = filter_search(
        list_earnings(
            q=q,
            unit_no=unit_no,
            station_code=station_code,
            include_tender_emd=include_tender_emd,
        ),
        search or q,
    )
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
