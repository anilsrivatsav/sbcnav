from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from mcdo.auth import administrator
from database import SessionLocal
from api_utils import envelope
from publicity_earnings import apply_import, dashboard, parse_workbook, read_ledger, summarize

router = APIRouter(prefix="/api/publicity-earnings", tags=["Publicity earnings"])


@router.get("")
def get_earnings(year: str | None = Query(None, pattern=r"^20\d{2}-\d{2}$"),
                 policy: str | None = None, head: str | None = None,
                 q: str | None = Query(None, max_length=200)):
    with SessionLocal() as session:
        rows, source = read_ledger(session)
    return envelope(dashboard(rows, source, year, policy, head, q))


@router.post("/import", dependencies=[Depends(administrator)])
def import_earnings(file: UploadFile = File(...), dry_run: bool = True):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(422, "Upload an .xlsx workbook containing Main Sheet.")
    content = file.file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "Workbook exceeds the 20 MB limit.")
    try:
        parsed = parse_workbook(content)
    except Exception as exc:
        # Parsing happens before any database write; malformed files cannot partially import.
        raise HTTPException(422, f"Workbook validation failed: {exc}") from exc
    result = {"row_count": len(parsed["rows"]), "annual": summarize(parsed["rows"]),
              "warnings": parsed["warnings"], "sheet": "Main Sheet", "dry_run": dry_run}
    if not dry_run:
        with SessionLocal.begin() as session:
            result.update(apply_import(session, parsed, file.filename.replace("\\", "/").split("/")[-1]))
    return envelope(result)
