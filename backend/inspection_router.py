from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import ValidationError
from sqlalchemy import func

from api_utils import envelope
from database import SessionLocal
from inspection_schemas import InspectionCreate, SyncPushRequest
from inspection_service import (
    process_operation,
    seed_default_template,
    template_to_dict,
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
    Station,
)
from services import get_station_detail, row_to_dict


router = APIRouter(prefix="/api/mobile/v1", tags=["Mobile inspections"])
logger = logging.getLogger(__name__)


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
        cursor = session.query(MobileChange.sequence).order_by(MobileChange.sequence.desc()).limit(1).scalar() or 0
        return envelope(
            {
                "stations": [row_to_dict(row) for row in stations],
                "templates": [template_to_dict(row) for row in templates],
                "cursor": cursor,
            },
            "bootstrap ready",
        )
    finally:
        session.close()


@router.get("/offline/station-details")
def offline_station_details(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=25),
):
    session = SessionLocal()
    try:
        base_query = session.query(Station.station_code).filter(
            Station.is_active.is_(True),
            func.lower(func.trim(Station.categorisation)).notin_(("", "test", "non-commercial")),
        )
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
