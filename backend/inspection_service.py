from __future__ import annotations

import base64
import binascii
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from inspection_schemas import (
    EvidenceUpsert,
    FindingStatusUpdate,
    FindingUpsert,
    InspectionCreate,
    InspectionStatusUpdate,
    InspectionNoteUpsert,
    InspectionResponseUpsert,
    SyncOperation,
)
from models import (
    Inspection,
    InspectionEvidence,
    InspectionFinding,
    InspectionNote,
    InspectionResponse,
    InspectionTemplate,
    MobileChange,
    MobileSyncOperation,
    Station,
)
from services import row_to_dict


DEFAULT_TEMPLATE_ID = "10000000-0000-4000-8000-000000000002"

DEFAULT_TEMPLATE = {
    "template_id": DEFAULT_TEMPLATE_ID,
    "template_code": "GENERAL_STATION",
    "name": "General Station Commercial Inspection",
    "domain": "general",
    "version": 2,
    "sections": [
        {
            "code": "passenger_amenities",
            "title": "Passenger amenities",
            "questions": [
                {"code": "approach_road", "text": "Approach road and circulating area are serviceable", "required": True},
                {"code": "entry_exit", "text": "Entry and exit routes are clear and properly marked", "required": True},
                {"code": "fob", "text": "FOB, subway and platform connectivity are serviceable", "required": True},
                {"code": "lift_ramp", "text": "Lifts, escalators and ramps are operational", "required": True},
                {"code": "display_boards", "text": "Coach and train indication boards are functional", "required": True},
            ],
        },
        {
            "code": "cleanliness",
            "title": "Cleanliness",
            "questions": [
                {"code": "platform_cleanliness", "text": "Platforms and track area are clean", "required": True},
                {"code": "toilet_cleanliness", "text": "Toilets are clean, supplied and operational", "required": True},
                {"code": "waste_management", "text": "Waste segregation and disposal records are maintained", "required": True},
            ],
        },
        {
            "code": "divyangjan",
            "title": "Divyangjan compliance",
            "questions": [
                {"code": "accessible_route", "text": "A continuous accessible route is available", "required": True},
                {"code": "accessible_counter", "text": "Accessible ticket counter and toilet are available", "required": True},
                {"code": "tactile_signage", "text": "Tactile path and accessible signage are compliant", "required": True},
            ],
        },
        {
            "code": "commercial_records",
            "title": "Commercial records and returns",
            "questions": [
                {"code": "ropd", "text": "Return of Previous Day is complete and reconciled", "required": True},
                {"code": "registers", "text": "Prescribed records and registers are updated", "required": True},
                {"code": "ticketing_equipment", "text": "Ticketing equipment is operational and secured", "required": True},
            ],
        },
        {
            "code": "booking_reservation",
            "title": "Booking and reservation",
            "questions": [
                {"code": "ticket_stock", "text": "Ticket stock, rolls and stationery are accounted for", "required": True},
                {"code": "cash_remittance", "text": "Cash, shift handover and remittance are reconciled", "required": True},
                {"code": "refund_cancellation", "text": "Refund and cancellation transactions are supported by records", "required": True},
                {"code": "uts_prs", "text": "UTS, PRS, EFT and POS equipment are operational and secured", "required": True},
            ],
        },
        {
            "code": "parcel_goods",
            "title": "Parcel and goods",
            "questions": [
                {"code": "parcel_registers", "text": "Parcel inward, outward and delivery registers are updated", "required": True},
                {"code": "undelivered", "text": "Undelivered consignments have current disposal action", "required": True},
                {"code": "demurrage_wharfage", "text": "Demurrage and wharfage are assessed and recovered", "required": True},
                {"code": "goods_records", "text": "Goods office returns, loading and weighing records are reconciled", "required": True},
            ],
        },
        {
            "code": "signage_information",
            "title": "Signage and passenger information",
            "questions": [
                {"code": "signage_boards", "text": "Mandatory directional and passenger signage is available and legible", "required": True},
                {"code": "coach_indication", "text": "Coach indication boards are functional and accurate", "required": True},
                {"code": "train_indication", "text": "Train indication boards and enquiry systems are functional", "required": True},
                {"code": "public_address", "text": "Public-address announcements are clear across passenger areas", "required": True},
            ],
        },
        {
            "code": "outstanding",
            "title": "Outstanding and recoveries",
            "questions": [
                {"code": "admitted_debits", "text": "Admitted debits have current recovery action", "required": True},
                {"code": "disputed_debits", "text": "Disputed debits have documented action", "required": True},
                {"code": "saleable_items", "text": "Saleable items are accounted for and reconciled", "required": True},
            ],
        },
    ],
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def seed_default_template(session: Session) -> None:
    if session.get(InspectionTemplate, DEFAULT_TEMPLATE_ID):
        return
    (
        session.query(InspectionTemplate)
        .filter(
            InspectionTemplate.template_code == DEFAULT_TEMPLATE["template_code"],
            InspectionTemplate.is_active.is_(True),
        )
        .update({"is_active": False}, synchronize_session=False)
    )
    session.add(
        InspectionTemplate(
            template_id=DEFAULT_TEMPLATE_ID,
            template_code=DEFAULT_TEMPLATE["template_code"],
            name=DEFAULT_TEMPLATE["name"],
            domain=DEFAULT_TEMPLATE["domain"],
            version=DEFAULT_TEMPLATE["version"],
            definition_json=json.dumps(DEFAULT_TEMPLATE, separators=(",", ":")),
            source_hash=hashlib.sha256(
                json.dumps(DEFAULT_TEMPLATE, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        )
    )


def template_to_dict(template: InspectionTemplate) -> dict[str, Any]:
    data = row_to_dict(template)
    data["definition"] = json.loads(template.definition_json)
    data.pop("definition_json", None)
    return data


def _json_value(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, separators=(",", ":"), default=str)


def _check_client_version(record: Any, client_version: int) -> None:
    if client_version < record.server_version:
        raise HTTPException(
            status_code=409,
            detail=(
                "This record changed on another device. Refresh data, review "
                "the latest version, and apply your update again."
            ),
        )


def _record_change(
    session: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    payload: dict[str, Any],
) -> MobileChange:
    change = MobileChange(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        payload_json=json.dumps(payload, separators=(",", ":"), default=str),
    )
    session.add(change)
    session.flush()
    return change


def upsert_inspection(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    data = InspectionCreate.model_validate(payload)
    if not session.get(Station, data.station_code):
        raise HTTPException(status_code=422, detail=f"Unknown station code: {data.station_code}")
    if not session.get(InspectionTemplate, data.template_id):
        raise HTTPException(status_code=422, detail="Unknown inspection template")

    record = session.get(Inspection, data.inspection_id)
    values = data.model_dump(exclude_none=True, exclude={"server_version"})
    if record:
        _check_client_version(record, data.server_version)
        for key, value in values.items():
            if key != "inspection_id":
                setattr(record, key, value)
        record.server_version += 1
        record.updated_at = utcnow()
    else:
        values.setdefault("started_at", utcnow())
        record = Inspection(**values)
        session.add(record)
    session.flush()
    result = row_to_dict(record)
    _record_change(session, "inspection", record.inspection_id, "upsert", result)
    return result


def upsert_response(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    data = InspectionResponseUpsert.model_validate(payload)
    if not session.get(Inspection, data.inspection_id):
        raise HTTPException(status_code=422, detail="Inspection must be synced before its responses")
    record = session.get(InspectionResponse, data.response_id)
    values = data.model_dump(exclude_none=True, exclude={"server_version"})
    if "response_json" in values:
        values["response_json"] = _json_value(values["response_json"])
    if record:
        _check_client_version(record, data.server_version)
        for key, value in values.items():
            if key != "response_id":
                setattr(record, key, value)
        record.server_version += 1
        record.updated_at = utcnow()
    else:
        record = InspectionResponse(**values)
        session.add(record)
    session.flush()
    result = row_to_dict(record)
    if record.response_json:
        result["response_json"] = json.loads(record.response_json)
    _record_change(session, "response", record.response_id, "upsert", result)
    return result


def upsert_finding(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    data = FindingUpsert.model_validate(payload)
    inspection = session.get(Inspection, data.inspection_id)
    if not inspection:
        raise HTTPException(status_code=422, detail="Inspection must be synced before its findings")
    if inspection.station_code != data.station_code:
        raise HTTPException(status_code=422, detail="Finding station must match inspection station")
    record = session.get(InspectionFinding, data.finding_id)
    values = data.model_dump(exclude_none=True, exclude={"server_version"})
    if record:
        _check_client_version(record, data.server_version)
        for key, value in values.items():
            if key != "finding_id":
                setattr(record, key, value)
        record.server_version += 1
        record.updated_at = utcnow()
    else:
        record = InspectionFinding(**values)
        session.add(record)
    session.flush()
    result = row_to_dict(record)
    _record_change(session, "finding", record.finding_id, "upsert", result)
    return result


def _serious_findings_without_evidence(session: Session, inspection_id: str) -> list[str]:
    findings = (
        session.query(InspectionFinding)
        .filter(
            InspectionFinding.inspection_id == inspection_id,
            InspectionFinding.severity.in_(["high", "critical"]),
        )
        .all()
    )
    missing = []
    for finding in findings:
        evidence_query = session.query(InspectionEvidence).filter(
            InspectionEvidence.inspection_id == inspection_id,
        )
        if finding.response_id:
            evidence_query = evidence_query.filter(
                InspectionEvidence.response_id == finding.response_id,
            )
        if evidence_query.count() == 0:
            missing.append(finding.finding_id)
    return missing


def _finding_has_evidence(session: Session, finding: InspectionFinding) -> bool:
    evidence_query = session.query(InspectionEvidence).filter(
        InspectionEvidence.inspection_id == finding.inspection_id,
    )
    if finding.response_id:
        evidence_query = evidence_query.filter(
            InspectionEvidence.response_id == finding.response_id,
        )
    return evidence_query.count() > 0


INSPECTION_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"draft", "in_progress", "submitted"},
    "in_progress": {"in_progress", "submitted"},
    "submitted": {"submitted", "assigned", "returned"},
    "assigned": {"assigned", "action_taken", "returned"},
    "action_taken": {"action_taken", "verification", "returned"},
    "verification": {"verification", "closed", "returned"},
    "returned": {"returned", "submitted"},
    "closed": {"closed"},
    # Kept for records created by the earlier mobile schema.
    "reviewed": {"reviewed", "verification", "closed", "returned"},
}


FINDING_TRANSITIONS: dict[str, set[str]] = {
    "open": {"open", "assigned", "returned"},
    "assigned": {"assigned", "action_taken", "returned"},
    "action_taken": {"action_taken", "verification_due", "returned"},
    "verification_due": {"verification_due", "verified", "returned"},
    "verified": {"verified", "closed"},
    "returned": {"returned", "assigned"},
    "closed": {"closed"},
}


def transition_inspection_status(
    session: Session,
    inspection_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    data = InspectionStatusUpdate.model_validate(payload)
    record = session.get(Inspection, inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inspection not found")
    _check_client_version(record, data.server_version)
    current = record.status or "draft"
    if data.status not in INSPECTION_TRANSITIONS.get(current, {current}):
        raise HTTPException(
            status_code=409,
            detail=f"Inspection cannot move from {current} to {data.status}",
        )
    if data.status in {"submitted", "verification", "closed"}:
        missing = _serious_findings_without_evidence(session, inspection_id)
        if missing:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Serious findings require photo evidence before this workflow step",
                    "finding_ids": missing,
                },
            )
    if data.status == "closed":
        open_findings = (
            session.query(InspectionFinding)
            .filter(
                InspectionFinding.inspection_id == inspection_id,
                InspectionFinding.status.notin_(["verified", "closed"]),
            )
            .count()
        )
        if open_findings:
            raise HTTPException(
                status_code=422,
                detail=f"{open_findings} finding(s) must be verified or closed before inspection closure",
            )
        record.completed_at = utcnow()
    record.status = data.status
    if data.remarks is not None:
        record.remarks = data.remarks
    record.server_version += 1
    record.updated_at = utcnow()
    session.flush()
    result = row_to_dict(record)
    _record_change(session, "inspection", record.inspection_id, "status_transition", result)
    return result


def transition_finding_status(
    session: Session,
    finding_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    data = FindingStatusUpdate.model_validate(payload)
    record = session.get(InspectionFinding, finding_id)
    if not record:
        raise HTTPException(status_code=404, detail="Finding not found")
    _check_client_version(record, data.server_version)
    current = record.status or "open"
    if data.status not in FINDING_TRANSITIONS.get(current, {current}):
        raise HTTPException(
            status_code=409,
            detail=f"Finding cannot move from {current} to {data.status}",
        )
    if data.status in {"verification_due", "verified", "closed"}:
        if record.severity in {"high", "critical"} and not _finding_has_evidence(session, record):
            raise HTTPException(
                status_code=422,
                detail="High and critical findings require photo evidence before verification",
            )
    record.status = data.status
    if data.responsible_party is not None:
        record.responsible_party = data.responsible_party
    if data.target_date is not None:
        record.target_date = data.target_date
    record.server_version += 1
    record.updated_at = utcnow()
    session.flush()
    result = row_to_dict(record)
    _record_change(session, "finding", record.finding_id, "status_transition", result)
    return result


def upsert_evidence(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    data = EvidenceUpsert.model_validate(payload)
    if not session.get(Inspection, data.inspection_id):
        raise HTTPException(status_code=422, detail="Inspection must be synced before its evidence")
    if data.response_id:
        response = session.get(InspectionResponse, data.response_id)
        if not response or response.inspection_id != data.inspection_id:
            raise HTTPException(status_code=422, detail="Evidence response does not belong to inspection")
    try:
        content = base64.b64decode(data.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Photo content is not valid base64") from exc
    if not content or len(content) > 6_000_000:
        raise HTTPException(status_code=422, detail="Photo must be between 1 byte and 6 MB")

    record = session.get(InspectionEvidence, data.evidence_id)
    values = data.model_dump(
        exclude={"content_base64", "server_version"}, exclude_none=True
    )
    values["content"] = content
    if record:
        _check_client_version(record, data.server_version)
        for key, value in values.items():
            if key != "evidence_id":
                setattr(record, key, value)
        record.server_version += 1
        record.updated_at = utcnow()
    else:
        record = InspectionEvidence(**values)
        session.add(record)
    session.flush()
    result = {
        "evidence_id": record.evidence_id,
        "inspection_id": record.inspection_id,
        "response_id": record.response_id,
        "question_code": record.question_code,
        "mime_type": record.mime_type,
        "caption": record.caption,
        "context": record.context,
        "created_at": record.created_at,
        "client_updated_at": record.client_updated_at,
        "server_version": record.server_version,
    }
    _record_change(session, "evidence", record.evidence_id, "upsert", result)
    return result


def upsert_note(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    data = InspectionNoteUpsert.model_validate(payload)
    if not session.get(Inspection, data.inspection_id):
        raise HTTPException(status_code=422, detail="Inspection must be synced before its notes")
    record = session.get(InspectionNote, data.note_id)
    values = data.model_dump(exclude_none=True, exclude={"server_version"})
    if record:
        _check_client_version(record, data.server_version)
        for key, value in values.items():
            if key != "note_id":
                setattr(record, key, value)
        record.server_version += 1
        record.updated_at = utcnow()
    else:
        record = InspectionNote(**values)
        session.add(record)
    session.flush()
    result = row_to_dict(record)
    _record_change(session, "note", record.note_id, "upsert", result)
    return result


def delete_entity(session: Session, entity_type: str, entity_id: str) -> dict[str, Any]:
    models = {
        "inspection": Inspection,
        "response": InspectionResponse,
        "finding": InspectionFinding,
        "evidence": InspectionEvidence,
        "note": InspectionNote,
    }
    model = models[entity_type]
    record = session.get(model, entity_id)
    if record:
        session.delete(record)
    payload = {"id": entity_id}
    _record_change(session, entity_type, entity_id, "delete", payload)
    return payload


def process_operation(
    session: Session,
    device_id: str,
    operation: SyncOperation,
) -> dict[str, Any]:
    existing = session.get(MobileSyncOperation, operation.operation_id)
    if existing:
        return json.loads(existing.result_json or "{}")

    payload_hash = hashlib.sha256(
        json.dumps(operation.payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    if operation.action == "delete":
        result = delete_entity(session, operation.entity_type, operation.entity_id)
    elif operation.entity_type == "inspection":
        result = upsert_inspection(session, operation.payload)
    elif operation.entity_type == "response":
        result = upsert_response(session, operation.payload)
    elif operation.entity_type == "finding":
        result = upsert_finding(session, operation.payload)
    elif operation.entity_type == "evidence":
        result = upsert_evidence(session, operation.payload)
    else:
        result = upsert_note(session, operation.payload)

    response = {
        "operation_id": operation.operation_id,
        "entity_type": operation.entity_type,
        "entity_id": operation.entity_id,
        "status": "processed",
        "record": result,
    }
    session.add(
        MobileSyncOperation(
            operation_id=operation.operation_id,
            device_id=device_id,
            entity_type=operation.entity_type,
            entity_id=operation.entity_id,
            action=operation.action,
            payload_hash=payload_hash,
            status="processed",
            result_json=json.dumps(response, separators=(",", ":"), default=str),
        )
    )
    return response
