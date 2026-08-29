from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import String, Text, UniqueConstraint, case, func, select, update

from database import SessionLocal
from models import Base, DataChangeLog, Work


REFERENCE_TARGETS = {
    "station_code": ("stations", "station_code"),
    "unit_no": ("units", "unit_no"),
    "project_id": ("works", "project_id"),
    "receipt_key": ("earnings", "receipt_key"),
    "contract_key": ("commercial_contracts", "contract_key"),
    "contract_id": ("contract_registry_contracts", "contract_id"),
}


def _is_text(column) -> bool:
    return isinstance(column.type, (String, Text))


def _trim_is_safe(table, column) -> bool:
    if column.primary_key or column.foreign_keys or column.unique:
        return False
    return not any(
        isinstance(constraint, UniqueConstraint) and constraint.columns.contains_column(column)
        for constraint in table.constraints
    )


def _issue(table: str, column: str | None, kind: str, count: int, description: str, *, severity: str = "warning", resolution: str | None = None) -> dict[str, Any]:
    return {
        "id": f"{table}:{column or '-'}:{kind}",
        "table": table,
        "column": column,
        "kind": kind,
        "count": int(count or 0),
        "description": description,
        "severity": severity,
        "resolution": resolution,
        "resolvable": bool(resolution),
    }


def _work_progress_is_complete(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return bool(re.search(r"(^|\D)100(?:\.0+)?\s*%?($|\D)", text) or re.search(r"\bcomplete(?:d)?\b|\bdone\b", text))


def _work_status_is_complete(value: Any) -> bool:
    return bool(re.search(r"\bcomplete(?:d)?\b|\bdone\b|\bclosed\b", str(value or "").strip().lower()))


def check_postgres_consistency() -> dict[str, Any]:
    """Inspect every application table without mutating PostgreSQL."""
    session = SessionLocal()
    try:
        issues: list[dict[str, Any]] = []
        tables: list[dict[str, Any]] = []
        metadata_tables = {table.name: table for table in Base.metadata.sorted_tables}

        for table in Base.metadata.sorted_tables:
            text_columns = [column for column in table.columns if _is_text(column)]
            aggregates = [func.count().label("row_count")]
            labels: list[tuple[str, Any, str]] = []
            for index, column in enumerate(text_columns):
                trim_label = f"trim_{index}"
                aggregates.append(func.sum(case((column.is_not(None) & (column != func.trim(column)), 1), else_=0)).label(trim_label))
                labels.append((trim_label, column, "whitespace"))
                if not column.nullable and not column.primary_key:
                    blank_label = f"blank_{index}"
                    aggregates.append(func.sum(case((func.trim(column) == "", 1), else_=0)).label(blank_label))
                    labels.append((blank_label, column, "required_blank"))

            result = session.execute(select(*aggregates).select_from(table)).mappings().one()
            table_issue_count = 0
            for label, column, kind in labels:
                count = int(result[label] or 0)
                if not count:
                    continue
                table_issue_count += count
                if kind == "whitespace":
                    safe = _trim_is_safe(table, column)
                    issues.append(_issue(
                        table.name,
                        column.name,
                        kind,
                        count,
                        "Leading or trailing whitespace makes matching and filtering inconsistent.",
                        resolution="trim_text" if safe else None,
                    ))
                else:
                    issues.append(_issue(
                        table.name,
                        column.name,
                        kind,
                        count,
                        "A required text field is blank and needs manual source correction.",
                        severity="danger",
                    ))

            checked_references: set[tuple[str, str]] = set()
            for column in table.columns:
                foreign_keys = list(column.foreign_keys)
                for foreign_key in foreign_keys:
                    target = foreign_key.column
                    checked_references.add((column.name, target.table.name))
                    orphan_count = session.scalar(
                        select(func.count())
                        .select_from(table.outerjoin(target.table, column == target))
                        .where(column.is_not(None), target.is_(None))
                    ) or 0
                    if orphan_count:
                        table_issue_count += orphan_count
                        issues.append(_issue(
                            table.name,
                            column.name,
                            "orphan_reference",
                            orphan_count,
                            f"Value does not match {target.table.name}.{target.name}.",
                            severity="danger",
                        ))

                target_spec = REFERENCE_TARGETS.get(column.name)
                if not target_spec or target_spec[0] == table.name or (column.name, target_spec[0]) in checked_references:
                    continue
                target_table = metadata_tables.get(target_spec[0])
                if target_table is None:
                    continue
                target = target_table.c[target_spec[1]]
                orphan_count = session.scalar(
                    select(func.count())
                    .select_from(table.outerjoin(target_table, column == target))
                    .where(column.is_not(None), target.is_(None))
                ) or 0
                if orphan_count:
                    table_issue_count += orphan_count
                    issues.append(_issue(
                        table.name,
                        column.name,
                        "unmatched_reference",
                        orphan_count,
                        f"Value does not match the canonical {target_table.name}.{target.name} register.",
                        severity="danger",
                    ))

            tables.append({
                "table": table.name,
                "rows": int(result["row_count"] or 0),
                "issue_count": table_issue_count,
                "status": "attention" if table_issue_count else "clean",
            })

        works = session.query(Work.project_id, Work.status, Work.physical_progress).all()
        progress_complete = [row for row in works if _work_progress_is_complete(row.physical_progress) and not _work_status_is_complete(row.status)]
        status_complete = [row for row in works if _work_status_is_complete(row.status) and row.physical_progress and not _work_progress_is_complete(row.physical_progress)]
        if progress_complete:
            issues.append(_issue(
                "works",
                "status",
                "work_progress_complete_status_open",
                len(progress_complete),
                "Physical progress is complete but work status is not marked completed.",
                severity="danger",
                resolution="normalize_work_completion",
            ))
        if status_complete:
            issues.append(_issue(
                "works",
                "physical_progress",
                "work_status_complete_progress_open",
                len(status_complete),
                "Work status is completed but physical progress does not indicate completion; review manually.",
                severity="danger",
            ))

        issues.sort(key=lambda row: (0 if row["severity"] == "danger" else 1, -row["count"], row["table"], row.get("column") or ""))
        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL",
            "tables_checked": len(tables),
            "rows_checked": sum(table["rows"] for table in tables),
            "issues_total": sum(issue["count"] for issue in issues),
            "resolvable_total": sum(issue["count"] for issue in issues if issue["resolvable"]),
            "tables": tables,
            "issues": issues,
        }
    finally:
        session.close()


