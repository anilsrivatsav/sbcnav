from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from database import SessionLocal
from models import (
    AmenityNorm,
    Earning,
    EarningLink,
    PassengerAmenityWork,
    PlatformExtensionSummary,
    PlatformDetail,
    Station,
    StationInfra,
    StationPlatformExtensionStatus,
    TrolleyPath,
    Unit,
    WheelChairAvailability,
    Work,
    WorkLink,
)

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


def to_money(value: Any) -> int:
    parsed = to_int(value)
    return parsed or 0


def parse_date_value(value: Any) -> date | None:
    text = clean(value)
    if not text:
        return None
    text = re.sub(r"\s+00:00:00$", "", text)
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%d %b %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if match:
        day, month, year = match.groups()
        year_int = int(year)
        if year_int < 100:
            year_int += 2000
        try:
            return date(year_int, int(month), int(day))
        except ValueError:
            return None
    return None


def month_end(value: date) -> date:
    if value.month == 12:
        return date(value.year, 12, 31)
    return date(value.year, value.month + 1, 1) - timedelta(days=1)


def month_delta(start: date, end: date) -> int:
    if start > end:
        return 0
    return (end.year - start.year) * 12 + end.month - start.month + 1


def is_active_status(value: Any) -> bool:
    text = normalize(clean(value))
    if not text:
        return True
    return not any(token in text for token in ["closed", "inactive", "terminated", "expired", "vacant", "surrender"])


def is_license_fee_row(row: Earning) -> bool:
    text = normalize(" ".join([clean(row.payment_head), clean(row.payment_sub_head), clean(row.receipt_type)]))
    return "license" in text or "licence" in text or "lf" == text


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


def _header_map(headers: list[str]) -> dict[str, int]:
    return {normalize(header): index for index, header in enumerate(headers) if normalize(header)}


def _cell(row: list[str], indexes: dict[str, int], *names: str) -> str:
    for name in names:
        idx = indexes.get(normalize(name))
        if idx is not None and idx < len(row):
            value = clean(row[idx])
            if value:
                return value
    return ""


def parse_amenity_norms(text: str) -> list[dict[str, Any]]:
    rows = parse_csv(text)
    if not rows:
        return []
    indexes = _header_map(rows[0])
    out: list[dict[str, Any]] = []
    for row in rows[1:]:
        item = {
            "category": _cell(row, indexes, "categorization"),
            "amenity": _cell(row, indexes, "amenity"),
            "norm": _cell(row, indexes, "norms"),
            "norm_quantity": _cell(row, indexes, "norms quantity"),
        }
        if item["category"] and item["norm"]:
            out.append(item)
    return out


def parse_station_infra(text: str) -> list[dict[str, Any]]:
    rows = parse_csv(text)
    if not rows:
        return []
    indexes = _header_map(rows[0])
    out: list[dict[str, Any]] = []
    for row in rows[1:]:
        item = {
            "station_name": _cell(row, indexes, "stn"),
            "station_code": _cell(row, indexes, "code").upper(),
            "category": _cell(row, indexes, "catg"),
            "platform_list": clean(row[4] if len(row) > 4 else ""),
            "platform_count": to_int(_cell(row, indexes, "available")),
            "platform_level": _cell(row, indexes, "available"),
            "fob_details": _cell(row, indexes, "fob"),
            "shelter_details": _cell(row, indexes, "shelter"),
            "remarks": " | ".join(part for part in [_cell(row, indexes, "column 1"), _cell(row, indexes, "column 2"), _cell(row, indexes, "column 3")] if part),
        }
        count_candidate = to_int(row[5] if len(row) > 5 else "")
        level_candidate = clean(row[6] if len(row) > 6 else "")
        if count_candidate is not None:
            item["platform_count"] = count_candidate
        if level_candidate:
            item["platform_level"] = level_candidate
        if item["station_code"]:
            out.append(item)
    return out


def parse_platform_details(text: str) -> list[dict[str, Any]]:
    rows = parse_csv(text)
    if not rows:
        return []
    indexes = _header_map(rows[0])
    out: list[dict[str, Any]] = []
    for row in rows[1:]:
        item = {
            "station_code": _cell(row, indexes, "station").upper(),
            "platform": _cell(row, indexes, "platforms"),
            "length_m": to_int(_cell(row, indexes, "length")),
            "lifts": _cell(row, indexes, "lifts"),
            "escalators": _cell(row, indexes, "escalators"),
            "ramp": _cell(row, indexes, "ramp"),
        }
        if item["station_code"] and item["platform"]:
            out.append(item)
    return out


def parse_wheel_chairs(text: str) -> list[dict[str, Any]]:
    rows = parse_csv(text)
    header_idx = next((idx for idx, row in enumerate(rows) if any(normalize(cell) == "station code" for cell in row)), 0)
    indexes = _header_map(rows[header_idx])
    out: list[dict[str, Any]] = []
    for row in rows[header_idx + 1:]:
        item = {
            "station_code": _cell(row, indexes, "station code").upper(),
            "station_name": _cell(row, indexes, "station name"),
            "section": _cell(row, indexes, "section"),
            "category": _cell(row, indexes, "cat."),
            "available_good_condition": to_int(_cell(row, indexes, "no of wheel chairs available in good condition")),
        }
        if item["station_code"]:
            out.append(item)
    return out


