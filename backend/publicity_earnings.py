"""Main Sheet receipt ledger. Never imports pivots or contract/payment schedules."""
from __future__ import annotations

import calendar
import hashlib
import io
import json
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel

MONTHS = list(range(4, 13)) + [1, 2, 3]
MONEY = {"LF": "licence_fee", "Penalty": "penalty", "App Based cab": "app_based_cab",
         "PUB earnings": "pub_earnings", "NFR earnings": "nfr_earnings", "GST": "gst",
         "With GST Total": "total_with_gst"}
TEXT = {"Details": "details", "Firm": "firm", "Location": "location",
        "Detailed Head": "detailed_head", "Allocation Code": "allocation_code",
        "DD # & Date": "receipt_reference"}


def text(value):
    if value is None or str(value).strip() == "":
        return None
    return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value).strip()


def money(value, cell):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        result = Decimal(str(value).replace(",", ""))
        if not result.is_finite() or abs(result) >= Decimal("1e14"):
            raise InvalidOperation
        return result.quantize(Decimal("0.0000000001"))
    except InvalidOperation:
        raise ValueError(f"Main Sheet {cell}: invalid amount {value!r}") from None


def parse_workbook(content: bytes):
    book = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    formulas = load_workbook(io.BytesIO(content), data_only=False, read_only=True)
    try:
        if "Main Sheet" not in book.sheetnames:
            raise ValueError('Workbook must contain a sheet named "Main Sheet".')
        sheet = book["Main Sheet"]
        cells = sheet.iter_rows()
        headers = [text(c.value) for c in next(cells)]
        required = ["Year", "Month", "Date", "Policy new", "Policy", *MONEY, *TEXT]
        for header in required:
            if headers.count(header) != 1:
                raise ValueError(f"Main Sheet must contain exactly one {header!r} column.")
        formula_rows = formulas["Main Sheet"].iter_rows(min_row=2)
        rows, warnings = [], []
        for number, (values, formula_cells) in enumerate(zip(cells, formula_rows), 2):
            raw = {h: c.value for h, c in zip(headers, values) if h}
            if not any(v is not None for v in raw.values()):
                continue
            for h, c, f in zip(headers, values, formula_cells):
                if h in MONEY and (c.data_type == "e" or (f.data_type == "f" and c.value is None)):
                    raise ValueError(f"Main Sheet {c.coordinate}: formula error or missing cached value. Recalculate and save in Excel.")
            fy = text(raw["Year"])
            if not fy or not re.fullmatch(r"20\d{2}-\d{2}", fy) or int(fy[5:]) != (int(fy[:4]) + 1) % 100:
                raise ValueError(f"Main Sheet row {number}: invalid financial year {fy!r}.")
            dt = raw["Date"]
            parsed_date = dt.date() if isinstance(dt, datetime) else dt if isinstance(dt, date) else None
            # Google Sheets exports unformatted dates as Excel serial numbers.
            if isinstance(dt, (int, float)) and not isinstance(dt, bool):
                try:
                    serial_date = from_excel(dt, epoch=book.epoch)
                    if isinstance(serial_date, datetime):
                        parsed_date = serial_date.date()
                except (ValueError, OverflowError):
                    pass
            if dt and parsed_date is None:
                for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
                    try:
                        parsed_date = datetime.strptime(str(dt).strip(), fmt).date()
                        break
                    except ValueError:
                        pass
            month_text = text(raw["Month"])
            month = next((m for m in range(1, 13) if month_text and calendar.month_name[m].lower() == month_text.lower()), None)
            if month_text and month is None:
                warnings.append({"row": number, "message": f"Unrecognised month: {month_text}; excluded from monthly comparisons."})
            elif month is None:
                warnings.append({"row": number, "message": "Month missing; retained only in annual totals."})
            if parsed_date is None:
                warnings.append({"row": number, "message": "Date missing or ambiguous; original value retained."})
            elif (parsed_date.year if parsed_date.month >= 4 else parsed_date.year - 1) != int(fy[:4]) or (month and parsed_date.month != month):
                warnings.append({"row": number, "message": "Date disagrees with Year/Month; reporting uses source Year/Month."})
            row = {"source_row": number, "financial_year": fy, "month": month, "receipt_date": parsed_date,
                   "policy": text(raw["Policy new"]) or text(raw["Policy"]),
                   "source_values": {k: v.isoformat() if isinstance(v, (datetime, date)) else v for k, v in raw.items()}}
            row.update({field: text(raw.get(header)) for header, field in TEXT.items()})
            for header, field in MONEY.items():
                try:
                    row[field] = money(raw.get(header), f"row {number}, {header}")
                except ValueError:
                    if field in ("pub_earnings", "nfr_earnings"):
                        raise
                    row[field] = None
                    warnings.append({"row": number, "message": f"Non-numeric {header}; original retained, amount left missing."})
            rows.append(row)
        if not rows:
            raise ValueError("Main Sheet contains no earnings rows.")
        # Hash only Main Sheet data: edits to a pivot or a filename cannot duplicate receipts.
        digest = hashlib.sha256(json.dumps([r["source_values"] for r in rows], sort_keys=True, default=str).encode()).hexdigest()
        return {"import_id": digest, "rows": rows, "warnings": warnings}
    finally:
        book.close()
        formulas.close()


