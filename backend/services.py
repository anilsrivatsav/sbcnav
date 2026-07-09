from __future__ import annotations

import csv
import hashlib
import io
import os
import re
from datetime import datetime, timezone
from typing import Any

import requests
from sqlalchemy import func, select

from auth import create_access_token, hash_password, verify_password
from database import SessionLocal
from models import AuthSession, Earning, EarningLink, Station, SyncRun, Unit, User, Work, WorkLink

STATIONS_SHEET = "1UdRgQQPEkak1fUTuVH7jIn5R4sE3szAhM4VZJOdFIOU"
WORKS_SHEET = "1rJbfhcnEVuGMwGkT8yBObb9Bk5Hx0uU224EGxfplGRc"
WORKS_GID = "590791228"
EARNINGS_GID = "1453342147"

DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
DEFAULT_EDITOR_USERNAME = os.getenv("DEFAULT_EDITOR_USERNAME", "editor")
DEFAULT_EDITOR_PASSWORD = os.getenv("DEFAULT_EDITOR_PASSWORD", "editor123")
DEFAULT_VIEWER_USERNAME = os.getenv("DEFAULT_VIEWER_USERNAME", "viewer")
DEFAULT_VIEWER_PASSWORD = os.getenv("DEFAULT_VIEWER_PASSWORD", "viewer123")


