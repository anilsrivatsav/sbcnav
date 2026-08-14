from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditMixin:
    source_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Station(Base, AuditMixin):
    __tablename__ = "stations"

    station_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    station_name: Mapped[str | None] = mapped_column(Text, index=True)
    division: Mapped[str | None] = mapped_column(Text, index=True)
    zone: Mapped[str | None] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(Text, index=True)
    cmi: Mapped[str | None] = mapped_column(Text)
    den: Mapped[str | None] = mapped_column(Text)
    sr_den: Mapped[str | None] = mapped_column(Text)
    categorisation: Mapped[str | None] = mapped_column(Text, index=True)
    earnings_range: Mapped[str | None] = mapped_column(Text)
    passenger_range: Mapped[str | None] = mapped_column(Text)
    passenger_footfall: Mapped[int | None] = mapped_column(Integer, index=True)
    platforms: Mapped[str | None] = mapped_column(Text)
    number_of_platforms: Mapped[int | None] = mapped_column(Integer)
    platform_type: Mapped[str | None] = mapped_column(Text)
    parking: Mapped[str | None] = mapped_column(Text)
    pay_and_use: Mapped[str | None] = mapped_column(Text)
    trains_dealt: Mapped[int | None] = mapped_column(Integer)
    tickets_per_day: Mapped[int | None] = mapped_column(Integer)
    passengers_per_day: Mapped[int | None] = mapped_column(Integer)
    earnings_per_day: Mapped[int | None] = mapped_column(Integer)
    footfalls_per_day: Mapped[int | None] = mapped_column(Integer)
    abss_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    redevelopment_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)


class Unit(Base, AuditMixin):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("station_code", "unit_no", name="uq_units_station_unit"),
    )

    unit_no: Mapped[str] = mapped_column(String(64), primary_key=True)
    sl_no: Mapped[int | None] = mapped_column(Integer)
    type_of_unit: Mapped[str | None] = mapped_column(Text, index=True)
    station_code: Mapped[str | None] = mapped_column(String(64), ForeignKey("stations.station_code", ondelete="SET NULL"), index=True)
    station_category: Mapped[str | None] = mapped_column(Text, index=True)
    old_category: Mapped[str | None] = mapped_column(Text)
    pf_no: Mapped[str | None] = mapped_column(Text)
    pegged_location: Mapped[str | None] = mapped_column(Text)
    reservation_category: Mapped[str | None] = mapped_column(Text)
    allotment_type: Mapped[str | None] = mapped_column(Text)
    licensee_name: Mapped[str | None] = mapped_column(Text, index=True)
    license_fee: Mapped[str | None] = mapped_column(Text)
    contract_from: Mapped[str | None] = mapped_column(Text)
    contract_to: Mapped[str | None] = mapped_column(Text)
    paid_upto: Mapped[str | None] = mapped_column(Text, index=True)
    unit_status: Mapped[str | None] = mapped_column(Text, index=True)
    remarks: Mapped[str | None] = mapped_column(Text)
    source_row: Mapped[int | None] = mapped_column(Integer)


class Work(Base, AuditMixin):
    __tablename__ = "works"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_works_project_id"),
        UniqueConstraint("project_id", "section", name="uq_works_project_section"),
    )

    work_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(128), index=True)
    source_sn: Mapped[int | None] = mapped_column(Integer, index=True)
    source_project_id: Mapped[str | None] = mapped_column(Text, index=True)
    year_of_sanction: Mapped[str | None] = mapped_column(Text)
    year_ub_works: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text, index=True)
    date_of_sanction: Mapped[str | None] = mapped_column(Text)
    short_name_of_work: Mapped[str | None] = mapped_column(Text, index=True)
    block_section_station: Mapped[str | None] = mapped_column(Text)
    allocation: Mapped[str | None] = mapped_column(Text)
    cost: Mapped[int | None] = mapped_column(Integer)
    expenditure_upto_date: Mapped[int | None] = mapped_column(Integer)
    physical_progress: Mapped[str | None] = mapped_column(Text)
    financial_progress: Mapped[str | None] = mapped_column(Text)
    engg_remarks: Mapped[str | None] = mapped_column(Text)
    if_ub: Mapped[str | None] = mapped_column(Text)
    parent_work: Mapped[str | None] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(Text, index=True)
    anticipated_expenditure: Mapped[int | None] = mapped_column(Integer)
    remarks: Mapped[str | None] = mapped_column(Text)


