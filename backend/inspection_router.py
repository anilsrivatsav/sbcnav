from __future__ import annotations

import json
import logging
import hashlib
import hmac
import io
import os
from html import escape
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, File, Header, HTTPException, Query, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import func

from api_utils import envelope
from database import SessionLocal
from inspection_schemas import (
    FindingStatusUpdate,
    InspectionCreate,
    InspectionStatusUpdate,
    AmenityFindingRequest,
    MobileDeviceStateUpdate,
    SyncPushRequest,
)
from inspection_service import (
    process_operation,
    seed_default_template,
    template_to_dict,
    transition_finding_status,
    transition_inspection_status,
    upsert_finding,
    upsert_inspection,
)
from models import (
    Inspection,
    InspectionEvidence,
    InspectionFinding,
    InspectionNote,
    InspectionResponse,
    InspectionTemplate,
    MobileChange,
    MobileDeviceState,
    Station,
    Work,
)
from services import get_station_detail, row_to_dict


router = APIRouter(prefix="/api/mobile/v1", tags=["Mobile inspections"])
logger = logging.getLogger(__name__)


_SYNC_ENTITY_MODELS = {
    "inspection": Inspection,
    "response": InspectionResponse,
    "finding": InspectionFinding,
    "evidence": InspectionEvidence,
    "note": InspectionNote,
}


def _server_entity(session, entity_type: str, entity_id: str):
    model = _SYNC_ENTITY_MODELS.get(entity_type)
    if not model:
        return None
    return session.get(model, entity_id)


def _conflict_payload(session, entity_type: str, entity_id: str) -> dict | None:
    record = _server_entity(session, entity_type, entity_id)
    if not record:
        return None
    payload = row_to_dict(record)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "server_version": payload.get("server_version"),
        "record": payload,
    }


@router.post("/devices/{device_id}/state")
def update_device_state(device_id: str, payload: MobileDeviceStateUpdate):
    """Record the latest offline cache and sync state for a device."""
    device_id = device_id.strip()
    if not device_id or len(device_id) > 128:
        raise HTTPException(status_code=422, detail="device_id must be 1-128 characters")
    session = SessionLocal()
    try:
        state = session.get(MobileDeviceState, device_id)
        if state is None:
            state = MobileDeviceState(device_id=device_id)
            session.add(state)
        for key, value in payload.model_dump(exclude_none=True).items():
            setattr(state, key, value)
        state.last_seen_at = datetime.now(timezone.utc)
        session.commit()
        return envelope(row_to_dict(state), "device cache state recorded")
    finally:
        session.close()


@router.get("/templates")
def list_templates():
    session = SessionLocal()
    try:
        seed_default_template(session)
        session.commit()
        rows = (
            session.query(InspectionTemplate)
            .filter(InspectionTemplate.is_active.is_(True))
            .order_by(InspectionTemplate.domain, InspectionTemplate.name, InspectionTemplate.version.desc())
            .all()
        )
        return envelope([template_to_dict(row) for row in rows], "ok")
    finally:
        session.close()


@router.get("/bootstrap")
def bootstrap(station_limit: int = Query(default=500, ge=1, le=2000)):
    session = SessionLocal()
    try:
        seed_default_template(session)
        session.commit()
        stations = (
            session.query(Station)
            .filter(
                Station.is_active.is_(True),
                func.lower(func.trim(Station.categorisation)).notin_(("", "test", "non-commercial")),
            )
            .order_by(Station.station_name, Station.station_code)
            .limit(station_limit)
            .all()
        )
        templates = (
            session.query(InspectionTemplate)
            .filter(InspectionTemplate.is_active.is_(True))
            .order_by(InspectionTemplate.name, InspectionTemplate.version.desc())
            .all()
        )
        works = (
            session.query(Work)
            .filter(Work.is_active.is_(True))
            .order_by(Work.source_sn.asc().nullslast(), Work.work_key)
            .all()
        )
        latest_work_update = session.query(func.max(Work.updated_at)).scalar()
        cursor = session.query(MobileChange.sequence).order_by(MobileChange.sequence.desc()).limit(1).scalar() or 0
        return envelope(
            {
                "stations": [row_to_dict(row) for row in stations],
                "templates": [template_to_dict(row) for row in templates],
                "all_works": [row_to_dict(row) for row in works],
                "portfolio_totals": {
                    "stations": len(stations),
                    "works": len(works),
                },
                "data_version": latest_work_update.isoformat() if latest_work_update else str(cursor),
                "cursor": cursor,
            },
            "bootstrap ready",
        )
    finally:
        session.close()