def resolve_postgres_inconsistency(resolution: str, table_name: str | None = None, column_name: str | None = None) -> dict[str, Any]:
    session = SessionLocal()
    try:
        with session.begin():
            if resolution == "trim_text":
                table = Base.metadata.tables.get(table_name or "")
                if table is None or not column_name or column_name not in table.c:
                    raise ValueError("Unknown table or column")
                column = table.c[column_name]
                if not _is_text(column) or not _trim_is_safe(table, column):
                    raise ValueError("This column cannot be trimmed automatically")
                values = {column_name: func.trim(column)}
                if "updated_at" in table.c:
                    values["updated_at"] = datetime.now(timezone.utc)
                result = session.execute(
                    update(table)
                    .where(column.is_not(None), column != func.trim(column))
                    .values(**values)
                )
                resolved = int(result.rowcount or 0)
                detail = f"Trimmed {table_name}.{column_name}"
            elif resolution == "normalize_work_completion":
                candidates = session.query(Work).all()
                resolved = 0
                for work in candidates:
                    if _work_progress_is_complete(work.physical_progress) and not _work_status_is_complete(work.status):
                        work.status = "Completed"
                        work.updated_at = datetime.now(timezone.utc)
                        resolved += 1
                detail = "Aligned completed physical progress with work status"
            else:
                raise ValueError("Unknown or unsupported resolution")

            session.add(DataChangeLog(
                resource="data_quality",
                record_key=f"{table_name or 'works'}:{column_name or resolution}",
                action="resolve",
                source="settings",
                details=f"{detail}; {resolved} rows",
                created_at=datetime.now(timezone.utc),
            ))
        return {"resolution": resolution, "resolved": resolved, "message": detail}
    finally:
        session.close()