def clean(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return "" if not text or text.upper() == "#N/A" else text


def to_int(value: Any) -> int | None:
    text = clean(value).replace("₹", "").replace("?", "").replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", clean(text).lower())


def fetch_csv(sheet_id: str, query: str) -> str:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&{query}"

    try:
        response = requests.get(url, timeout=90)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        raise RuntimeError(f"Unable to fetch Google Sheet: {sheet_id}") from exc


def parse_csv(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


def hash_row(prefix: str, payload: dict[str, Any]) -> str:
    material = prefix + "|" + "|".join(f"{k}={clean(v)}" for k, v in sorted(payload.items()))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def audit_fields(now: datetime) -> dict[str, Any]:
    return {
        "created_at": now,
        "updated_at": now,
        "first_seen_at": now,
        "last_seen_at": now,
        "is_active": True,
    }


def parse_stations(text: str) -> list[dict[str, Any]]:
    rows = parse_csv(text)
    headers = [normalize(h) for h in rows[0]]
    out: list[dict[str, Any]] = []
    for row in rows[1:]:
        item: dict[str, Any] = {}
        for idx, header in enumerate(headers):
            value = row[idx] if idx < len(row) else ""
            mapping = {
                "station code": "station_code",
                "station name": "station_name",
                "division": "division",
                "zone": "zone",
                "section": "section",
                "cmi": "cmi",
                "den": "den",
                "sr.den": "sr_den",
                "categorisation": "categorisation",
                "earnings range": "earnings_range",
                "passenger range": "passenger_range",
                "passenger footfall": "passenger_footfall",
                "platforms": "platforms",
                "number of platforms": "number_of_platforms",
                "platform type": "platform_type",
                "parking": "parking",
                "pay-and-use": "pay_and_use",
                "no of trains dealt": "trains_dealt",
                "tkts per day": "tickets_per_day",
                "pass per day": "passengers_per_day",
                "earnings per day": "earnings_per_day",
                "footfalls per day": "footfalls_per_day",
            }
            if header in mapping:
                item[mapping[header]] = to_int(value) if header in {"passenger footfall", "number of platforms", "no of trains dealt", "tkts per day", "pass per day", "earnings per day", "footfalls per day"} else clean(value)
        if item.get("station_code"):
            out.append(item)
    return out


def parse_units(text: str) -> list[dict[str, Any]]:
    rows = parse_csv(text)
    headers = [normalize(h) for h in rows[0]]
    out: list[dict[str, Any]] = []
    for row in rows[1:]:
        item: dict[str, Any] = {}
        for idx, header in enumerate(headers):
            value = row[idx] if idx < len(row) else ""
            mapping = {
                "sl no.": "sl_no",
                "unit no.": "unit_no",
                "type of unit": "type_of_unit",
                "station": "station_code",
                "station category": "station_category",
                "old category": "old_category",
                "pf no": "pf_no",
                "pegged location": "pegged_location",
                "reservation category": "reservation_category",
                "type of allotment": "allotment_type",
                "name of licensee": "licensee_name",
                "license fee": "license_fee",
                "contract from": "contract_from",
                "contract to": "contract_to",
                "unit status": "unit_status",
            }
            if header in mapping:
                item[mapping[header]] = to_int(value) if header == "sl no." else clean(value).replace("₹", "")
        if item.get("unit_no"):
            out.append(item)
    return out


def parse_earnings(text: str) -> list[dict[str, Any]]:
    rows = parse_csv(text)
    headers = [normalize(h) for h in rows[0]]
    out: list[dict[str, Any]] = []
    for row in rows[1:]:
        item: dict[str, Any] = {}
        for idx, header in enumerate(headers):
            value = row[idx] if idx < len(row) else ""
            mapping = {
                "sl. no.": "sl_no",
                "date of receipt": "date_of_receipt",
                "unit no.": "unit_no",
                "station": "station_code",
                "pf no.": "pf_no",
                "name of licensee": "licensee_name",
                "payment head": "payment_head",
                "payment sub-head": "payment_sub_head",
                "period from": "period_from",
                "period to": "period_to",
                "amount": "amount",
                "gst": "gst",
                "reciept type": "receipt_type",
                "mr no/uts no/ challan no": "mr_no",
                "mr date": "mr_date",
                "u/a case": "ua_case",
            }
            if header in mapping:
                item[mapping[header]] = to_int(value) if header in {"sl. no.", "amount", "gst"} else clean(value)
        if item.get("unit_no"):
            item["receipt_key"] = hash_row("earning", item)
            out.append(item)
    return out


def parse_works(text: str) -> list[dict[str, Any]]:
    rows = parse_csv(text)
    header_idx = next(i for i, row in enumerate(rows) if "PROJECTID" in row)
    headers = [normalize(h) for h in rows[header_idx]]
    out: list[dict[str, Any]] = []
    for row in rows[header_idx + 1 :]:
        item: dict[str, Any] = {}
        for idx, header in enumerate(headers):
            value = row[idx] if idx < len(row) else ""
            mapping = {
                "projectid": "project_id",
                "year of sanction": "year_of_sanction",
                "year ub works": "year_ub_works",
                "status": "status",
                "date of sanction": "date_of_sanction",
                "short name of work": "short_name_of_work",
                "block section station": "block_section_station",
                "allocation": "allocation",
                "engg. remarks": "engg_remarks",
                "if ub?": "if_ub",
                "parent work": "parent_work",
                "section": "section",
                "anticipated expenditure": "anticipated_expenditure",
                "remarks": "remarks",
            }
            if header in mapping:
                item[mapping[header]] = to_int(value) if header == "anticipated expenditure" else clean(value)
        if item.get("project_id") and normalize(item["project_id"]) != "projectid":
            out.append(item)
    return out


def split_scopes(raw: str) -> list[dict[str, Any]]:
    text = clean(raw)
    if not text:
        return []
    body = text
    if re.search(r"\bstn:\s*", text, flags=re.I):
        body = re.split(r"\bstn:\s*", text, flags=re.I, maxsplit=1)[1]
    tokens = [token.strip() for token in re.split(r",|;|/|&|\band\b", body, flags=re.I) if token.strip()]
    scopes = []
    for token in tokens or [body]:
        upper = token.upper()
        if "ABSS" in upper:
            scopes.append({"scope_type": "ABSS", "scope_value": token, "station_code": None})
        elif re.search(r"\bDIV(ISION)?\b", upper):
            scopes.append({"scope_type": "Division", "scope_value": token, "station_code": None})
        else:
            scopes.append({"scope_type": "Station", "scope_value": token, "station_code": token})
    return scopes


def upsert_many(session, model, rows, conflict_cols, update_cols):
    if not rows:
        return 0
    existing_key_cols = [col.key if hasattr(col, "key") else col.name for col in conflict_cols]
    written = 0
    for row in rows:
        filters = {col: row[col] for col in existing_key_cols if row.get(col) is not None}
        obj = session.query(model).filter_by(**filters).one_or_none() if filters else None
        if obj is None:
            obj = model(**row)
            session.add(obj)
        else:
            for col in update_cols:
                setattr(obj, col, row.get(col))
        session.flush()
        written += 1
    return written


def rebuild_db() -> dict[str, int]:
    stations = parse_stations(fetch_csv(STATIONS_SHEET, "sheet=stations"))
    units = parse_units(fetch_csv(STATIONS_SHEET, "sheet=Units"))
    earnings = parse_earnings(fetch_csv(STATIONS_SHEET, f"gid={EARNINGS_GID}"))
    works = parse_works(fetch_csv(WORKS_SHEET, f"gid={WORKS_GID}"))

    station_codes = {row["station_code"] for row in stations}
    unit_codes = {row["unit_no"] for row in units}

    links: list[dict[str, Any]] = []
    for work in works:
        scopes = split_scopes(work.get("block_section_station", ""))
        if not scopes:
            links.append({"project_id": work["project_id"], "scope_type": "Other", "scope_value": work.get("block_section_station", ""), "station_code": None, "match_status": "Unparsed"})
            continue
        for scope in scopes:
            if scope["scope_type"] == "Station":
                codes = [code.strip() for code in re.split(r"\s*&\s*|,\s*|\s+AND\s+", scope["scope_value"], flags=re.I) if code.strip()]
                for code in codes or [scope["scope_value"]]:
                    links.append({"project_id": work["project_id"], "scope_type": "Station", "scope_value": code, "station_code": code, "match_status": "Matched" if code in station_codes else "Missing station"})
            else:
                links.append({"project_id": work["project_id"], "scope_type": scope["scope_type"], "scope_value": scope["scope_value"], "station_code": None, "match_status": scope["scope_type"]})

    earning_links = []
    for earning in earnings:
        earning_links.append({"receipt_key": earning["receipt_key"], "unit_no": earning.get("unit_no"), "station_code": earning.get("station_code", ""), "match_status": "Matched" if earning.get("unit_no") in unit_codes else "Missing unit"})

    now = datetime.now(timezone.utc)
    session = SessionLocal()
    sync_run = SyncRun(started_at=now, status="running")
    session.add(sync_run)
    session.commit()

    try:
        with session.begin():
           
            station_rows = [{**row, **audit_fields(now), "source_hash": hash_row("station", row)} for row in stations]
            unit_rows = [{**row, **audit_fields(now), "source_hash": hash_row("unit", row)} for row in units]
            work_rows = [{**row, **audit_fields(now), "source_hash": hash_row("work", row)} for row in works]
            earning_rows = [{**row, **audit_fields(now), "source_hash": hash_row("earning", row)} for row in earnings]
            stations_count = upsert_many(
                session,
                Station,
                station_rows,
                [Station.station_code],
                [c.name for c in Station.__table__.columns if c.name not in {"station_code", "created_at", "first_seen_at"}],
            )
            units_count = upsert_many(
                session,
                Unit,
                unit_rows,
                [Unit.unit_no],
                [c.name for c in Unit.__table__.columns if c.name not in {"unit_no", "created_at", "first_seen_at"}],
            )
            works_count = upsert_many(
                session,
                Work,
                work_rows,
                [Work.project_id],
                [c.name for c in Work.__table__.columns if c.name not in {"work_key", "project_id", "created_at", "first_seen_at"}],
            )
            earnings_count = upsert_many(
                session,
                Earning,
                earning_rows,
                [Earning.receipt_key],
                [c.name for c in Earning.__table__.columns if c.name not in {"earning_key", "receipt_key", "created_at", "first_seen_at"}],
            )

            session.query(WorkLink).delete()
            session.query(EarningLink).delete()
            session.bulk_insert_mappings(WorkLink, links)
            session.bulk_insert_mappings(EarningLink, earning_links)

            sync_run.status = "success"
            sync_run.finished_at = now
            sync_run.updated_at = now
            sync_run.created_at = sync_run.created_at or now
            sync_run.stations_upserted = stations_count
            sync_run.units_upserted = units_count
            sync_run.works_upserted = works_count
            sync_run.earnings_upserted = earnings_count
            sync_run.links_upserted = len(links) + len(earning_links)
    except Exception as exc:
        session.rollback()
        sync_run.status = "failed"
        sync_run.error_message = str(exc)
        sync_run.finished_at = datetime.now(timezone.utc)
        sync_run.updated_at = sync_run.finished_at
        session.add(sync_run)
        session.commit()
        raise
    finally:
        session.close()

    return {"stations": len(stations), "units": len(units), "works": len(works), "earnings": len(earnings), "links": len(links) + len(earning_links)}


def ensure_default_users(session) -> None:
    defaults = [
        (DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD, "admin"),
        (DEFAULT_EDITOR_USERNAME, DEFAULT_EDITOR_PASSWORD, "editor"),
        (DEFAULT_VIEWER_USERNAME, DEFAULT_VIEWER_PASSWORD, "viewer"),
    ]
    for username, password, role in defaults:
        exists_user = session.execute(select(User.id).where(User.username == username)).scalar_one_or_none()
        if not exists_user:
            session.add(User(username=username, password_hash=hash_password(password), role=role, is_active=True))


def login_user(session, username: str, password: str) -> tuple[str, str]:
    user = session.execute(select(User).where(User.username == username, User.is_active.is_(True))).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid username or password")
    token_jti = hashlib.sha256(f"{username}:{datetime.now(timezone.utc).timestamp()}".encode()).hexdigest()
    auth_session = AuthSession(user_id=user.id, token_jti=token_jti)
    session.add(auth_session)
    session.flush()
    token = create_access_token(subject=user.username, role=user.role, session_id=auth_session.id)
    return token, user.role


def revoke_session(session, session_id: int) -> None:
    auth_session = session.get(AuthSession, session_id)
    if auth_session:
        auth_session.revoked_at = datetime.now(timezone.utc)
        session.add(auth_session)


def row_to_dict(row) -> dict[str, Any]:
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def records_from_query(query) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in query]


def station_sort_map() -> set[str]:
    return {"station_code", "station_name", "division", "zone", "section", "categorisation", "passenger_footfall"}


def unit_sort_map() -> set[str]:
    return {"unit_no", "station_code", "station_name", "station_category", "licensee_name", "unit_status"}


def work_sort_map() -> set[str]:
    return {"project_id", "status", "date_of_sanction", "section", "short_name_of_work"}


def earnings_sort_map() -> set[str]:
    return {"receipt_key", "unit_no", "station_code", "date_of_receipt", "licensee_name", "payment_head", "payment_sub_head", "amount", "receipt_type"}


def get_stats() -> dict[str, Any]:
    session = SessionLocal()
    try:
        return {
            "stations": session.query(func.count(Station.station_code)).scalar() or 0,
            "units": session.query(func.count(Unit.unit_no)).scalar() or 0,
            "works": session.query(func.count(Work.work_key)).scalar() or 0,
            "earnings": session.query(func.count(Earning.earning_key)).scalar() or 0,
            "links": session.query(func.count(WorkLink.id)).scalar() or 0,
            "earningsTotal": session.query(func.coalesce(func.sum(Earning.amount), 0)).scalar() or 0,
            "footfall": session.query(func.coalesce(func.sum(Station.passenger_footfall), 0)).scalar() or 0,
            "topStations": [
                {"station_code": code, "station_name": name, "works": works}
                for code, name, works in session.execute(
                    select(Station.station_code, Station.station_name, func.count(WorkLink.id).label("works"))
                    .join(WorkLink, WorkLink.station_code == Station.station_code, isouter=True)
                    .group_by(Station.station_code, Station.station_name, Station.passenger_footfall)
                    .order_by(func.count(WorkLink.id).desc(), Station.passenger_footfall.desc().nullslast())
                    .limit(8)
                )
            ],
        }
    finally:
        session.close()


def list_stations(q: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(Station)
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Station.station_code.ilike(like))
                | (Station.station_name.ilike(like))
                | (Station.section.ilike(like))
                | (Station.division.ilike(like))
                | (Station.categorisation.ilike(like))
            )
        if category and category != "All":
            query = query.filter(Station.categorisation == category)
        return [row_to_dict(row) for row in query.order_by(Station.station_name, Station.station_code).all()]
    finally:
        session.close()