@router.get("/sync/conflicts/{entity_type}/{entity_id}")
def sync_conflict(entity_type: str, entity_id: str):
    """Return the current server record so an offline client can merge and retry."""
    session = SessionLocal()
    try:
        if entity_type not in _SYNC_ENTITY_MODELS:
            raise HTTPException(status_code=422, detail="Unsupported synchronized entity type")
        conflict = _conflict_payload(session, entity_type, entity_id)
        if not conflict:
            raise HTTPException(status_code=404, detail="Synchronized record not found")
        return envelope(conflict, "current server record ready")
    finally:
        session.close()


@router.get("/offline/station-details")
def offline_station_details(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=25),
    section: str | None = Query(default=None, max_length=128),
    station_codes: str | None = Query(default=None, max_length=4000),
):
    session = SessionLocal()
    try:
        base_query = session.query(Station.station_code).filter(
            Station.is_active.is_(True),
            func.lower(func.trim(Station.categorisation)).notin_(("", "test", "non-commercial")),
        )
        if section and section.strip():
            base_query = base_query.filter(Station.section == section.strip())
        selected_codes = {
            code.strip().upper()
            for code in (station_codes or "").split(",")
            if code.strip()
        }
        if selected_codes:
            base_query = base_query.filter(Station.station_code.in_(selected_codes))
        total = base_query.count()
        codes = [
            row[0]
            for row in base_query.order_by(
                Station.station_name,
                Station.station_code,
            )
            .offset(offset)
            .limit(limit)
            .all()
        ]
        items = []
        for code in codes:
            detail = get_station_detail(code)
            if detail:
                items.append({"station_code": code, "detail": detail})
        next_offset = offset + len(codes)
        return envelope(
            {
                "items": items,
                "total": total,
                "offset": offset,
                "next_offset": next_offset,
                "has_more": next_offset < total,
                "selection": {
                    "section": section.strip() if section else None,
                    "station_codes": sorted(selected_codes),
                },
            },
            "offline station details ready",
        )
    finally:
        session.close()


@router.get("/stations/{station_code}/360")
def station_360(station_code: str):
    detail = get_station_detail(station_code.strip().upper())
    if not detail:
        raise HTTPException(status_code=404, detail="Station not found")
    return envelope(detail, "ok")


@router.post("/stations/{station_code}/amenity-findings")
def create_amenity_findings(station_code: str, payload: AmenityFindingRequest):
    """Convert missing Station 360 norms into deduplicated inspection findings."""
    station_code = station_code.strip().upper()
    detail = get_station_detail(station_code)
    if not detail:
        raise HTTPException(status_code=404, detail="Station not found")
    session = SessionLocal()
    try:
        inspection = session.get(Inspection, payload.inspection_id)
        if not inspection:
            raise HTTPException(status_code=404, detail="Inspection not found")
        if inspection.station_code != station_code:
            raise HTTPException(status_code=422, detail="Inspection belongs to a different station")
        missing = detail.get("amenity_compliance", {}).get("missing", [])
        selected = set(payload.norm_keys or [])
        if selected:
            missing = [row for row in missing if row.get("norm_key") in selected]
        if not missing:
            raise HTTPException(status_code=422, detail="No missing amenity norms were selected")
        created = []
        skipped = []
        session.rollback()
        with session.begin():
            for row in missing:
                label = row.get("amenity") or row.get("norm") or "Amenity norm"
                title = f"Missing amenity norm: {label}"
                existing = session.query(InspectionFinding).filter(
                    InspectionFinding.inspection_id == payload.inspection_id,
                    InspectionFinding.station_code == station_code,
                    InspectionFinding.title == title,
                    InspectionFinding.status.notin_(["verified", "closed"]),
                ).first()
                if existing:
                    skipped.append(existing.finding_id)
                    continue
                category = str(row.get("category") or "").lower()
                severity = "high" if "divyang" in category or "mea" in category else "medium" if "recommended" in category else "low"
                description = f"{row.get('norm') or label}. Required quantity: {row.get('quantity') or 'Not specified'}."
                result = upsert_finding(session, {
                    "finding_id": str(uuid4()),
                    "inspection_id": payload.inspection_id,
                    "station_code": station_code,
                    "title": title,
                    "description": description,
                    "severity": severity,
                    "status": "open",
                    "responsible_party": payload.responsible_party,
                    "target_date": payload.target_date,
                    "repeat_observation": False,
                })
                created.append(result)
        return envelope({"created": created, "skipped": skipped, "total_created": len(created)}, "amenity findings created")
    finally:
        session.close()