class WorkLink(Base):
    __tablename__ = "work_links"
    __table_args__ = (
        UniqueConstraint("project_id", "scope_type", "scope_value", "station_code", name="uq_work_links_scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(128), ForeignKey("works.project_id", ondelete="CASCADE"), index=True)
    scope_type: Mapped[str | None] = mapped_column(Text, index=True)
    scope_value: Mapped[str | None] = mapped_column(Text)
    station_code: Mapped[str | None] = mapped_column(String(64), ForeignKey("stations.station_code", ondelete="SET NULL"), index=True)
    match_status: Mapped[str | None] = mapped_column(Text, index=True)


class AmenityNorm(Base, AuditMixin):
    __tablename__ = "amenity_norms"
    __table_args__ = (
        UniqueConstraint("category", "amenity", "norm", name="uq_amenity_norms_category_amenity_norm"),
    )

    norm_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    amenity: Mapped[str | None] = mapped_column(Text, index=True)
    norm: Mapped[str] = mapped_column(Text, index=True)
    norm_quantity: Mapped[str | None] = mapped_column(Text)


class StationInfra(Base, AuditMixin):
    __tablename__ = "station_infra"
    __table_args__ = (
        UniqueConstraint("station_code", name="uq_station_infra_station_code"),
    )

    infra_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_code: Mapped[str] = mapped_column(String(64), index=True)
    station_name: Mapped[str | None] = mapped_column(Text, index=True)
    category: Mapped[str | None] = mapped_column(Text, index=True)
    platform_list: Mapped[str | None] = mapped_column(Text)
    platform_count: Mapped[int | None] = mapped_column(Integer, index=True)
    platform_level: Mapped[str | None] = mapped_column(Text, index=True)
    fob_details: Mapped[str | None] = mapped_column(Text)
    shelter_details: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)


class PlatformDetail(Base, AuditMixin):
    __tablename__ = "platform_details"
    __table_args__ = (
        UniqueConstraint("station_code", "platform", name="uq_platform_details_station_platform"),
    )

    platform_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_code: Mapped[str] = mapped_column(String(64), index=True)
    platform: Mapped[str] = mapped_column(String(64), index=True)
    length_m: Mapped[int | None] = mapped_column(Integer, index=True)
    lifts: Mapped[str | None] = mapped_column(Text)
    escalators: Mapped[str | None] = mapped_column(Text)
    ramp: Mapped[str | None] = mapped_column(Text)


class WheelChairAvailability(Base, AuditMixin):
    __tablename__ = "wheel_chair_availability"
    __table_args__ = (
        UniqueConstraint("station_code", name="uq_wheel_chair_station_code"),
    )

    wheel_chair_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_code: Mapped[str] = mapped_column(String(64), index=True)
    station_name: Mapped[str | None] = mapped_column(Text, index=True)
    section: Mapped[str | None] = mapped_column(Text, index=True)
    category: Mapped[str | None] = mapped_column(Text, index=True)
    available_good_condition: Mapped[int | None] = mapped_column(Integer, index=True)


class TrolleyPath(Base, AuditMixin):
    __tablename__ = "trolley_paths"
    __table_args__ = (
        UniqueConstraint("station_code", name="uq_trolley_paths_station_code"),
    )

    trolley_path_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_code: Mapped[str] = mapped_column(String(64), index=True)
    station_name: Mapped[str | None] = mapped_column(Text, index=True)
    division: Mapped[str | None] = mapped_column(Text, index=True)
    zone: Mapped[str | None] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(Text, index=True)
    categorisation: Mapped[str | None] = mapped_column(Text, index=True)
    passenger_footfall: Mapped[int | None] = mapped_column(Integer, index=True)
    platforms: Mapped[str | None] = mapped_column(Text)
    number_of_platforms: Mapped[str | None] = mapped_column(Text)
    platform_type: Mapped[str | None] = mapped_column(Text, index=True)
    trolley_path: Mapped[str | None] = mapped_column(Text, index=True)
    trolley_path_sanction: Mapped[str | None] = mapped_column(Text)


class PassengerAmenityWork(Base, AuditMixin):
    __tablename__ = "passenger_amenity_works"
    __table_args__ = (
        UniqueConstraint("work_type", "station_code", "work_name", name="uq_pa_works_type_station_name"),
    )

    pa_work_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_type: Mapped[str] = mapped_column(String(64), index=True)
    station_code: Mapped[str | None] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(128), index=True)
    station_category: Mapped[str | None] = mapped_column(Text, index=True)
    platform_level: Mapped[str | None] = mapped_column(Text)
    work_name: Mapped[str] = mapped_column(Text, index=True)
    tender_status: Mapped[str | None] = mapped_column(Text, index=True)
    loa_date: Mapped[str | None] = mapped_column(Text)
    sanction_date: Mapped[str | None] = mapped_column(Text, index=True)
    executive_agency: Mapped[str | None] = mapped_column(Text, index=True)
    progress: Mapped[str | None] = mapped_column(Text)
    physical_progress: Mapped[str | None] = mapped_column(Text)
    tdc: Mapped[str | None] = mapped_column(Text, index=True)
    cost: Mapped[str | None] = mapped_column(Text)
    existing_platform_length: Mapped[str | None] = mapped_column(Text)


