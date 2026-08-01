from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import func

from database import SessionLocal, engine
from models import DataChangeLog, Earning, EarningLink, Station, Unit
from services import hash_row

UNIT_SHEET = "UNITS BASE DATA"
EARNING_SHEET = "EARNINGS BASE DATA"

UNIT_FIELDS = (
    "sl_no",
    "unit_no",
    "type_of_unit",
    "station_code",
    "station_category",
    "old_category",
    "pf_no",
    "pegged_location",
    "reservation_category",
    "allotment_type",
    "licensee_name",
    "license_fee",
    "contract_from",
    "contract_to",
    "paid_upto",
    "unit_status",
)

EARNING_FIELDS = (
    "sl_no",
    "date_of_receipt",
    "raw_unit_no",
    "raw_station_code",
    "pf_no",
    "licensee_name",
    "payment_head",
    "payment_sub_head",
    "period_from",
    "period_to",
    "amount",
    "gst",
    "receipt_type",
    "mr_no",
    "mr_date",
    "ua_case",
)

EXPECTED_UNIT_HEADERS = {
    1: "SL NO.",
    2: "UNIT NO.",
    3: "TYPE OF UNIT",
    4: "STATION",
    5: "STATION CATEGORY",
    7: "PF NO",
    8: "PEGGED LOCATION",
    9: "RESERVATION CATEGORY",
    10: "TYPE OF ALLOTMENT",
    11: "NAME OF LICENSEE",
    12: "LICENSE FEE",
    13: "CONTRACT PERIOD",
    15: "LICENSE FEE",
    16: "UNIT STATUS",
}

EXPECTED_EARNING_HEADERS = {
    1: "SL. NO.",
    2: "DATE OF RECEIPT",
    3: "UNIT NO.",
    4: "STATION",
    5: "PF NO.",
    6: "NAME OF LICENSEE",
    7: "PAYMENT HEAD",
    8: "PAYMENT SUB-HEAD",
    9: "PERIOD",
    11: "AMOUNT",
    12: "GST",
    13: "RECIEPT TYPE",
    14: "MR NO/UTS NO/ CHALLAN NO",
    15: "MR DATE",
    16: "U/A CASE",
}


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def identifier(value: Any) -> str | None:
    text = clean(value)
    return text.upper() if text else None


