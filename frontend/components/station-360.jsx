"use client";

import { BarChart3, CircleAlert, Database, TrainFront, Wallet, Wrench } from "lucide-react";
import { Badge, Button, DataTable, Panel, Tabs } from "./ui";

const boolText = (value) => (value ? "Yes" : "No");

function KeyValueGrid({ rows }) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {rows.map(([label, value]) => (
        <div key={label} className="rounded-xl border border-line bg-surface p-3">
          <dt className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">{label}</dt>
          <dd className="mt-1 text-sm font-semibold text-ink">{value === null || value === undefined || value === "" ? "NA" : String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function StationMetric({ label, value, subtext, tone = "accent" }) {
  return (
    <div className="rounded-2xl border border-line bg-surface/80 p-4">
      <div className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">{label}</div>
      <div className="mt-2 text-2xl font-black text-ink">{value}</div>
      <div className="mt-1 text-xs font-semibold text-muted">{subtext}</div>
      {tone === "danger" ? <div className="mt-3 h-1 rounded-full bg-red-500/70" /> : <div className="mt-3 h-1 rounded-full bg-accent/70" />}
    </div>
  );
}

function StationRiskPanel({ record, stationAlerts = [], qualityRows = [] }) {
  const station = record.station || {};
  const code = station.station_code;
  const summary = record.amenity_summary || {};
  const amenities = record.amenities || {};
  const pf = amenities.pf_extension_status || {};
  const issues = [
    ...(!record.contracts?.length && !record.units?.length ? ["No linked catering contracts"] : []),
    ...(!record.works?.length ? ["No linked sanctioned works"] : []),
    ...(!amenities.infra ? ["No station infra row linked"] : []),
    ...(!amenities.platforms?.length ? ["No platform detail rows"] : []),
    ...(!amenities.wheelchairs ? ["No wheelchair record"] : []),
    ...(pf.ramp_feasible && !pf.ramp_proposed ? ["Ramp feasible but not proposed"] : []),
    ...(summary.open_pa_works > 0 ? [`${summary.open_pa_works} open passenger amenity works`] : []),
  ];
  const alerts = stationAlerts.filter((row) => row.station_code === code);
  const quality = qualityRows.filter((row) => row.station_code === code);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <StationMetric label="Alerts" value={alerts.length} subtext="License fee or contract alerts" tone={alerts.length ? "danger" : "accent"} />
        <StationMetric label="Data Flags" value={issues.length + quality.length} subtext="Missing links or quality issues" tone={issues.length + quality.length ? "danger" : "accent"} />
        <StationMetric label="Open PA Works" value={summary.open_pa_works ?? 0} subtext="Passenger amenity work tracker" tone={summary.open_pa_works ? "danger" : "accent"} />
      </div>
      <Panel title="Missing Data / Risk Flags" subtitle="Station-level checks generated from linked datasets.">
        <div className="flex flex-wrap gap-2">
          {[...issues, ...quality.map((row) => row.problem)].length ? [...issues, ...quality.map((row) => row.problem)].map((item, index) => (
            <Badge key={`${item}-${index}`} tone="danger">{item}</Badge>
          )) : <Badge tone="accent">No obvious station data flags</Badge>}
        </div>
      </Panel>
      <Panel title="License Fee Alerts" subtitle="Rows from the reports module linked to this station.">
        <div className="space-y-2">
          {alerts.length ? alerts.map((row, index) => (
            <div key={`${row.unit_no}-${index}`} className="rounded-xl border border-line bg-surface p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-black text-blue">{row.unit_no}</span>
                <Badge tone={row.alert_bucket === "overdue" ? "danger" : "accent"}>{String(row.alert_bucket || "alert").replaceAll("_", " ")}</Badge>
              </div>
              <div className="mt-1 text-sm text-muted">{row.licensee_name || "NA"} | Contract to {row.contract_to || "NA"} | Pending {row.estimated_pending_amount || 0}</div>
            </div>
          )) : <div className="text-sm text-muted">No report alerts for this station.</div>}
        </div>
      </Panel>
    </div>
  );
}

export function Station360({
  record,
  activeTab,
  onTabChange,
  onEdit,
  onDelete,
  saving,
  columns,
  stationAlerts,
  qualityRows,
  openAmenity,
  openUnit,
  openWork,
  money,
}) {
  const station = record.station || {};
  const amenities = record.amenities || {};
  const summary = record.amenity_summary || {};
  const tabs = [
    { value: "overview", label: "Overview", icon: TrainFront },
    { value: "platforms", label: "Platforms", icon: BarChart3 },
    { value: "amenities", label: "Amenities", icon: Database },
    { value: "contracts", label: "Contracts", icon: Wallet },
    { value: "works", label: "Works", icon: Wrench },
    { value: "alerts", label: "Risks", icon: CircleAlert },
    { value: "norms", label: "Norms", icon: CircleAlert },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-2xl border border-line bg-surface/70 p-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-[11px] font-black uppercase tracking-[0.18em] text-accent">Station 360</div>
          <div className="mt-1 text-2xl font-black text-ink">{station.station_code} - {station.station_name || "Station"}</div>
          <div className="mt-1 text-sm text-muted">{station.division || "NA"} | {station.section || "NA"} | {station.categorisation || "NA"}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={onEdit}>Edit Station</Button>
          <Button variant="danger" size="sm" onClick={onDelete} disabled={saving}>Delete</Button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StationMetric label="Contracts" value={record.contracts?.length ?? record.units?.length ?? 0} subtext="Linked by station code" />
        <StationMetric label="Works" value={record.works?.length ?? 0} subtext="Sanctioned works linked" />
        <StationMetric label="Platforms" value={summary.platforms ?? amenities.platforms?.length ?? 0} subtext={summary.total_platform_length ? `${summary.total_platform_length} m total length` : "Platform details"} />
        <StationMetric label="Amenity Risk" value={summary.open_pa_works ?? 0} subtext="Open PA works" tone={summary.open_pa_works ? "danger" : "accent"} />
      </div>

      <Tabs tabs={tabs} value={activeTab} onChange={onTabChange} />

      {activeTab === "overview" ? (
        <div className="space-y-4">
          <KeyValueGrid
            rows={[
              ["Station Code", station.station_code],
              ["Station Name", station.station_name],
              ["Division", station.division],
              ["Section", station.section],
              ["Category", station.categorisation],
              ["Platform Type", station.platform_type],
              ["Footfall", station.passenger_footfall],
              ["Passenger Range", station.passenger_range],
              ["Wheel Chairs", summary.wheel_chairs],
              ["Trolley Path", summary.trolley_path],
              ["Ramp Feasible", boolText(summary.ramp_feasible)],
              ["PF Extension Proposed", boolText(summary.pf_extension_proposed)],
            ]}
          />
        </div>
      ) : null}

      {activeTab === "platforms" ? (
        <div className="space-y-4">
          <Panel title="PF Extension / Raising" subtitle="Station-specific status extracted from the FOB & PF extension workbook.">
            <KeyValueGrid
              rows={[
                ["PF Extension WIP", boolText(amenities.pf_extension_status?.pf_extension_wip)],
                ["PF Extension Proposed", boolText(amenities.pf_extension_status?.pf_extension_proposed)],
                ["Raising + Extension Proposed", boolText(amenities.pf_extension_status?.raising_extension_proposed)],
                ["Platform Extension Work Proposed", boolText(amenities.pf_extension_status?.platform_extension_work_proposed)],
                ["Source Category", amenities.pf_extension_status?.source_category],
                ["Source Rows", amenities.pf_extension_status?.source_rows],
                ["Source Detail", amenities.pf_extension_status?.status_text],
                ["Remarks", amenities.pf_extension_status?.remarks],
              ]}
            />
          </Panel>
          <DataTable
            columns={columns.platformColumns}
            rows={amenities.platforms || []}
            getKey={(row, index) => `${row.station_code}-${row.platform}-${index}`}
            onRowClick={openAmenity}
            emptyTitle="No platform-wise amenity details found for this station."
            fileName={`${station.station_code}-platforms.csv`}
          />
        </div>
      ) : null}

      {activeTab === "amenities" ? (
        <div className="space-y-4">
          <KeyValueGrid
            rows={[
              ["FOB / Access", amenities.infra?.fob_details],
              ["Shelter", amenities.infra?.shelter_details],
              ["Platform Count", amenities.infra?.platform_count],
              ["Platform Level", amenities.infra?.platform_level],
              ["Wheel Chairs", amenities.wheelchairs?.available_good_condition],
              ["Trolley Path", amenities.trolley?.trolley_path],
              ["Trolley Sanction", amenities.trolley?.trolley_path_sanction],
              ["Ramp Feasible", boolText(amenities.pf_extension_status?.ramp_feasible)],
              ["Ramp Proposed", boolText(amenities.pf_extension_status?.ramp_proposed)],
              ["Lift Available", boolText(amenities.pf_extension_status?.lift_available)],
              ["Lift Proposed", boolText(amenities.pf_extension_status?.lift_proposed)],
              ["Lift/Ramp Not Feasible", boolText(amenities.pf_extension_status?.not_feasible_lift_ramp)],
            ]}
          />
          <DataTable
            columns={columns.paWorkColumns}
            rows={amenities.pa_works || amenities.paWorks || []}
            getKey={(row, index) => `${row.work_type}-${row.station_code}-${index}`}
            onRowClick={openAmenity}
            emptyTitle="No passenger amenity work tracker rows found for this station."
            fileName={`${station.station_code}-pa-works.csv`}
          />
        </div>
      ) : null}

      {activeTab === "contracts" ? (
        <DataTable
          columns={[
            ...columns.unitColumns,
            { key: "earnings_total", label: "Paid", value: (row) => row.earnings_total || 0, render: (row) => <span className="font-semibold">{money(row.earnings_total)}</span> },
            { key: "pending_receipts", label: "Pending" },
          ]}
          rows={record.contracts || record.units || []}
          getKey={(row, index) => `${row.unit_no}-${index}`}
          onRowClick={openUnit}
          emptyTitle="No catering contracts found for this station."
          fileName={`${station.station_code}-contracts.csv`}
        />
      ) : null}

      {activeTab === "works" ? (
        <DataTable
          columns={columns.workColumns}
          rows={record.works || []}
          getKey={(row, index) => `${row.project_id}-${index}`}
          onRowClick={openWork}
          emptyTitle="No sanctioned works found for this station."
          fileName={`${station.station_code}-works.csv`}
        />
      ) : null}

      {activeTab === "alerts" ? (
        <StationRiskPanel record={record} stationAlerts={stationAlerts} qualityRows={qualityRows} />
      ) : null}

      {activeTab === "norms" ? (
        <DataTable
          columns={columns.normColumns}
          rows={amenities.norms || []}
          getKey={(row, index) => `${row.category}-${row.amenity}-${index}`}
          onRowClick={openAmenity}
          emptyTitle="No category norms found for this station."
          fileName={`${station.station_code}-norms.csv`}
        />
      ) : null}
    </div>
  );
}