class PlatformExtensionSummary(Base, AuditMixin):
    __tablename__ = "platform_extension_summaries"
    __table_args__ = (
        UniqueConstraint("summary_type", "category", name="uq_pf_extension_summary_type_category"),
    )

    summary_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    summary_type: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    station_count: Mapped[int | None] = mapped_column(Integer, index=True)
    full_length_platforms: Mapped[int | None] = mapped_column(Integer)
    work_under_progress: Mapped[str | None] = mapped_column(Text)
    pf_extension_proposed: Mapped[str | None] = mapped_column(Text)
    raising_extension_proposed: Mapped[str | None] = mapped_column(Text)
    platform_extension_work_proposed: Mapped[str | None] = mapped_column(Text)
    existing_length: Mapped[str | None] = mapped_column(Text)
    required_length: Mapped[str | None] = mapped_column(Text)
    fob_ramps_stairs_available: Mapped[str | None] = mapped_column(Text)
    stations_without_fob: Mapped[str | None] = mapped_column(Text)
    stations_with_fob_ramp: Mapped[str | None] = mapped_column(Text)
    stations_fob_wip: Mapped[str | None] = mapped_column(Text)
    stations_with_lift: Mapped[str | None] = mapped_column(Text)
    stations_lift_proposed: Mapped[str | None] = mapped_column(Text)
    stations_ramp_proposed: Mapped[str | None] = mapped_column(Text)
    stations_not_feasible_lift_ramp: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)
    source_row: Mapped[int | None] = mapped_column(Integer)


class StationPlatformExtensionStatus(Base, AuditMixin):
    __tablename__ = "station_platform_extension_status"
    __table_args__ = (
        UniqueConstraint("station_code", name="uq_station_pf_extension_status_station_code"),
    )

    status_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_code: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str | None] = mapped_column(Text, index=True)
    source_category: Mapped[str | None] = mapped_column(Text, index=True)
    station_detail_category_code: Mapped[str | None] = mapped_column(Text, index=True)
    pf_extension_wip: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    pf_extension_proposed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    raising_extension_proposed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    platform_extension_work_proposed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    ramp_feasible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    fob_without: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    fob_ramp_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    fob_wip: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    lift_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    lift_proposed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    ramp_proposed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    not_feasible_lift_ramp: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    source_rows: Mapped[str | None] = mapped_column(Text)
    status_text: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)
    footfall_day: Mapped[int | None] = mapped_column(Integer, index=True)
    lift_details: Mapped[str | None] = mapped_column(Text)
    ramp_details: Mapped[str | None] = mapped_column(Text)
    escalator_details: Mapped[str | None] = mapped_column(Text)
    accessibility_source: Mapped[str | None] = mapped_column(Text)