def list_units(q: str | None = None, station_code: str | None = None) -> list[dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(Unit, Station.station_name, Station.categorisation).join(Station, Station.station_code == Unit.station_code, isouter=True)
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Unit.unit_no.ilike(like))
                | (Unit.licensee_name.ilike(like))
                | (Unit.station_code.ilike(like))
                | (Unit.unit_status.ilike(like))
            )
        if station_code and station_code != "All":
            query = query.filter(Unit.station_code == station_code)
        return [{**row_to_dict(unit), "station_name": station_name, "categorisation": categorisation} for unit, station_name, categorisation in query.order_by(Unit.station_code, Unit.unit_no).all()]
    finally:
        session.close()


def list_works(q: str | None = None, scope_type: str | None = None, station_code: str | None = None) -> list[dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(Work, WorkLink, Station.station_name, Station.categorisation).join(WorkLink, WorkLink.project_id == Work.project_id, isouter=True).join(Station, Station.station_code == WorkLink.station_code, isouter=True)
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Work.project_id.ilike(like))
                | (Work.short_name_of_work.ilike(like))
                | (Work.block_section_station.ilike(like))
                | (WorkLink.scope_value.ilike(like))
                | (WorkLink.scope_type.ilike(like))
            )
        if scope_type and scope_type != "All":
            query = query.filter(WorkLink.scope_type == scope_type)
        if station_code and station_code != "All":
            query = query.filter(WorkLink.station_code == station_code)
        return [{**row_to_dict(work), "scope_type": wl.scope_type, "scope_value": wl.scope_value, "station_code": wl.station_code, "match_status": wl.match_status, "station_name": station_name, "categorisation": categorisation} for work, wl, station_name, categorisation in query.order_by(Work.date_of_sanction.desc().nullslast(), Work.project_id).all()]
    finally:
        session.close()


