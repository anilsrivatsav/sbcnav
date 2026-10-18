import io
import os
import unittest
from datetime import date
from decimal import Decimal

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models import PublicityEarning, PublicityEarningsCurrent, PublicityEarningsImport
from publicity_earnings import MONEY, TEXT, apply_import, dashboard, parse_workbook, read_ledger, summarize


def workbook(records, extra=False):
    book = Workbook()
    sheet = book.active
    sheet.title = "Main Sheet"
    headers = list(dict.fromkeys(["Year", "Month", "Date", "Policy new", "Policy", *MONEY, *TEXT]))
    sheet.append(headers)
    for record in records:
        sheet.append([record.get(h) for h in headers])
    if extra:
        book.create_sheet("Ignore me").append(["PUB earnings", 999999999])
    result = io.BytesIO(); book.save(result)
    return result.getvalue()


def receipt(**overrides):
    return {"Year": "2026-27", "Month": "April", "PUB earnings": 10.125, "NFR earnings": 12.125, "Policy new": "RDN", **overrides}


class EarningsTests(unittest.TestCase):
    def test_unformatted_google_sheets_date_serial(self):
        data = parse_workbook(workbook([receipt(**{"Month": "October", "Date": 46298})]))
        self.assertEqual(data["rows"][0]["receipt_date"], date(2026, 10, 3))
        self.assertEqual(data["rows"][0]["source_values"]["Date"], 46298)
        self.assertEqual(dashboard(data["rows"], None)["latest_receipt_date"], "2026-10-03")
        self.assertEqual(data["warnings"], [])

    def test_only_main_sheet_and_precision(self):
        data = parse_workbook(workbook([receipt(), receipt()], extra=True))
        self.assertEqual(len(data["rows"]), 2)  # identical rows can be legitimate separate receipts
        self.assertEqual(summarize(data["rows"])[0]["pub_earnings"], "20.25")
        self.assertEqual(data["import_id"], parse_workbook(workbook([receipt(), receipt()]))["import_id"])

    def test_missing_month_not_in_monthly_comparison(self):
        data = parse_workbook(workbook([receipt(), receipt(**{"Month": None, "PUB earnings": 90}), receipt(**{"Year": "2025-26", "PUB earnings": 5}), receipt(**{"Year": "2025-26", "Month": "March", "PUB earnings": 999})]))
        result = dashboard(data["rows"], None)
        self.assertEqual(result["annual"][-1]["pub_earnings"], "100.13")
        self.assertEqual(result["comparison"]["months"], [4])
        self.assertEqual(result["comparison"]["pub_earnings"]["change_percent"], "102.50")
        self.assertIsNone(result["monthly"][1]["pub_earnings"])

    def test_invalid_amount_and_uncached_formula_rejected(self):
        for amount in ("wrong", "=1+2", "#N/A"):
            with self.assertRaises(ValueError):
                parse_workbook(workbook([receipt(**{"PUB earnings": amount})]))

    def test_ambiguous_date_and_optional_amount_retained(self):
        result = parse_workbook(workbook([receipt(**{"Date": "10-1-2025 ?", "With GST Total": "GST-ID"})]))
        self.assertIsNone(result["rows"][0]["receipt_date"])
        self.assertIsNone(result["rows"][0]["total_with_gst"])
        self.assertEqual(result["rows"][0]["source_values"]["With GST Total"], "GST-ID")
        self.assertEqual(len(result["warnings"]), 2)

    def test_versioning_reimport_and_rollback(self):
        engine = create_engine("sqlite+pysqlite:///:memory:")
        for model in (PublicityEarningsImport, PublicityEarningsCurrent, PublicityEarning):
            model.__table__.create(engine)
        with Session(engine) as session:
            session.add(PublicityEarningsCurrent(dataset="main_sheet")); session.commit()
            parsed = parse_workbook(workbook([receipt()]))
            apply_import(session, parsed, "test.xlsx"); session.commit()
            self.assertEqual(apply_import(session, parsed, "renamed.xlsx")["status"], "unchanged")
            changed = parse_workbook(workbook([receipt(**{"PUB earnings": 20})]))
            apply_import(session, changed, "test.xlsx"); session.rollback()
            self.assertEqual(read_ledger(session)[0][0]["pub_earnings"], Decimal("10.125"))
            apply_import(session, changed, "test.xlsx"); session.commit()
            self.assertEqual(len(read_ledger(session)[0]), 1)
            self.assertEqual(session.query(PublicityEarningsImport).count(), 2)
            self.assertEqual(session.query(PublicityEarning).count(), 2)

    def test_filters_and_missing_comparison_values(self):
        data = parse_workbook(workbook([receipt(**{"PUB earnings": None}), receipt(**{"Year": "2025-26"})]))
        self.assertIsNone(dashboard(data["rows"], None)["comparison"]["pub_earnings"]["change_percent"])
        self.assertEqual(dashboard(data["rows"], None, policy="OTHER")["rows"], [])


if __name__ == "__main__":
    unittest.main()