class Earning(Base, AuditMixin):
    __tablename__ = "earnings"
    __table_args__ = (
        UniqueConstraint("receipt_key", name="uq_earnings_receipt_key"),
        UniqueConstraint("unit_no", "receipt_key", name="uq_earnings_unit_receipt"),
    )

    earning_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_key: Mapped[str] = mapped_column(String(128), index=True)
    sl_no: Mapped[int | None] = mapped_column(Integer)
    source_rows: Mapped[str | None] = mapped_column(Text)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    date_of_receipt: Mapped[str | None] = mapped_column(Text, index=True)
    unit_no: Mapped[str | None] = mapped_column(
    String(50),
    nullable=True,
    index=True,
)
    station_code: Mapped[str | None] = mapped_column(String(64), ForeignKey("stations.station_code", ondelete="SET NULL"), index=True)
    raw_unit_no: Mapped[str | None] = mapped_column(Text, index=True)
    raw_station_code: Mapped[str | None] = mapped_column(Text, index=True)
    earning_scope: Mapped[str | None] = mapped_column(String(32), index=True)
    pf_no: Mapped[str | None] = mapped_column(Text)
    licensee_name: Mapped[str | None] = mapped_column(Text, index=True)
    payment_head: Mapped[str | None] = mapped_column(Text, index=True)
    payment_sub_head: Mapped[str | None] = mapped_column(Text, index=True)
    period_from: Mapped[str | None] = mapped_column(Text)
    period_to: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[int | None] = mapped_column(Integer, index=True)
    gst: Mapped[int | None] = mapped_column(Integer)
    receipt_type: Mapped[str | None] = mapped_column(Text, index=True)
    mr_no: Mapped[str | None] = mapped_column(Text, index=True)
    mr_date: Mapped[str | None] = mapped_column(Text)
    ua_case: Mapped[str | None] = mapped_column(Text)