def rounded(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["financial_year"]].append(row)
    result = []
    for year, records in sorted(groups.items()):
        totals = {}
        for key in MONEY.values():
            values = [r[key] for r in records if r[key] is not None]
            totals[key] = rounded(sum(values, Decimal(0))) if values else None
        months = sorted({r["month"] for r in records if r["month"]}, key=MONTHS.index)
        result.append({"financial_year": year, "row_count": len(records), "months": months,
                       "unallocated_rows": sum(r["month"] is None for r in records),
                       "missing_pub_amounts": sum(r["pub_earnings"] is None for r in records),
                       "missing_nfr_amounts": sum(r["nfr_earnings"] is None for r in records), **totals})
    return result


def apply_import(session, parsed, filename):
    from models import PublicityEarning, PublicityEarningsCurrent, PublicityEarningsImport
    # The migration seeds one pointer row; its lock serializes snapshot activation.
    current = session.query(PublicityEarningsCurrent).filter_by(dataset="main_sheet").with_for_update().one()
    digest = parsed["import_id"]
    if current.import_id == digest:
        return {"status": "unchanged", "row_count": len(parsed["rows"]), "import_id": digest}
    if not session.get(PublicityEarningsImport, digest):
        session.add(PublicityEarningsImport(import_id=digest, filename=filename, row_count=len(parsed["rows"]), warnings=parsed["warnings"]))
        session.flush()
        session.add_all(PublicityEarning(import_id=digest, **row) for row in parsed["rows"])
        session.flush()
    current.import_id = digest
    session.flush()
    return {"status": "imported", "row_count": len(parsed["rows"]), "import_id": digest}


def read_ledger(session):
    from models import PublicityEarning, PublicityEarningsCurrent, PublicityEarningsImport
    current = session.get(PublicityEarningsCurrent, "main_sheet")
    if not current or not current.import_id:
        return [], None
    batch = session.get(PublicityEarningsImport, current.import_id)
    records = session.query(PublicityEarning).filter_by(import_id=current.import_id).order_by(PublicityEarning.source_row).all()
    rows = [{c.name: getattr(record, c.name) for c in PublicityEarning.__table__.columns if c.name != "import_id"} for record in records]
    return rows, {"filename": batch.filename, "sheet": "Main Sheet", "import_id": batch.import_id,
                  "imported_at": batch.imported_at.isoformat(), "row_count": batch.row_count, "warnings": batch.warnings}


def dashboard(rows, source, year=None, policy=None, head=None, query=None):
    options = {"years": sorted({r["financial_year"] for r in rows}),
               "policies": sorted({r["policy"] for r in rows if r["policy"]}),
               "heads": sorted({r["detailed_head"] for r in rows if r["detailed_head"]})}
    filtered = [r for r in rows if (not policy or r["policy"] == policy) and (not head or r["detailed_head"] == head)
                and (not query or query.casefold() in " ".join(str(r.get(k) or "") for k in ["details", "firm", "location", "receipt_reference"]).casefold())]
    annual = summarize(filtered)
    selected = year or (options["years"][-1] if options["years"] else None)
    selected_rows = [r for r in filtered if r["financial_year"] == selected]
    months = []
    for month in MONTHS:
        subset = [r for r in selected_rows if r["month"] == month]
        totals = summarize(subset)
        months.append({"month": month, "label": calendar.month_abbr[month], "row_count": len(subset),
                       "pub_earnings": totals[0]["pub_earnings"] if totals else None,
                       "nfr_earnings": totals[0]["nfr_earnings"] if totals else None})
    policies = []
    for name in sorted({r["policy"] or "Unspecified" for r in selected_rows}):
        totals = summarize([r for r in selected_rows if (r["policy"] or "Unspecified") == name])[0]
        policies.append({"policy": name, **totals})
    # Missing months cannot be assumed zero. Compare only months represented in both years.
    previous = f"{int(selected[:4])-1}-{int(selected[:4]) % 100:02d}" if selected else None
    previous_rows = [r for r in filtered if r["financial_year"] == previous]
    common = sorted({r["month"] for r in selected_rows if r["month"]} & {r["month"] for r in previous_rows if r["month"]}, key=MONTHS.index)
    comparison = {"previous_year": previous, "months": common}
    for field in ("pub_earnings", "nfr_earnings"):
        current_values = [r[field] for r in selected_rows if r["month"] in common]
        previous_values = [r[field] for r in previous_rows if r["month"] in common]
        now = sum((v for v in current_values if v is not None), Decimal(0))
        before = sum((v for v in previous_values if v is not None), Decimal(0))
        valid = bool(common) and None not in current_values and None not in previous_values
        comparison[field] = {"current": rounded(now), "previous": rounded(before),
                             "change_percent": rounded((now-before)/before*100) if valid and before else None}
    dates = [r["receipt_date"] for r in rows if r["receipt_date"]]
    # Do not return GST identities, contact information or raw notes in the public ledger.
    public_rows = [{k: (str(v) if isinstance(v, Decimal) else v.isoformat() if isinstance(v, date) else v)
                    for k, v in r.items() if k != "source_values"} for r in selected_rows]
    return {"source": source, "options": options, "selected_year": selected, "annual": annual,
            "monthly": months, "policies": policies, "comparison": comparison, "rows": public_rows,
            "latest_receipt_date": max(dates).isoformat() if dates else None}


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Validate or import only Main Sheet publicity earnings.")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--apply", action="store_true", help="Activate this complete ledger snapshot in configured database")
    args = parser.parse_args()
    parsed = parse_workbook(args.workbook.read_bytes())
    result = {"row_count": len(parsed["rows"]), "annual": summarize(parsed["rows"]), "warnings": parsed["warnings"]}
    if args.apply:
        from database import SessionLocal
        with SessionLocal.begin() as session:
            result["import"] = apply_import(session, parsed, args.workbook.name)
    print(json.dumps(result, indent=2))