@router.get("/inspections")
def list_inspections(
    station_code: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    session = SessionLocal()
    try:
        query = session.query(Inspection)
        if station_code:
            query = query.filter(Inspection.station_code == station_code.strip().upper())
        if status:
            query = query.filter(Inspection.status == status)
        rows = query.order_by(Inspection.updated_at.desc()).limit(limit).all()
        return envelope([row_to_dict(row) for row in rows], "ok")
    finally:
        session.close()


@router.get("/inspections/{inspection_id}")
def inspection_detail(inspection_id: str):
    session = SessionLocal()
    try:
        inspection = session.get(Inspection, inspection_id)
        if not inspection:
            raise HTTPException(status_code=404, detail="Inspection not found")
        responses = (
            session.query(InspectionResponse)
            .filter(InspectionResponse.inspection_id == inspection_id)
            .order_by(InspectionResponse.section_code, InspectionResponse.question_code)
            .all()
        )
        findings = (
            session.query(InspectionFinding)
            .filter(InspectionFinding.inspection_id == inspection_id)
            .order_by(InspectionFinding.created_at.desc())
            .all()
        )
        evidence = (
            session.query(InspectionEvidence)
            .filter(InspectionEvidence.inspection_id == inspection_id)
            .order_by(InspectionEvidence.created_at.desc())
            .all()
        )
        notes = (
            session.query(InspectionNote)
            .filter(InspectionNote.inspection_id == inspection_id)
            .order_by(InspectionNote.created_at.desc())
            .all()
        )
        response_rows = []
        for response in responses:
            row = row_to_dict(response)
            if response.response_json:
                row["response_json"] = json.loads(response.response_json)
            response_rows.append(row)
        return envelope(
            {
                "inspection": row_to_dict(inspection),
                "responses": response_rows,
                "findings": [row_to_dict(row) for row in findings],
                "evidence": [
                    {
                        "evidence_id": row.evidence_id,
                        "inspection_id": row.inspection_id,
                        "response_id": row.response_id,
                        "question_code": row.question_code,
                        "mime_type": row.mime_type,
                        "caption": row.caption,
                        "context": row.context,
                        "created_at": row.created_at,
                        "server_version": row.server_version,
                    }
                    for row in evidence
                ],
                "notes": [row_to_dict(row) for row in notes],
            },
            "ok",
        )
    finally:
        session.close()


@router.get("/inspections/{inspection_id}/report")
def inspection_report(inspection_id: str):
    """Generate a PostgreSQL-backed inspection PDF with an integrity fingerprint."""
    session = SessionLocal()
    try:
        inspection = session.get(Inspection, inspection_id)
        if not inspection:
            raise HTTPException(status_code=404, detail="Inspection not found")
        station = session.get(Station, inspection.station_code)
        findings = session.query(InspectionFinding).filter(
            InspectionFinding.inspection_id == inspection_id,
        ).order_by(InspectionFinding.severity.desc(), InspectionFinding.created_at).all()
        evidence_count = session.query(func.count(InspectionEvidence.evidence_id)).filter(
            InspectionEvidence.inspection_id == inspection_id,
        ).scalar() or 0
        notes_count = session.query(func.count(InspectionNote.note_id)).filter(
            InspectionNote.inspection_id == inspection_id,
        ).scalar() or 0
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
        except ImportError as exc:
            raise HTTPException(status_code=503, detail="PDF generation dependency is not installed") from exc

        buffer = io.BytesIO()
        document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="SmallMuted", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#667085"), leading=10))
        styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontSize=12, leading=15, spaceBefore=10, spaceAfter=5, textColor=colors.HexColor("#123b59")))
        story = [
            Paragraph("RAIL INSPECTION REPORT", styles["Title"]),
            Paragraph(f"Station: <b>{escape(station.station_name if station else inspection.station_code)}</b> ({escape(inspection.station_code)})", styles["Normal"]),
            Spacer(1, 6),
        ]
        metadata = [
            ["Inspector", inspection.inspector_name or "-", "Inspection type", inspection.inspection_type or "-"],
            ["Status", inspection.status or "-", "Score", f"{inspection.score}%" if inspection.score is not None else "-"],
            ["Started", inspection.started_at.isoformat() if inspection.started_at else "-", "Completed", inspection.completed_at.isoformat() if inspection.completed_at else "-"],
            ["Evidence", str(evidence_count), "Notes", str(notes_count)],
        ]
        table = Table(metadata, colWidths=[28 * mm, 64 * mm, 28 * mm, 64 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f7fa")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d5dde5")),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([table, Paragraph("Findings and action points", styles["Section"])])
        if findings:
            finding_rows = [["Severity", "Title", "Responsible", "Target", "Status"]]
            for finding in findings:
                finding_rows.append([
                    escape(finding.severity or "-"),
                    Paragraph(escape(finding.title or finding.description or "-"), styles["Normal"]),
                    Paragraph(escape(finding.responsible_party or "Unassigned"), styles["Normal"]),
                    escape(finding.target_date or "-"),
                    escape(finding.status or "-"),
                ])
            finding_table = Table(finding_rows, colWidths=[23 * mm, 72 * mm, 36 * mm, 25 * mm, 25 * mm], repeatRows=1)
            finding_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123b59")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d5dde5")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(finding_table)
            for finding in findings:
                if finding.description:
                    story.extend([Spacer(1, 4), Paragraph(f"<b>{escape(finding.title)}</b>: {escape(finding.description)}", styles["SmallMuted"])])
        else:
            story.append(Paragraph("No findings recorded.", styles["Normal"]))
        story.extend([
            Paragraph("Overall remarks", styles["Section"]),
            Paragraph(escape(inspection.remarks or "No overall remarks recorded."), styles["Normal"]),
            Spacer(1, 18),
            Paragraph("This report was generated from the Railway Dashboard PostgreSQL record. The SHA-256 fingerprint returned in the response headers can be used to verify the file has not changed.", styles["SmallMuted"]),
        ])
        document.build(story)
        content = buffer.getvalue()
        fingerprint = hashlib.sha256(content).hexdigest()
        signing_secret = os.getenv("REPORT_SIGNING_SECRET", "rail-dashboard-development-report-key").encode("utf-8")
        signature = hmac.new(signing_secret, content, hashlib.sha256).hexdigest()
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="inspection-{inspection_id}.pdf"',
                "X-Report-SHA256": fingerprint,
                "X-Report-Signature": f"sha256={signature}",
                "X-Report-Signed": "true",
                "X-Report-Status": inspection.status or "draft",
            },
        )
    finally:
        session.close()