class EarningLink(Base):
    __tablename__ = "earning_links"
    __table_args__ = (
        UniqueConstraint("receipt_key", "unit_no", "station_code", name="uq_earning_links_receipt_unit_station"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_key: Mapped[str] = mapped_column(String(128), ForeignKey("earnings.receipt_key", ondelete="CASCADE"), index=True)
    unit_no: Mapped[str | None] = mapped_column(String(64), ForeignKey("units.unit_no", ondelete="SET NULL"), index=True)
    station_code: Mapped[str | None] = mapped_column(String(64), ForeignKey("stations.station_code", ondelete="SET NULL"), index=True)
    match_status: Mapped[str | None] = mapped_column(Text, index=True)


class CommercialContract(Base, AuditMixin):
    __tablename__ = "commercial_contracts"
    __table_args__ = (
        UniqueConstraint("contract_name", name="uq_commercial_contracts_contract_name"),
    )

    contract_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_sl_no: Mapped[int | None] = mapped_column(Integer, index=True)
    raw_station_value: Mapped[str | None] = mapped_column(Text, index=True)
    contract_name: Mapped[str] = mapped_column(String(255), index=True)
    licensee_name: Mapped[str | None] = mapped_column(Text, index=True)
    allocation_code: Mapped[str | None] = mapped_column(String(64), index=True)
    contract_allotted_on: Mapped[str | None] = mapped_column(Text, index=True)
    policy: Mapped[str | None] = mapped_column(Text, index=True)
    sub_category: Mapped[str | None] = mapped_column(Text, index=True)
    asset_scope: Mapped[str | None] = mapped_column(Text, index=True)
    space_sq_ft: Mapped[int | None] = mapped_column(Integer)
    annual_license_fee: Mapped[int | None] = mapped_column(Integer, index=True)
    quarterly_license_fee: Mapped[int | None] = mapped_column(Integer, index=True)
    no_of_years: Mapped[int | None] = mapped_column(Integer)
    contract_period_from: Mapped[str | None] = mapped_column(Text, index=True)
    contract_upto: Mapped[str | None] = mapped_column(Text, index=True)
    cycle: Mapped[str | None] = mapped_column(Text, index=True)
    year_ending_amount: Mapped[int | None] = mapped_column(Integer)
    total_license_fee_2026_2027: Mapped[int | None] = mapped_column(Integer)
    station_match_status: Mapped[str | None] = mapped_column(Text, index=True)
    remarks: Mapped[str | None] = mapped_column(Text)


class CommercialContractStationLink(Base):
    __tablename__ = "commercial_contract_station_links"
    __table_args__ = (
        UniqueConstraint("contract_key", "station_code", "raw_station_value", "match_type", name="uq_commercial_contract_station_link"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_key: Mapped[int] = mapped_column(Integer, ForeignKey("commercial_contracts.contract_key", ondelete="CASCADE"), index=True)
    station_code: Mapped[str | None] = mapped_column(String(64), ForeignKey("stations.station_code", ondelete="SET NULL"), index=True)
    raw_station_value: Mapped[str | None] = mapped_column(Text, index=True)
    match_type: Mapped[str | None] = mapped_column(Text, index=True)
    match_status: Mapped[str | None] = mapped_column(Text, index=True)


class CommercialContractPayment(Base, AuditMixin):
    __tablename__ = "commercial_contract_payments"
    __table_args__ = (
        UniqueConstraint("contract_key", "payment_month", name="uq_commercial_contract_payment_month"),
    )

    payment_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_key: Mapped[int] = mapped_column(Integer, ForeignKey("commercial_contracts.contract_key", ondelete="CASCADE"), index=True)
    payment_month: Mapped[str] = mapped_column(String(16), index=True)
    source_column: Mapped[str | None] = mapped_column(Text)
    amount_due: Mapped[int | None] = mapped_column(Integer, index=True)
    amount_paid: Mapped[int | None] = mapped_column(Integer, index=True)
    payment_status: Mapped[str | None] = mapped_column(Text, index=True)


class DataChangeLog(Base):
    __tablename__ = "data_change_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    record_key: Mapped[str | None] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CateringSyncRun(Base):
    __tablename__ = "catering_sync_runs"

    sync_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_spreadsheet_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unit_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    earning_source_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    earning_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    linked_earnings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unlinked_earnings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report_json: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)


class InspectionTemplate(Base, AuditMixin):
    __tablename__ = "inspection_templates"
    __table_args__ = (
        UniqueConstraint("template_code", "version", name="uq_inspection_templates_code_version"),
    )

    template_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    template_code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    domain: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_json: Mapped[str] = mapped_column(Text, nullable=False)


class Inspection(Base):
    __tablename__ = "inspections"

    inspection_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    station_code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("stations.station_code", ondelete="RESTRICT"),
        index=True,
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inspection_templates.template_id", ondelete="RESTRICT"),
        index=True,
    )
    inspector_name: Mapped[str] = mapped_column(String(255), index=True)
    inspection_type: Mapped[str] = mapped_column(String(32), default="scheduled", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    score: Mapped[int | None] = mapped_column(Integer)
    remarks: Mapped[str | None] = mapped_column(Text)
    device_id: Mapped[str | None] = mapped_column(String(128), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    server_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class InspectionResponse(Base):
    __tablename__ = "inspection_responses"

    response_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inspections.inspection_id", ondelete="CASCADE"),
        index=True,
    )
    section_code: Mapped[str] = mapped_column(String(64), index=True)
    question_code: Mapped[str] = mapped_column(String(128), index=True)
    response_value: Mapped[str | None] = mapped_column(String(64), index=True)
    remarks: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(32), index=True)
    asset_ref: Mapped[str | None] = mapped_column(String(128), index=True)
    platform: Mapped[str | None] = mapped_column(String(64), index=True)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_json: Mapped[str | None] = mapped_column(Text)
    client_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    server_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class InspectionFinding(Base):
    __tablename__ = "inspection_findings"

    finding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inspections.inspection_id", ondelete="CASCADE"),
        index=True,
    )
    response_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("inspection_responses.response_id", ondelete="SET NULL"),
        index=True,
    )
    station_code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("stations.station_code", ondelete="RESTRICT"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(32), default="medium", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False, index=True)
    responsible_party: Mapped[str | None] = mapped_column(String(255), index=True)
    target_date: Mapped[str | None] = mapped_column(String(32), index=True)
    financial_implication: Mapped[int | None] = mapped_column(Integer)
    repeat_observation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    client_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    server_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class InspectionEvidence(Base):
    __tablename__ = "inspection_evidence"

    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inspections.inspection_id", ondelete="CASCADE"),
        index=True,
    )
    response_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("inspection_responses.response_id", ondelete="SET NULL"),
        index=True,
    )
    question_code: Mapped[str | None] = mapped_column(String(128), index=True)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text)
    client_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    server_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class InspectionNote(Base):
    __tablename__ = "inspection_notes"

    note_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inspections.inspection_id", ondelete="CASCADE"),
        index=True,
    )
    section_code: Mapped[str | None] = mapped_column(String(64), index=True)
    question_code: Mapped[str | None] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text)
    client_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    server_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class MobileSyncOperation(Base):
    __tablename__ = "mobile_sync_operations"

    operation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="processed", nullable=False, index=True)
    result_json: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MobileChange(Base):
    __tablename__ = "mobile_changes"

    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

