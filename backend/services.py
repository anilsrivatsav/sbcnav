from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from database import SessionLocal
from models import Earning, EarningLink, Station, Unit, Work, WorkLink

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
    header_idx = next(i for i, row in enumerate(rows) if any(normalize(cell) == "projectid" for cell in row))
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