@router.post("/inspections/{inspection_id}/report/verify")
async def verify_inspection_report(
    inspection_id: str,
    file: UploadFile = File(...),
    report_signature: str | None = Header(default=None, alias="X-Report-Signature"),
):
    """Verify a downloaded report's SHA-256 and HMAC signature."""
    session = SessionLocal()
    try:
        if not session.get(Inspection, inspection_id):
            raise HTTPException(status_code=404, detail="Inspection not found")
    finally:
        session.close()
    content = await file.read()
    fingerprint = hashlib.sha256(content).hexdigest()
    signing_secret = os.getenv("REPORT_SIGNING_SECRET", "rail-dashboard-development-report-key").encode("utf-8")
    expected = f"sha256={hmac.new(signing_secret, content, hashlib.sha256).hexdigest()}"
    valid = bool(report_signature) and hmac.compare_digest(report_signature.strip(), expected)
    return envelope(
        {
            "valid": valid,
            "sha256": fingerprint,
            "signature": expected,
            "file_name": file.filename,
        },
        "Report signature verified" if valid else "Report signature invalid",
    )


@router.get("/evidence/{evidence_id}/content")
def evidence_content(evidence_id: str):
    session = SessionLocal()
    try:
        evidence = session.get(InspectionEvidence, evidence_id)
        if not evidence:
            raise HTTPException(status_code=404, detail="Evidence not found")
        return Response(
            content=evidence.content,
            media_type=evidence.mime_type,
            headers={"Cache-Control": "private, max-age=86400"},
        )
    finally:
        session.close()