def list_earnings(q: str | None = None, unit_no: str | None = None, station_code: str | None = None) -> list[dict[str, Any]]:
    session = SessionLocal()
    try:
        query = session.query(Earning, EarningLink, Unit.station_category, Unit.unit_status, Unit.type_of_unit, Station.station_name, Station.division, Station.section, Station.categorisation).join(EarningLink, EarningLink.receipt_key == Earning.receipt_key, isouter=True).join(Unit, Unit.unit_no == Earning.unit_no, isouter=True).join(Station, Station.station_code == func.coalesce(Earning.station_code, Unit.station_code), isouter=True)
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Earning.unit_no.ilike(like))
                | (Earning.station_code.ilike(like))
                | (Earning.licensee_name.ilike(like))
                | (Earning.payment_head.ilike(like))
                | (Earning.payment_sub_head.ilike(like))
                | (Earning.mr_no.ilike(like))
            )
        if unit_no and unit_no != "All":
            query = query.filter(Earning.unit_no == unit_no)
        if station_code and station_code != "All":
            query = query.filter(Earning.station_code == station_code)
        return [{**row_to_dict(earning), "match_status": link.match_status if link else None, "station_category": station_category, "unit_status": unit_status, "type_of_unit": type_of_unit, "station_name": station_name, "division": division, "section": section, "categorisation": categorisation} for earning, link, station_category, unit_status, type_of_unit, station_name, division, section, categorisation in query.order_by(Earning.date_of_receipt.desc().nullslast(), Earning.earning_key.desc()).all()]
    finally:
        session.close()
