from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


EntityType = Literal["inspection", "response", "finding", "evidence", "note"]
SyncAction = Literal["upsert", "delete"]
InspectionStatus = Literal[
    "draft",
    "in_progress",
    "submitted",
    "assigned",
    "action_taken",
    "verification",
    "closed",
    "returned",
]
FindingStatus = Literal[
    "open",
    "assigned",
    "action_taken",
    "verification_due",
    "returned",
    "verified",
    "closed",
]


class InspectionCreate(BaseModel):
    inspection_id: str = Field(min_length=36, max_length=36)
    station_code: str = Field(min_length=1, max_length=64)
    template_id: str = Field(min_length=36, max_length=36)
    inspector_name: str = Field(min_length=1, max_length=255)
    inspection_type: Literal["scheduled", "surprise", "follow_up"] = "scheduled"
    status: InspectionStatus = "draft"
    score: int | None = Field(default=None, ge=0, le=100)
    remarks: str | None = Field(default=None, max_length=5000)
    device_id: str | None = Field(default=None, max_length=128)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    client_updated_at: datetime | None = None
    server_version: int = Field(default=0, ge=0)

    @field_validator("station_code")
    @classmethod
    def normalize_station_code(cls, value: str) -> str:
        return value.strip().upper()


class InspectionResponseUpsert(BaseModel):
    response_id: str = Field(min_length=36, max_length=36)
    inspection_id: str = Field(min_length=36, max_length=36)
    section_code: str = Field(min_length=1, max_length=64)
    question_code: str = Field(min_length=1, max_length=128)
    response_value: str | None = Field(default=None, max_length=64)
    remarks: str | None = Field(default=None, max_length=5000)
    severity: Literal["low", "medium", "high", "critical"] | None = None
    asset_ref: str | None = Field(default=None, max_length=128)
    platform: str | None = Field(default=None, max_length=64)
    evidence_count: int = Field(default=0, ge=0, le=100)
    response_json: dict[str, Any] | list[Any] | None = None
    client_updated_at: datetime | None = None
    server_version: int = Field(default=0, ge=0)


class FindingUpsert(BaseModel):
    finding_id: str = Field(min_length=36, max_length=36)
    inspection_id: str = Field(min_length=36, max_length=36)
    response_id: str | None = Field(default=None, min_length=36, max_length=36)
    station_code: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    status: Literal[
        "open",
        "assigned",
        "action_taken",
        "verification_due",
        "returned",
        "verified",
        "closed",
    ] = "open"
    responsible_party: str | None = Field(default=None, max_length=255)
    target_date: str | None = Field(default=None, max_length=32)
    financial_implication: int | None = Field(default=None, ge=0)
    repeat_observation: bool = False
    client_updated_at: datetime | None = None
    server_version: int = Field(default=0, ge=0)

    @field_validator("station_code")
    @classmethod
    def normalize_station_code(cls, value: str) -> str:
        return value.strip().upper()


class InspectionStatusUpdate(BaseModel):
    status: InspectionStatus
    remarks: str | None = Field(default=None, max_length=5000)
    client_updated_at: datetime | None = None
    server_version: int = Field(default=0, ge=0)


class FindingStatusUpdate(BaseModel):
    status: FindingStatus
    responsible_party: str | None = Field(default=None, max_length=255)
    target_date: str | None = Field(default=None, max_length=32)
    client_updated_at: datetime | None = None
    server_version: int = Field(default=0, ge=0)


class EvidenceUpsert(BaseModel):
    evidence_id: str = Field(min_length=36, max_length=36)
    inspection_id: str = Field(min_length=36, max_length=36)
    response_id: str | None = Field(default=None, min_length=36, max_length=36)
    question_code: str | None = Field(default=None, max_length=128)
    mime_type: Literal["image/jpeg", "image/png"]
    content_base64: str = Field(min_length=4, max_length=8_000_000)
    caption: str | None = Field(default=None, max_length=1000)
    context: str | None = Field(default=None, max_length=1000)
    created_at: datetime | None = None
    client_updated_at: datetime | None = None
    server_version: int = Field(default=0, ge=0)


class InspectionNoteUpsert(BaseModel):
    note_id: str = Field(min_length=36, max_length=36)
    inspection_id: str = Field(min_length=36, max_length=36)
    section_code: str | None = Field(default=None, max_length=64)
    question_code: str | None = Field(default=None, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=10000)
    context: str | None = Field(default=None, max_length=1000)
    created_at: datetime | None = None
    client_updated_at: datetime | None = None
    server_version: int = Field(default=0, ge=0)


class SyncOperation(BaseModel):
    operation_id: str = Field(min_length=36, max_length=36)
    entity_type: EntityType
    entity_id: str = Field(min_length=36, max_length=36)
    action: SyncAction = "upsert"
    payload: dict[str, Any]


class SyncPushRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    operations: list[SyncOperation] = Field(max_length=500)


class MobileDeviceStateUpdate(BaseModel):
    cached_stations: int = Field(default=0, ge=0)
    cached_station_details: int = Field(default=0, ge=0)
    cached_works: int = Field(default=0, ge=0)
    cached_units: int = Field(default=0, ge=0)
    cached_earnings: int = Field(default=0, ge=0)
    pending_operations: int = Field(default=0, ge=0)
    failed_operations: int = Field(default=0, ge=0)
    data_version: str | None = Field(default=None, max_length=128)
    cache_updated_at: datetime | None = None
    last_sync_at: datetime | None = None


class AmenityFindingRequest(BaseModel):
    inspection_id: str = Field(min_length=36, max_length=36)
    norm_keys: list[int] | None = Field(default=None, max_length=200)
    responsible_party: str | None = Field(default=None, max_length=255)
    target_date: str | None = Field(default=None, max_length=32)