@router.post("/inspections", status_code=201)
def create_inspection(payload: InspectionCreate):
    session = SessionLocal()
    try:
        with session.begin():
            result = upsert_inspection(session, payload.model_dump())
        return envelope(result, "inspection saved")
    finally:
        session.close()


@router.patch("/inspections/{inspection_id}/status")
def update_inspection_status(inspection_id: str, payload: InspectionStatusUpdate):
    session = SessionLocal()
    try:
        with session.begin():
            result = transition_inspection_status(
                session,
                inspection_id,
                payload.model_dump(exclude_none=True),
            )
        return envelope(result, "inspection status updated")
    finally:
        session.close()


@router.patch("/findings/{finding_id}/status")
def update_finding_status(finding_id: str, payload: FindingStatusUpdate):
    session = SessionLocal()
    try:
        with session.begin():
            result = transition_finding_status(
                session,
                finding_id,
                payload.model_dump(exclude_none=True),
            )
        return envelope(result, "finding status updated")
    finally:
        session.close()


@router.post("/sync/push")
def sync_push(payload: SyncPushRequest):
    session = SessionLocal()
    try:
        results = []
        for operation in payload.operations:
            try:
                with session.begin():
                    results.append(
                        process_operation(session, payload.device_id, operation)
                    )
            except HTTPException as exc:
                session.rollback()
                detail = exc.detail
                message = (
                    detail
                    if isinstance(detail, str)
                    else detail.get("message", "Record validation failed")
                    if isinstance(detail, dict)
                    else "Record validation failed"
                )
                results.append(
                    {
                        "operation_id": operation.operation_id,
                        "entity_type": operation.entity_type,
                        "entity_id": operation.entity_id,
                        "status": "rejected",
                        "message": message,
                        "conflict": _conflict_payload(session, operation.entity_type, operation.entity_id)
                        if exc.status_code == 409 else None,
                    }
                )
            except ValidationError as exc:
                session.rollback()
                results.append(
                    {
                        "operation_id": operation.operation_id,
                        "entity_type": operation.entity_type,
                        "entity_id": operation.entity_id,
                        "status": "rejected",
                        "message": "Invalid synchronized record",
                        "errors": exc.errors(),
                    }
                )
            except Exception:
                session.rollback()
                logger.exception(
                    "Mobile sync operation failed",
                    extra={"operation_id": operation.operation_id},
                )
                results.append(
                    {
                        "operation_id": operation.operation_id,
                        "entity_type": operation.entity_type,
                        "entity_id": operation.entity_id,
                        "status": "rejected",
                        "message": "The server could not save this record",
                    }
                )
        cursor = (
            session.query(MobileChange.sequence)
            .order_by(MobileChange.sequence.desc())
            .limit(1)
            .scalar()
            or 0
        )
        processed = sum(1 for row in results if row["status"] == "processed")
        rejected = len(results) - processed
        return envelope(
            {
                "results": results,
                "cursor": cursor,
                "processed": processed,
                "rejected": rejected,
            },
            "sync completed" if rejected == 0 else "sync completed with errors",
        )
    finally:
        session.close()


@router.get("/sync/pull")
def sync_pull(cursor: int = Query(default=0, ge=0), limit: int = Query(default=500, ge=1, le=2000)):
    session = SessionLocal()
    try:
        rows = (
            session.query(MobileChange)
            .filter(MobileChange.sequence > cursor)
            .order_by(MobileChange.sequence)
            .limit(limit)
            .all()
        )
        changes = [
            {
                "sequence": row.sequence,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "action": row.action,
                "payload": json.loads(row.payload_json),
                "changed_at": row.changed_at.isoformat(),
            }
            for row in rows
        ]
        next_cursor = changes[-1]["sequence"] if changes else cursor
        return envelope({"changes": changes, "cursor": next_cursor, "has_more": len(rows) == limit}, "ok")
    finally:
        session.close()