def parse_trolley_paths(text: str) -> list[dict[str, Any]]:
    rows = parse_csv(text)
    if not rows:
        return []
    indexes = _header_map(rows[0])
    out: list[dict[str, Any]] = []
    for row in rows[1:]:
        item = {
            "station_code": _cell(row, indexes, "station code").upper(),
            "station_name": _cell(row, indexes, "station name"),
            "division": _cell(row, indexes, "division"),
            "zone": _cell(row, indexes, "zone"),
            "section": _cell(row, indexes, "section"),
            "categorisation": _cell(row, indexes, "categorisation"),
            "passenger_footfall": to_int(_cell(row, indexes, "passenger footfall")),
            "platforms": _cell(row, indexes, "platforms"),
            "number_of_platforms": _cell(row, indexes, "number of platforms"),
            "platform_type": _cell(row, indexes, "platform type"),
            "trolley_path": _cell(row, indexes, "trolleypath"),
            "trolley_path_sanction": _cell(row, indexes, "trolleypath sanction"),
        }
        if item["station_code"]:
            out.append(item)
    return out


def parse_fob_works(text: str) -> list[dict[str, Any]]:
    rows = parse_csv(text)
    if not rows:
        return []
    indexes = _header_map(rows[0])
    out: list[dict[str, Any]] = []
    current_group = "FOB"
    for row in rows[1:]:
        if any(normalize(cell) == "abss" for cell in row):
            current_group = "FOB ABSS"
            continue
        station_code = _cell(row, indexes, "station").upper() or (clean(row[1]).upper() if len(row) > 1 else "")
        if not station_code or station_code in {"STATION", "ABSS"}:
            continue
        item = {
            "work_type": current_group,
            "station_code": station_code,
            "work_name": f"{current_group} work at {station_code}",
            "tender_status": _cell(row, indexes, "tender status"),
            "loa_date": _cell(row, indexes, "loa date"),
            "progress": _cell(row, indexes, "progress of work"),
            "physical_progress": _cell(row, indexes, "physical progress"),
        }
        out.append(item)
    return out


def parse_pf_extension_works(text: str, work_type: str = "PF Extension") -> list[dict[str, Any]]:
    rows = parse_csv(text)
    if not rows:
        return []
    headers = rows[0]
    out: list[dict[str, Any]] = []
    for row in rows[2:]:
        station_code = clean(row[3] if work_type == "HAS" and len(row) > 3 else row[1] if len(row) > 1 else "").upper()
        if not station_code:
            continue
        item = {
            "work_type": work_type,
            "project_id": clean(row[1]) if work_type == "HAS" and len(row) > 1 else None,
            "cost": clean(row[2]) if work_type == "HAS" and len(row) > 2 else None,
            "station_code": station_code,
            "station_category": clean(row[4] if work_type == "HAS" and len(row) > 4 else row[2] if len(row) > 2 else ""),
            "platform_level": clean(row[5] if work_type == "HAS" and len(row) > 5 else row[3] if len(row) > 3 else ""),
            "existing_platform_length": " | ".join(clean(row[idx]) for idx in ([6, 7, 8] if work_type == "HAS" else [4, 5, 6, 7]) if idx < len(row) and clean(row[idx])),
            "sanction_date": clean(row[9] if work_type == "HAS" and len(row) > 9 else row[8] if len(row) > 8 else ""),
            "executive_agency": clean(row[10] if work_type == "HAS" and len(row) > 10 else row[9] if len(row) > 9 else ""),
            "progress": clean(row[11] if work_type == "HAS" and len(row) > 11 else row[10] if len(row) > 10 else ""),
            "tdc": clean(row[12] if work_type == "HAS" and len(row) > 12 else row[11] if len(row) > 11 else ""),
            "work_name": f"{work_type} at {station_code}",
        }
        out.append(item)
    return out


STATION_CODE_STOPWORDS = {
    "ABSS", "AND", "AS", "AT", "BASIC", "CAT", "CATG", "DIV", "DIVISION", "EXISTING", "FEASIBLE",
    "FOB", "FOR", "FULL", "HAS", "LENGTH", "LIFT", "NIL", "NO", "NONE", "NOT", "OF", "PF",
    "PLATFORM", "PROPOSED", "RAMP", "RAISING", "REQUIRED", "STATION", "STATIONS", "TO", "TOTAL",
    "WIP", "WITH", "WITHOUT", "WORK", "WORKS",
}


def extract_station_codes(value: Any) -> list[str]:
    text = clean(value).upper()
    if not text:
        return []
    codes = []
    for token in re.findall(r"\b[A-Z]{1,5}[A-Z0-9]?\b", text):
        if token in STATION_CODE_STOPWORDS:
            continue
        if re.fullmatch(r"NSG|HG|SG|YES|WIP|NIL|NA", token):
            continue
        if len(token) < 2:
            continue
        codes.append(token)
    return list(dict.fromkeys(codes))


def _xlsx_cell(row, index: int) -> str:
    return clean(row[index].value if index < len(row) else "")


def _status_for(statuses: dict[str, dict[str, Any]], code: str) -> dict[str, Any]:
    return statuses.setdefault(code, {
        "station_code": code,
        "category": None,
        "source_category": None,
        "station_detail_category_code": None,
        "pf_extension_wip": False,
        "pf_extension_proposed": False,
        "raising_extension_proposed": False,
        "platform_extension_work_proposed": False,
        "ramp_feasible": False,
        "fob_without": False,
        "fob_ramp_available": False,
        "fob_wip": False,
        "lift_available": False,
        "lift_proposed": False,
        "ramp_proposed": False,
        "not_feasible_lift_ramp": False,
        "source_rows": "",
        "status_text": "",
        "remarks": "",
    })