def integer(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(round(value))
    text = str(value).replace(",", "").replace("INR", "").replace("Rs.", "").strip()
    try:
        return int(round(float(text)))
    except ValueError:
        return None


def date_iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = clean(value)
    if not text:
        return None
    for pattern in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return text


def normalized_header(value: Any) -> str:
    return " ".join((clean(value) or "").upper().split())


def validate_headers(sheet, expected: dict[int, str], subheaders: dict[int, str]) -> None:
    errors: list[str] = []
    for column, wanted in expected.items():
        actual = normalized_header(sheet.cell(2, column).value)
        if actual != wanted:
            errors.append(f"{sheet.title}!{sheet.cell(2, column).coordinate}: expected {wanted!r}, got {actual!r}")
    for column, wanted in subheaders.items():
        actual = normalized_header(sheet.cell(3, column).value)
        if actual != wanted:
            errors.append(f"{sheet.title}!{sheet.cell(3, column).coordinate}: expected {wanted!r}, got {actual!r}")
    if errors:
        raise ValueError("Workbook layout validation failed:\n" + "\n".join(errors))


def parse_units(sheet) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    skipped_labels = 0
    seen: set[str] = set()
    for row_number in range(4, sheet.max_row + 1):
        values = [sheet.cell(row_number, column).value for column in range(1, 17)]
        if not any(value not in (None, "") for value in values):
            continue
        raw = dict(zip(UNIT_FIELDS, values, strict=True))
        unit_no = identifier(raw["unit_no"])
        if not unit_no:
            skipped_labels += 1
            continue
        if unit_no in seen:
            raise ValueError(f"Duplicate unit number {unit_no!r} at {UNIT_SHEET} row {row_number}")
        seen.add(unit_no)
        rows.append(
            {
                "sl_no": integer(raw["sl_no"]),
                "unit_no": unit_no,
                "type_of_unit": clean(raw["type_of_unit"]),
                "station_code": identifier(raw["station_code"]),
                "station_category": clean(raw["station_category"]),
                "old_category": clean(raw["old_category"]),
                "pf_no": clean(raw["pf_no"]),
                "pegged_location": clean(raw["pegged_location"]),
                "reservation_category": clean(raw["reservation_category"]),
                "allotment_type": clean(raw["allotment_type"]),
                "licensee_name": clean(raw["licensee_name"]),
                "license_fee": clean(integer(raw["license_fee"])),
                "contract_from": date_iso(raw["contract_from"]),
                "contract_to": date_iso(raw["contract_to"]),
                "unit_status": clean(raw["unit_status"]),
                "_paid_upto": date_iso(raw["paid_upto"]),
                "_source_row": row_number,
            }
        )
    return rows, {"skipped_category_labels": skipped_labels}


def parse_earnings(sheet) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_serials: set[int] = set()
    for row_number in range(4, sheet.max_row + 1):
        values = [sheet.cell(row_number, column).value for column in range(1, 17)]
        if not any(value not in (None, "") for value in values):
            continue
        raw = dict(zip(EARNING_FIELDS, values, strict=True))
        sl_no = integer(raw["sl_no"])
        if sl_no is None:
            raise ValueError(f"Missing earning serial number at {EARNING_SHEET} row {row_number}")
        if sl_no in seen_serials:
            raise ValueError(f"Duplicate earning serial number {sl_no} at {EARNING_SHEET} row {row_number}")
        seen_serials.add(sl_no)
        source = {
            "sl_no": sl_no,
            "date_of_receipt": date_iso(raw["date_of_receipt"]),
            "raw_unit_no": identifier(raw["raw_unit_no"]),
            "raw_station_code": identifier(raw["raw_station_code"]),
            "pf_no": clean(raw["pf_no"]),
            "licensee_name": clean(raw["licensee_name"]),
            "payment_head": clean(raw["payment_head"]),
            "payment_sub_head": clean(raw["payment_sub_head"]),
            "period_from": date_iso(raw["period_from"]),
            "period_to": date_iso(raw["period_to"]),
            "amount": integer(raw["amount"]),
            "gst": integer(raw["gst"]),
            "receipt_type": clean(raw["receipt_type"]),
            "mr_no": clean(raw["mr_no"]),
            "mr_date": date_iso(raw["mr_date"]),
            "ua_case": clean(raw["ua_case"]),
            "_source_row": row_number,
        }
        source["receipt_key"] = hash_row("earning-base-data", source)
        rows.append(source)
    return rows


def load_source(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    workbook = load_workbook(path, data_only=True)
    missing_sheets = [name for name in (UNIT_SHEET, EARNING_SHEET) if name not in workbook.sheetnames]
    if missing_sheets:
        raise ValueError(f"Missing required worksheet(s): {', '.join(missing_sheets)}")

    unit_sheet = workbook[UNIT_SHEET]
    earning_sheet = workbook[EARNING_SHEET]
    validate_headers(unit_sheet, EXPECTED_UNIT_HEADERS, {13: "FROM", 14: "TO", 15: "PAID UPTO"})
    validate_headers(earning_sheet, EXPECTED_EARNING_HEADERS, {9: "FROM", 10: "TO"})

    units, unit_notes = parse_units(unit_sheet)
    earnings = parse_earnings(earning_sheet)
    if not units:
        raise ValueError("No unit records were found")
    if not earnings:
        raise ValueError("No earning records were found")
    return units, earnings, unit_notes


def reconcile(
    units: list[dict[str, Any]],
    earnings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with SessionLocal() as session:
        station_codes = {code for (code,) in session.query(Station.station_code).all()}
        existing_units = {unit_no for (unit_no,) in session.query(Unit.unit_no).all()}
        current = {
            "units": session.query(func.count(Unit.unit_no)).scalar() or 0,
            "earnings": session.query(func.count(Earning.earning_key)).scalar() or 0,
            "earning_links": session.query(func.count(EarningLink.id)).scalar() or 0,
        }

    source_unit_codes = {row["unit_no"] for row in units}
    missing_unit_stations = sorted(
        {row["station_code"] for row in units if row["station_code"] and row["station_code"] not in station_codes}
    )
    if missing_unit_stations:
        raise ValueError("Unit station codes missing from station master: " + ", ".join(missing_unit_stations))

    prepared: list[dict[str, Any]] = []
    unlinked_units: dict[str, int] = {}
    invalid_stations: dict[str, int] = {}
    for source in earnings:
        raw_unit = source["raw_unit_no"]
        raw_station = source["raw_station_code"]
        matched_unit = raw_unit if raw_unit in source_unit_codes else None
        matched_station = raw_station if raw_station in station_codes else None
        if raw_unit and not matched_unit:
            unlinked_units[raw_unit] = unlinked_units.get(raw_unit, 0) + 1
        if raw_station and not matched_station:
            invalid_stations[raw_station] = invalid_stations.get(raw_station, 0) + 1
        prepared.append(
            {
                "receipt_key": source["receipt_key"],
                "sl_no": source["sl_no"],
                "date_of_receipt": source["date_of_receipt"],
                "unit_no": matched_unit,
                "station_code": matched_station,
                "pf_no": source["pf_no"],
                "licensee_name": source["licensee_name"],
                "payment_head": source["payment_head"],
                "payment_sub_head": source["payment_sub_head"],
                "period_from": source["period_from"],
                "period_to": source["period_to"],
                "amount": source["amount"],
                "gst": source["gst"],
                "receipt_type": source["receipt_type"],
                "mr_no": source["mr_no"],
                "mr_date": source["mr_date"],
                "ua_case": source["ua_case"],
            }
        )

    report = {
        "database": {
            "dialect": engine.dialect.name,
            "current": current,
        },
        "source": {
            "units": len(units),
            "earnings": len(earnings),
            "earning_amount_total": sum(row["amount"] or 0 for row in prepared),
            "gst_total": sum(row["gst"] or 0 for row in prepared),
        },
        "reconciliation": {
            "new_unit_numbers": len(source_unit_codes - existing_units),
            "existing_unit_numbers": len(source_unit_codes & existing_units),
            "units_absent_from_source": len(existing_units - source_unit_codes),
            "linked_earning_rows": sum(1 for row in prepared if row["unit_no"]),
            "unlinked_earning_rows": sum(1 for row in prepared if not row["unit_no"]),
            "unlinked_unit_labels": dict(sorted(unlinked_units.items())),
            "invalid_station_labels": dict(sorted(invalid_stations.items())),
        },
    }
    return prepared, report


def public_unit_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def apply_import(
    workbook_path: Path,
    units: list[dict[str, Any]],
    earnings: list[dict[str, Any]],
    report: dict[str, Any],
) -> None:
    now = datetime.now(timezone.utc)
    source_unit_numbers = {row["unit_no"] for row in units}
    session = SessionLocal()
    try:
        with session.begin():
            # Earnings are an authoritative snapshot and are rebuilt below. Removing
            # their links first also permits case-only unit-key normalization.
            session.query(EarningLink).delete(synchronize_session=False)
            session.query(Earning).delete(synchronize_session=False)

            existing_units = {unit.unit_no: unit for unit in session.query(Unit).all()}
            existing_units_casefold = {unit_no.upper(): unit for unit_no, unit in existing_units.items()}
            mutable_unit_fields = [
                column.name
                for column in Unit.__table__.columns
                if column.name
                not in {"unit_no", "created_at", "first_seen_at", "updated_at", "last_seen_at", "is_active", "source_hash"}
            ]
            inserted_units = 0
            updated_units = 0
            renamed_units = 0
            for source in units:
                payload = public_unit_row(source)
                payload["source_hash"] = hash_row("unit-base-data", payload)
                unit = existing_units.get(payload["unit_no"]) or existing_units_casefold.get(payload["unit_no"].upper())
                if unit is None:
                    unit = Unit(
                        **payload,
                        created_at=now,
                        updated_at=now,
                        first_seen_at=now,
                        last_seen_at=now,
                        is_active=True,
                    )
                    session.add(unit)
                    inserted_units += 1
                else:
                    if unit.unit_no != payload["unit_no"]:
                        unit.unit_no = payload["unit_no"]
                        renamed_units += 1
                    for field in mutable_unit_fields:
                        setattr(unit, field, payload.get(field))
                    unit.source_hash = payload["source_hash"]
                    unit.updated_at = now
                    unit.last_seen_at = now
                    unit.is_active = True
                    updated_units += 1

            session.flush()
            deactivated_units = (
                session.query(Unit)
                .filter(Unit.unit_no.notin_(source_unit_numbers))
                .update(
                    {Unit.is_active: False, Unit.updated_at: now, Unit.last_seen_at: now},
                    synchronize_session=False,
                )
            )
            session.flush()

            earning_models: list[Earning] = []
            for row in earnings:
                source_hash = hash_row("earning-base-data", row)
                earning_models.append(
                    Earning(
                        **row,
                        source_hash=source_hash,
                        created_at=now,
                        updated_at=now,
                        first_seen_at=now,
                        last_seen_at=now,
                        is_active=True,
                    )
                )
            session.add_all(earning_models)
            session.flush()
            session.add_all(
                [
                    EarningLink(
                        receipt_key=row["receipt_key"],
                        unit_no=row["unit_no"],
                        station_code=row["station_code"],
                        match_status="Matched" if row["unit_no"] else "Missing unit",
                    )
                    for row in earnings
                ]
            )
            session.add(
                DataChangeLog(
                    resource="catering",
                    record_key=None,
                    action="replace_import",
                    source="xlsx",
                    details=(
                        f"{len(units)} units and {len(earnings)} earnings imported from "
                        f"{workbook_path.name}; {report['reconciliation']['linked_earning_rows']} earnings linked"
                    ),
                    created_at=now,
                )
            )
            session.flush()
            transaction_totals = {
                "active_units": session.query(func.count(Unit.unit_no)).filter(Unit.is_active.is_(True)).scalar() or 0,
                "earnings": session.query(func.count(Earning.earning_key)).scalar() or 0,
                "earning_links": session.query(func.count(EarningLink.id)).scalar() or 0,
                "earning_amount_total": session.query(func.coalesce(func.sum(Earning.amount), 0)).scalar() or 0,
            }
            if transaction_totals != {
                "active_units": len(units),
                "earnings": len(earnings),
                "earning_links": len(earnings),
                "earning_amount_total": report["source"]["earning_amount_total"],
            }:
                raise RuntimeError(f"In-transaction verification failed: {transaction_totals}")

        report["applied"] = {
            "inserted_units": inserted_units,
            "updated_units": updated_units,
            "renamed_units": renamed_units,
            "deactivated_units": deactivated_units,
            "replaced_earnings": len(earnings),
            "rebuilt_earning_links": len(earnings),
        }
    finally:
        session.close()


def verify(report: dict[str, Any]) -> None:
    with SessionLocal() as session:
        database = {
            "units": session.query(func.count(Unit.unit_no)).filter(Unit.is_active.is_(True)).scalar() or 0,
            "earnings": session.query(func.count(Earning.earning_key)).scalar() or 0,
            "earning_links": session.query(func.count(EarningLink.id)).scalar() or 0,
            "linked_earnings": session.query(func.count(EarningLink.id)).filter(EarningLink.unit_no.is_not(None)).scalar()
            or 0,
            "earning_amount_total": session.query(func.coalesce(func.sum(Earning.amount), 0)).scalar() or 0,
            "gst_total": session.query(func.coalesce(func.sum(Earning.gst), 0)).scalar() or 0,
        }
    expected = report["source"]
    if database["units"] != expected["units"]:
        raise RuntimeError(f"Verification failed: expected {expected['units']} active units, got {database['units']}")
    if database["earnings"] != expected["earnings"] or database["earning_links"] != expected["earnings"]:
        raise RuntimeError("Verification failed: earning or earning-link row counts differ from the source")
    if database["earning_amount_total"] != expected["earning_amount_total"]:
        raise RuntimeError("Verification failed: earning amount total differs from the source")
    report["verified"] = database


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and import updated catering unit and earning base data.")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--apply", action="store_true", help="Write to PostgreSQL. Without this flag, runs validation only.")
    args = parser.parse_args()

    workbook_path = args.workbook.resolve()
    if not workbook_path.exists():
        raise FileNotFoundError(workbook_path)
    if engine.dialect.name != "postgresql":
        raise RuntimeError(f"PostgreSQL is required; connected dialect is {engine.dialect.name!r}")

    units, raw_earnings, notes = load_source(workbook_path)
    earnings, report = reconcile(units, raw_earnings)
    report["workbook"] = str(workbook_path)
    report["source"].update(notes)
    report["mode"] = "apply" if args.apply else "dry-run"
    if args.apply:
        apply_import(workbook_path, units, earnings, report)
        verify(report)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