def _append_status_text(row: dict[str, Any], field: str, text: str) -> None:
    value = clean(text)
    if not value:
        return
    existing = clean(row.get(field))
    parts = [part for part in existing.split(" | ") if part] if existing else []
    if value not in parts:
        parts.append(value)
    row[field] = " | ".join(parts)


def _mark_station_codes(statuses: dict[str, dict[str, Any]], source: Any, *, flag: str, category: str, source_row: int, label: str, remarks: str = "") -> None:
    for code in extract_station_codes(source):
        row = _status_for(statuses, code)
        row[flag] = True
        row["category"] = row["category"] or category
        row["source_category"] = row["source_category"] or category
        _append_status_text(row, "source_rows", str(source_row))
        _append_status_text(row, "status_text", f"{label}: {clean(source)}")
        _append_status_text(row, "remarks", remarks)


def parse_platform_extension_workbook(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is required to import platform extension workbook") from exc

    workbook_path = Path(path)
    wb = load_workbook(workbook_path, data_only=True)
    if "PF Extn and Raising" not in wb.sheetnames:
        raise ValueError("PF Extn and Raising sheet was not found in the workbook")
    ws = wb["PF Extn and Raising"]
    rows = list(ws.iter_rows())
    summaries: list[dict[str, Any]] = []
    statuses: dict[str, dict[str, Any]] = {}

    for row_number in range(5, 14):
        row = rows[row_number - 1]
        category = _xlsx_cell(row, 1)
        if not category or normalize(category) == "total":
            continue
        item = {
            "summary_type": "platform_extension",
            "category": category,
            "station_count": to_int(_xlsx_cell(row, 2)),
            "full_length_platforms": to_int(_xlsx_cell(row, 3)),
            "work_under_progress": _xlsx_cell(row, 4),
            "pf_extension_proposed": _xlsx_cell(row, 5),
            "raising_extension_proposed": _xlsx_cell(row, 6),
            "remarks": _xlsx_cell(row, 7),
            "platform_extension_work_proposed": _xlsx_cell(row, 8),
            "existing_length": _xlsx_cell(row, 9),
            "required_length": _xlsx_cell(row, 10),
            "source_row": row_number,
        }
        summaries.append(item)
        _mark_station_codes(statuses, item["work_under_progress"], flag="pf_extension_wip", category=category, source_row=row_number, label="PF extension WIP", remarks=item["remarks"])
        _mark_station_codes(statuses, item["pf_extension_proposed"], flag="pf_extension_proposed", category=category, source_row=row_number, label="PF extension proposed", remarks=item["remarks"])
        _mark_station_codes(statuses, item["raising_extension_proposed"], flag="raising_extension_proposed", category=category, source_row=row_number, label="Raising and extension proposed", remarks=item["remarks"])
        _mark_station_codes(statuses, item["platform_extension_work_proposed"], flag="platform_extension_work_proposed", category=category, source_row=row_number, label="Platform extension work proposed", remarks=item["remarks"])

    for row_number in range(19, 28):
        row = rows[row_number - 1]
        category = _xlsx_cell(row, 1)
        if not category or normalize(category) == "total":
            continue
        item = {
            "summary_type": "accessibility",
            "category": category,
            "station_count": to_int(_xlsx_cell(row, 2)),
            "fob_ramps_stairs_available": _xlsx_cell(row, 3),
            "stations_without_fob": _xlsx_cell(row, 4),
            "stations_with_fob_ramp": _xlsx_cell(row, 5),
            "stations_fob_wip": _xlsx_cell(row, 6),
            "stations_with_lift": _xlsx_cell(row, 7),
            "stations_lift_proposed": _xlsx_cell(row, 8),
            "stations_ramp_proposed": _xlsx_cell(row, 9),
            "stations_not_feasible_lift_ramp": _xlsx_cell(row, 10),
            "remarks": _xlsx_cell(row, 11),
            "source_row": row_number,
        }
        summaries.append(item)
        _mark_station_codes(statuses, item["stations_without_fob"], flag="fob_without", category=category, source_row=row_number, label="Without FOB", remarks=item["remarks"])
        _mark_station_codes(statuses, item["stations_with_fob_ramp"], flag="fob_ramp_available", category=category, source_row=row_number, label="FOB/Subway ramp available", remarks=item["remarks"])
        _mark_station_codes(statuses, item["stations_fob_wip"], flag="fob_wip", category=category, source_row=row_number, label="FOB work in progress", remarks=item["remarks"])
        _mark_station_codes(statuses, item["stations_with_lift"], flag="lift_available", category=category, source_row=row_number, label="Lift available", remarks=item["remarks"])
        _mark_station_codes(statuses, item["stations_lift_proposed"], flag="lift_proposed", category=category, source_row=row_number, label="Lift proposed", remarks=item["remarks"])
        _mark_station_codes(statuses, item["stations_ramp_proposed"], flag="ramp_proposed", category=category, source_row=row_number, label="Ramp proposed", remarks=item["remarks"])
        _mark_station_codes(statuses, item["stations_not_feasible_lift_ramp"], flag="not_feasible_lift_ramp", category=category, source_row=row_number, label="Lift/Ramp not feasible", remarks=item["remarks"])

    ramp_feasible_text = _xlsx_cell(rows[28], 1)
    for code in extract_station_codes(ramp_feasible_text):
        row = _status_for(statuses, code)
        row["ramp_feasible"] = True
        _append_status_text(row, "source_rows", "29")
        _append_status_text(row, "status_text", "Station feasible for ramp")

    for row_number in range(40, min(len(rows), 95) + 1):
        row = rows[row_number - 1]
        category_code = _xlsx_cell(row, 4)
        for cell_index in (3, 6):
            for code in extract_station_codes(_xlsx_cell(row, cell_index)):
                item = _status_for(statuses, code)
                if category_code and not item.get("station_detail_category_code"):
                    item["station_detail_category_code"] = category_code
                _append_status_text(item, "source_rows", str(row_number))

    return {"summaries": summaries, "statuses": list(statuses.values())}


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


def passenger_amenity_sort_map() -> set[str]:
    return {"station_code", "station_name", "category", "section", "work_type", "tender_status", "sanction_date", "tdc", "platform_count", "available_good_condition", "ramp_feasible", "lift_proposed"}


def list_passenger_amenities(kind: str = "summary", q: str | None = None, station_code: str | None = None) -> list[dict[str, Any]]:
    session = SessionLocal()
    try:
        like = f"%{q}%" if q else None
        if kind == "norms":
            query = session.query(AmenityNorm)
            if like:
                query = query.filter((AmenityNorm.category.ilike(like)) | (AmenityNorm.amenity.ilike(like)) | (AmenityNorm.norm.ilike(like)))
            return [row_to_dict(row) for row in query.order_by(AmenityNorm.category, AmenityNorm.amenity, AmenityNorm.norm).all()]
        if kind == "infra":
            query = session.query(StationInfra, Station.division, Station.section).join(Station, Station.station_code == StationInfra.station_code, isouter=True)
            if like:
                query = query.filter((StationInfra.station_code.ilike(like)) | (StationInfra.station_name.ilike(like)) | (StationInfra.fob_details.ilike(like)))
            if station_code and station_code != "All":
                query = query.filter(StationInfra.station_code == station_code)
            return [{**row_to_dict(row), "division": division, "section": section} for row, division, section in query.order_by(StationInfra.station_code).all()]
        if kind == "platforms":
            query = session.query(PlatformDetail, Station.station_name, Station.division, Station.section).join(Station, Station.station_code == PlatformDetail.station_code, isouter=True)
            if like:
                query = query.filter((PlatformDetail.station_code.ilike(like)) | (PlatformDetail.platform.ilike(like)))
            if station_code and station_code != "All":
                query = query.filter(PlatformDetail.station_code == station_code)
            return [{**row_to_dict(row), "station_name": station_name, "division": division, "section": section} for row, station_name, division, section in query.order_by(PlatformDetail.station_code, PlatformDetail.platform).all()]
        if kind == "wheelchairs":
            query = session.query(WheelChairAvailability, Station.division).join(Station, Station.station_code == WheelChairAvailability.station_code, isouter=True)
            if like:
                query = query.filter((WheelChairAvailability.station_code.ilike(like)) | (WheelChairAvailability.station_name.ilike(like)) | (WheelChairAvailability.section.ilike(like)))
            if station_code and station_code != "All":
                query = query.filter(WheelChairAvailability.station_code == station_code)
            return [{**row_to_dict(row), "division": division} for row, division in query.order_by(WheelChairAvailability.station_code).all()]
        if kind == "trolley":
            query = session.query(TrolleyPath)
            if like:
                query = query.filter((TrolleyPath.station_code.ilike(like)) | (TrolleyPath.station_name.ilike(like)) | (TrolleyPath.section.ilike(like)) | (TrolleyPath.trolley_path.ilike(like)))
            if station_code and station_code != "All":
                query = query.filter(TrolleyPath.station_code == station_code)
            return [row_to_dict(row) for row in query.order_by(TrolleyPath.station_code).all()]
        if kind == "pa_works":
            query = session.query(PassengerAmenityWork, Station.station_name, Station.division, Station.section).join(Station, Station.station_code == PassengerAmenityWork.station_code, isouter=True)
            if like:
                query = query.filter((PassengerAmenityWork.station_code.ilike(like)) | (PassengerAmenityWork.work_name.ilike(like)) | (PassengerAmenityWork.work_type.ilike(like)) | (PassengerAmenityWork.progress.ilike(like)))
            if station_code and station_code != "All":
                query = query.filter(PassengerAmenityWork.station_code == station_code)
            return [{**row_to_dict(row), "station_name": station_name, "division": division, "section": section} for row, station_name, division, section in query.order_by(PassengerAmenityWork.work_type, PassengerAmenityWork.station_code).all()]
        if kind == "pf_extension":
            query = session.query(StationPlatformExtensionStatus, Station.station_name, Station.division, Station.section, Station.categorisation).join(Station, Station.station_code == StationPlatformExtensionStatus.station_code, isouter=True)
            if like:
                query = query.filter(
                    (StationPlatformExtensionStatus.station_code.ilike(like))
                    | (StationPlatformExtensionStatus.category.ilike(like))
                    | (StationPlatformExtensionStatus.source_category.ilike(like))
                    | (StationPlatformExtensionStatus.status_text.ilike(like))
                    | (StationPlatformExtensionStatus.remarks.ilike(like))
                )
            if station_code and station_code != "All":
                query = query.filter(StationPlatformExtensionStatus.station_code == station_code)
            return [
                {
                    **row_to_dict(row),
                    "station_name": station_name,
                    "division": division,
                    "section": section,
                    "categorisation": categorisation,
                }
                for row, station_name, division, section, categorisation in query.order_by(StationPlatformExtensionStatus.station_code).all()
            ]
        if kind == "pf_extension_summary":
            query = session.query(PlatformExtensionSummary)
            if like:
                query = query.filter((PlatformExtensionSummary.category.ilike(like)) | (PlatformExtensionSummary.remarks.ilike(like)) | (PlatformExtensionSummary.summary_type.ilike(like)))
            return [row_to_dict(row) for row in query.order_by(PlatformExtensionSummary.summary_type, PlatformExtensionSummary.category).all()]

        station_rows = session.query(Station).all()
        infra_by_station = {row.station_code: row for row in session.query(StationInfra).all()}
        wheel_by_station = {row.station_code: row for row in session.query(WheelChairAvailability).all()}
        trolley_by_station = {row.station_code: row for row in session.query(TrolleyPath).all()}
        platform_counts = dict(session.execute(select(PlatformDetail.station_code, func.count(PlatformDetail.platform_key)).group_by(PlatformDetail.station_code)).all())
        pa_work_counts = dict(session.execute(select(PassengerAmenityWork.station_code, func.count(PassengerAmenityWork.pa_work_key)).group_by(PassengerAmenityWork.station_code)).all())
        pf_status_by_station = {row.station_code: row for row in session.query(StationPlatformExtensionStatus).all()}
        rows = []
        for station in station_rows:
            if station_code and station_code != "All" and station.station_code != station_code:
                continue
            infra = infra_by_station.get(station.station_code)
            wheel = wheel_by_station.get(station.station_code)
            trolley = trolley_by_station.get(station.station_code)
            row = {
                "station_code": station.station_code,
                "station_name": station.station_name,
                "division": station.division,
                "section": station.section,
                "category": station.categorisation,
                "platform_type": station.platform_type,
                "platform_count": infra.platform_count if infra else station.number_of_platforms,
                "platform_detail_count": platform_counts.get(station.station_code, 0),
                "wheel_chairs": wheel.available_good_condition if wheel else None,
                "trolley_path": trolley.trolley_path if trolley else None,
                "pa_works": pa_work_counts.get(station.station_code, 0),
                "fob_details": infra.fob_details if infra else None,
                "ramp_feasible": pf_status_by_station.get(station.station_code).ramp_feasible if pf_status_by_station.get(station.station_code) else False,
                "lift_proposed": pf_status_by_station.get(station.station_code).lift_proposed if pf_status_by_station.get(station.station_code) else False,
                "pf_extension_proposed": pf_status_by_station.get(station.station_code).pf_extension_proposed if pf_status_by_station.get(station.station_code) else False,
            }
            if not q or any(normalize(q) in normalize(value) for value in row.values()):
                rows.append(row)
        return sorted(rows, key=lambda item: (item.get("station_name") or "", item.get("station_code") or ""))
    finally:
        session.close()


def get_passenger_amenity_reports() -> dict[str, Any]:
    session = SessionLocal()
    try:
        station_count = session.query(func.count(Station.station_code)).scalar() or 0
        infra_count = session.query(func.count(StationInfra.infra_key)).scalar() or 0
        platform_count = session.query(func.count(PlatformDetail.platform_key)).scalar() or 0
        wheelchair_stations = session.query(func.count(WheelChairAvailability.wheel_chair_key)).scalar() or 0
        trolley_yes = session.query(func.count(TrolleyPath.trolley_path_key)).filter(TrolleyPath.trolley_path.ilike("%yes%")).scalar() or 0
        trolley_no = session.query(func.count(TrolleyPath.trolley_path_key)).filter(TrolleyPath.trolley_path.ilike("%no%")).scalar() or 0
        pa_works = session.query(func.count(PassengerAmenityWork.pa_work_key)).scalar() or 0
        open_pa_works = session.query(func.count(PassengerAmenityWork.pa_work_key)).filter(~PassengerAmenityWork.progress.ilike("%complete%")).scalar() or 0
        norms = session.query(func.count(AmenityNorm.norm_key)).scalar() or 0
        pf_statuses = session.query(func.count(StationPlatformExtensionStatus.status_key)).scalar() or 0
        pf_wip = session.query(func.count(StationPlatformExtensionStatus.status_key)).filter(StationPlatformExtensionStatus.pf_extension_wip.is_(True)).scalar() or 0
        pf_proposed = session.query(func.count(StationPlatformExtensionStatus.status_key)).filter(StationPlatformExtensionStatus.pf_extension_proposed.is_(True)).scalar() or 0
        ramp_feasible = session.query(func.count(StationPlatformExtensionStatus.status_key)).filter(StationPlatformExtensionStatus.ramp_feasible.is_(True)).scalar() or 0
        lift_proposed = session.query(func.count(StationPlatformExtensionStatus.status_key)).filter(StationPlatformExtensionStatus.lift_proposed.is_(True)).scalar() or 0
        ramp_proposed = session.query(func.count(StationPlatformExtensionStatus.status_key)).filter(StationPlatformExtensionStatus.ramp_proposed.is_(True)).scalar() or 0
        not_feasible = session.query(func.count(StationPlatformExtensionStatus.status_key)).filter(StationPlatformExtensionStatus.not_feasible_lift_ramp.is_(True)).scalar() or 0
        return {
            "stations": station_count,
            "infra_records": infra_count,
            "platform_records": platform_count,
            "wheelchair_stations": wheelchair_stations,
            "trolley_path_yes": trolley_yes,
            "trolley_path_no": trolley_no,
            "pa_works": pa_works,
            "open_pa_works": open_pa_works,
            "norms": norms,
            "pf_extension_statuses": pf_statuses,
            "pf_extension_wip": pf_wip,
            "pf_extension_proposed": pf_proposed,
            "ramp_feasible": ramp_feasible,
            "lift_proposed": lift_proposed,
            "ramp_proposed": ramp_proposed,
            "not_feasible_lift_ramp": not_feasible,
            "coverage": {
                "infra": round((infra_count / station_count) * 100, 1) if station_count else 0,
                "wheelchairs": round((wheelchair_stations / station_count) * 100, 1) if station_count else 0,
                "pf_extension": round((pf_statuses / station_count) * 100, 1) if station_count else 0,
            },
        }
    finally:
        session.close()


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
        rows = []
        for work, wl, station_name, categorisation in query.order_by(Work.date_of_sanction.desc().nullslast(), Work.project_id).all():
            rows.append({
                **row_to_dict(work),
                "scope_type": wl.scope_type if wl else "Unlinked",
                "scope_value": wl.scope_value if wl else work.block_section_station,
                "station_code": wl.station_code if wl else None,
                "match_status": wl.match_status if wl else "Missing link",
                "station_name": station_name,
                "categorisation": categorisation,
            })
        return rows
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


def get_station_detail(station_code: str) -> dict[str, Any] | None:
    code = clean(station_code).upper()
    session = SessionLocal()
    try:
        station = session.get(Station, code)
        if not station:
            return None

        station_row = row_to_dict(station)
        units = list_units(station_code=code)
        earnings = list_earnings(station_code=code)
        earnings_by_unit: dict[str, list[dict[str, Any]]] = {}
        for earning in earnings:
            if earning.get("unit_no"):
                earnings_by_unit.setdefault(earning["unit_no"], []).append(earning)
        contracts = [
            {
                **unit,
                "earnings": earnings_by_unit.get(unit.get("unit_no"), []),
                "earnings_total": sum(to_money(row.get("amount")) for row in earnings_by_unit.get(unit.get("unit_no"), [])),
                "pending_receipts": sum(1 for row in earnings_by_unit.get(unit.get("unit_no"), []) if "pending" in normalize(row.get("receipt_type"))),
            }
            for unit in units
        ]

        works = list_works(station_code=code)
        infra = session.query(StationInfra).filter(StationInfra.station_code == code).one_or_none()
        platforms = session.query(PlatformDetail).filter(PlatformDetail.station_code == code).order_by(PlatformDetail.platform).all()
        wheelchairs = session.query(WheelChairAvailability).filter(WheelChairAvailability.station_code == code).one_or_none()
        trolley = session.query(TrolleyPath).filter(TrolleyPath.station_code == code).one_or_none()
        pa_works = session.query(PassengerAmenityWork).filter(PassengerAmenityWork.station_code == code).order_by(PassengerAmenityWork.work_type, PassengerAmenityWork.work_name).all()
        pf_extension = session.query(StationPlatformExtensionStatus).filter(StationPlatformExtensionStatus.station_code == code).one_or_none()
        norms = session.query(AmenityNorm).filter(AmenityNorm.category == station.categorisation).order_by(AmenityNorm.amenity, AmenityNorm.norm).all() if station.categorisation else []

        platform_lengths = [row.length_m for row in platforms if row.length_m is not None]
        amenities = {
            "infra": row_to_dict(infra) if infra else None,
            "platforms": [row_to_dict(row) for row in platforms],
            "wheelchairs": row_to_dict(wheelchairs) if wheelchairs else None,
            "trolley": row_to_dict(trolley) if trolley else None,
            "pa_works": [row_to_dict(row) for row in pa_works],
            "pf_extension_status": row_to_dict(pf_extension) if pf_extension else None,
            "norms": [row_to_dict(row) for row in norms],
        }
        amenity_summary = {
            "platforms": len(platforms),
            "platform_count_declared": infra.platform_count if infra else station.number_of_platforms,
            "total_platform_length": sum(platform_lengths),
            "shortest_platform": min(platform_lengths) if platform_lengths else None,
            "longest_platform": max(platform_lengths) if platform_lengths else None,
            "wheel_chairs": wheelchairs.available_good_condition if wheelchairs else None,
            "trolley_path": trolley.trolley_path if trolley else None,
            "fob_details": infra.fob_details if infra else None,
            "pa_works": len(pa_works),
            "open_pa_works": sum(1 for row in pa_works if "complete" not in normalize(row.progress)),
            "norms": len(norms),
            "pf_extension_wip": bool(pf_extension and pf_extension.pf_extension_wip),
            "pf_extension_proposed": bool(pf_extension and pf_extension.pf_extension_proposed),
            "raising_extension_proposed": bool(pf_extension and pf_extension.raising_extension_proposed),
            "platform_extension_work_proposed": bool(pf_extension and pf_extension.platform_extension_work_proposed),
            "ramp_feasible": bool(pf_extension and pf_extension.ramp_feasible),
            "lift_proposed": bool(pf_extension and pf_extension.lift_proposed),
            "ramp_proposed": bool(pf_extension and pf_extension.ramp_proposed),
            "not_feasible_lift_ramp": bool(pf_extension and pf_extension.not_feasible_lift_ramp),
        }
        return {
            "station": station_row,
            "contracts": contracts,
            "units": units,
            "earnings": earnings,
            "works": works,
            "amenities": amenities,
            "amenity_summary": amenity_summary,
        }
    finally:
        session.close()


def get_reports(today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    current_month_end = month_end(today)
    next_7 = today + timedelta(days=7)
    next_30 = today + timedelta(days=30)
    next_90 = today + timedelta(days=90)
    three_month_start = date(today.year, today.month, 1) - timedelta(days=62)

    session = SessionLocal()
    try:
        stations = session.query(Station).all()
        units = session.query(Unit, Station.station_name, Station.division, Station.section).join(Station, Station.station_code == Unit.station_code, isouter=True).all()
        earnings = session.query(Earning).all()
        works = session.query(Work, WorkLink, Station.station_name).join(WorkLink, WorkLink.project_id == Work.project_id, isouter=True).join(Station, Station.station_code == WorkLink.station_code, isouter=True).all()

        by_unit: dict[str, list[Earning]] = {}
        for earning in earnings:
            if earning.unit_no:
                by_unit.setdefault(earning.unit_no, []).append(earning)

        station_codes = {station.station_code for station in stations}
        unit_codes = {unit.unit_no for unit, *_ in units}
        station_with_units = {unit.station_code for unit, *_ in units if unit.station_code}
        station_with_works = {link.station_code for _, link, _ in works if link and link.station_code}
        station_with_earnings = {earning.station_code for earning in earnings if earning.station_code}

        by_station_category: dict[str, int] = {}
        by_division: dict[str, int] = {}
        by_section: dict[str, int] = {}
        for station in stations:
            by_station_category[clean(station.categorisation) or "Unknown"] = by_station_category.get(clean(station.categorisation) or "Unknown", 0) + 1
            by_division[clean(station.division) or "Unknown"] = by_division.get(clean(station.division) or "Unknown", 0) + 1
            by_section[clean(station.section) or "Unknown"] = by_section.get(clean(station.section) or "Unknown", 0) + 1

        active_units = [(unit, station_name, division, section) for unit, station_name, division, section in units if is_active_status(unit.unit_status)]
        inactive_units = len(units) - len(active_units)
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_unit_category: dict[str, int] = {}
        for unit, *_ in units:
            by_status[clean(unit.unit_status) or "Unknown"] = by_status.get(clean(unit.unit_status) or "Unknown", 0) + 1
            by_type[clean(unit.type_of_unit) or "Unknown"] = by_type.get(clean(unit.type_of_unit) or "Unknown", 0) + 1
            by_unit_category[clean(unit.station_category) or "Unknown"] = by_unit_category.get(clean(unit.station_category) or "Unknown", 0) + 1

        license_earnings = [row for row in earnings if is_license_fee_row(row)]
        pending_receipts = [row for row in earnings if "pending" in normalize(row.receipt_type)]
        current_month_license = [
            row for row in license_earnings
            if (parsed := parse_date_value(row.date_of_receipt or row.mr_date)) and parsed.year == today.year and parsed.month == today.month
        ]
        recent_license = [
            row for row in license_earnings
            if (parsed := parse_date_value(row.date_of_receipt or row.mr_date)) and parsed >= three_month_start
        ]

        earnings_by_month: dict[str, int] = {}
        earnings_by_head: dict[str, int] = {}
        for row in earnings:
            receipt_date = parse_date_value(row.date_of_receipt or row.mr_date)
            month_key = receipt_date.strftime("%Y-%m") if receipt_date else "Unknown"
            head_key = clean(row.payment_head) or "Unknown"
            earnings_by_month[month_key] = earnings_by_month.get(month_key, 0) + to_money(row.amount)
            earnings_by_head[head_key] = earnings_by_head.get(head_key, 0) + to_money(row.amount)

        works_by_status: dict[str, int] = {}
        works_by_scope: dict[str, int] = {}
        works_by_section: dict[str, int] = {}
        works_by_station: dict[str, int] = {}
        works_seen: set[str] = set()
        completed_work_count = 0
        pending_work_count = 0
        for work, link, station_name in works:
            if work.project_id not in works_seen:
                works_seen.add(work.project_id)
                status_key = clean(work.status) or "Unknown"
                section_key = clean(work.section) or "Unknown"
                works_by_status[status_key] = works_by_status.get(status_key, 0) + 1
                works_by_section[section_key] = works_by_section.get(section_key, 0) + 1
                if re.search(r"complete|done", status_key, flags=re.I):
                    completed_work_count += 1
                else:
                    pending_work_count += 1
            scope_key = clean(link.scope_type) if link else "Unlinked"
            station_key = clean(link.station_code) if link and link.station_code else clean(station_name) or "Unlinked"
            works_by_scope[scope_key or "Unknown"] = works_by_scope.get(scope_key or "Unknown", 0) + 1
            works_by_station[station_key] = works_by_station.get(station_key, 0) + 1

        alerts: list[dict[str, Any]] = []
        bucket_counts = {
            "overdue": 0,
            "due_this_month": 0,
            "due_next_7_days": 0,
            "due_next_30_days": 0,
            "due_next_90_days": 0,
            "needs_review": 0,
        }
        estimated_overdue_amount = 0

        for unit, station_name, division, section in active_units:
            unit_license_rows = [row for row in by_unit.get(unit.unit_no, []) if is_license_fee_row(row)]
            paid_through_values = [
                parsed for row in unit_license_rows
                if (parsed := parse_date_value(row.period_to or row.date_of_receipt or row.mr_date))
                and "pending" not in normalize(row.receipt_type)
            ]
            last_paid_through = max(paid_through_values) if paid_through_values else None
            contract_to = parse_date_value(unit.contract_to)
            license_fee_amount = to_money(unit.license_fee)

            if last_paid_through is None:
                months_pending = 1
                alert_bucket = "needs_review"
            elif last_paid_through < today:
                months_pending = month_delta(last_paid_through + timedelta(days=1), current_month_end)
                alert_bucket = "overdue"
            elif last_paid_through <= current_month_end:
                months_pending = 0
                alert_bucket = "due_this_month"
            else:
                months_pending = 0
                alert_bucket = None

            days_to_contract_end = (contract_to - today).days if contract_to else None
            if contract_to and today <= contract_to <= next_7:
                contract_bucket = "due_next_7_days"
            elif contract_to and today <= contract_to <= next_30:
                contract_bucket = "due_next_30_days"
            elif contract_to and today <= contract_to <= next_90:
                contract_bucket = "due_next_90_days"
            else:
                contract_bucket = None

            final_bucket = alert_bucket or contract_bucket
            if not final_bucket:
                continue

            bucket_counts[final_bucket] = bucket_counts.get(final_bucket, 0) + 1
            estimated_pending = months_pending * license_fee_amount
            if final_bucket == "overdue":
                estimated_overdue_amount += estimated_pending

            alerts.append({
                "unit_no": unit.unit_no,
                "station_code": unit.station_code,
                "station_name": station_name,
                "division": division,
                "section": section,
                "licensee_name": unit.licensee_name,
                "type_of_unit": unit.type_of_unit,
                "unit_status": unit.unit_status,
                "license_fee": unit.license_fee,
                "license_fee_amount": license_fee_amount,
                "contract_to": unit.contract_to,
                "last_paid_through": last_paid_through.isoformat() if last_paid_through else None,
                "days_to_contract_end": days_to_contract_end,
                "months_pending": months_pending,
                "estimated_pending_amount": estimated_pending,
                "alert_bucket": final_bucket,
            })

        bucket_order = {
            "overdue": 0,
            "needs_review": 1,
            "due_this_month": 2,
            "due_next_7_days": 3,
            "due_next_30_days": 4,
            "due_next_90_days": 5,
        }
        alerts.sort(key=lambda row: (bucket_order.get(row["alert_bucket"], 9), row["days_to_contract_end"] is None, row["days_to_contract_end"] or 99999, row["unit_no"] or ""))

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "as_of": today.isoformat(),
            "overview": {
                "stations": len(stations),
                "units": len(units),
                "active_units": len(active_units),
                "earnings_total": sum(to_money(row.amount) for row in earnings),
                "works": len(works_seen),
                "open_works": pending_work_count,
                "critical_alerts": bucket_counts["overdue"] + bucket_counts["needs_review"],
            },
            "stations": {
                "total": len(stations),
                "with_units": len(station_with_units),
                "without_units": max(len(station_codes - station_with_units), 0),
                "with_works": len(station_with_works),
                "with_earnings": len(station_with_earnings),
                "by_category": [{"label": key, "value": value} for key, value in sorted(by_station_category.items())],
                "by_division": [{"label": key, "value": value} for key, value in sorted(by_division.items())],
                "by_section": [{"label": key, "value": value} for key, value in sorted(by_section.items())],
            },
            "units": {
                "total": len(units),
                "active": len(active_units),
                "inactive": inactive_units,
                "missing_license_fee": sum(1 for unit, *_ in active_units if not to_money(unit.license_fee)),
                "by_status": [{"label": key, "value": value} for key, value in sorted(by_status.items())],
                "by_type": [{"label": key, "value": value} for key, value in sorted(by_type.items())],
                "by_category": [{"label": key, "value": value} for key, value in sorted(by_unit_category.items())],
            },
            "earnings": {
                "total_receipts": len(earnings),
                "total_amount": sum(to_money(row.amount) for row in earnings),
                "license_fee_receipts": len(license_earnings),
                "license_fee_collected": sum(to_money(row.amount) for row in license_earnings),
                "pending_receipts": len(pending_receipts),
                "pending_receipt_amount": sum(to_money(row.amount) for row in pending_receipts),
                "current_month_license_collected": sum(to_money(row.amount) for row in current_month_license),
                "last_3_month_license_collected": sum(to_money(row.amount) for row in recent_license),
                "by_month": [{"label": key, "value": value} for key, value in sorted(earnings_by_month.items())[-12:]],
                "by_head": [{"label": key, "value": value} for key, value in sorted(earnings_by_head.items(), key=lambda item: item[1], reverse=True)[:10]],
            },
            "works": {
                "total": len(works_seen),
                "completed": completed_work_count,
                "pending": pending_work_count,
                "by_status": [{"label": key, "value": value} for key, value in sorted(works_by_status.items(), key=lambda item: item[1], reverse=True)],
                "by_scope": [{"label": key, "value": value} for key, value in sorted(works_by_scope.items(), key=lambda item: item[1], reverse=True)],
                "by_section": [{"label": key, "value": value} for key, value in sorted(works_by_section.items(), key=lambda item: item[1], reverse=True)[:12]],
                "by_station": [{"label": key, "value": value} for key, value in sorted(works_by_station.items(), key=lambda item: item[1], reverse=True)[:12]],
            },
            "data_quality": {
                "units_missing_station": sum(1 for unit, *_ in units if unit.station_code and unit.station_code not in station_codes),
                "earnings_missing_unit": sum(1 for row in earnings if row.unit_no and row.unit_no not in unit_codes),
                "earnings_missing_station": sum(1 for row in earnings if row.station_code and row.station_code not in station_codes),
                "works_unmatched_station": sum(1 for _, link, _ in works if link and link.scope_type == "Station" and link.station_code and link.station_code not in station_codes),
                "units_missing_license_fee": sum(1 for unit, *_ in units if not to_money(unit.license_fee)),
            },
            "license_fee_alerts": {
                **bucket_counts,
                "estimated_overdue_amount": estimated_overdue_amount,
                "rows": alerts[:300],
            },
        }
    finally:
        session.close()
