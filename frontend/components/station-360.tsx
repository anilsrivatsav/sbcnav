// @ts-nocheck
"use client";
import { useState } from "react";
// Legacy API payloads are intentionally heterogeneous; feature typing is added at the API boundary.

import { BarChart3, CircleAlert, Database, TrainFront, Wallet, Wrench } from "lucide-react";
import { Badge, Button, DataTable, Panel, Tabs } from "./ui";
import { API_URL, fetchJson } from "../lib/api";

const boolText = (value) => (value ? "Yes" : "No");
const isAvailableUnit = (unit = {}) => String(unit.unit_status || "").trim().toLowerCase() === "available"
  || (!String(unit.licensee_name || "").trim() && !String(unit.contract_from || "").trim() && !String(unit.contract_to || "").trim());
const dailyFootfall = (station) => {
  const annual = Number(station.passenger_footfall || 0);
  return annual > 0 ? Math.round(annual / 30).toLocaleString("en-IN") : "NA";
};
const platformTotal = (rows = [], fallback = 0) => {
  const numbers = rows.flatMap((row) => String(row.platform || row.pf_no || "").match(/\d+/g) || [])
    .map(Number)
    .filter(Number.isFinite);
  return numbers.length ? Math.max(...numbers) : Number(fallback || rows.length || 0);
};

function KeyValueGrid({ rows }) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {rows.map(([label, value]) => (
        <div key={label} className="soft-raised rounded-lg border border-line p-3">
          <dt className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">{label}</dt>
          <dd className="mt-1 text-sm font-semibold text-ink">{value === null || value === undefined || value === "" ? "NA" : String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function StationMetric({ label, value, subtext, tone = "accent" }) {
  return (
    <div className="soft-surface rounded-lg border p-4">
      <div className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">{label}</div>
      <div className="mt-2 text-2xl font-black text-ink">{value}</div>
      <div className="mt-1 text-xs font-semibold text-muted">{subtext}</div>
      {tone === "danger" ? <div className="mt-3 h-1 rounded-full bg-red-500/70" /> : <div className="mt-3 h-1 rounded-full bg-accent/70" />}
    </div>
  );
}

function MonthlyMetrics({ station, record, money }) {
  const [rows, setRows] = useState(record.monthly_metrics || []);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [form, setForm] = useState({ passenger_footfall: "", tickets_issued: "", earnings: "" });
  const latest = rows[0] || record.latest_monthly_metric;
  const save = async () => {
    const saved = await fetchJson(`${API_URL}/api/stations/${encodeURIComponent(station.station_code)}/metrics/${month}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...form, passenger_footfall: form.passenger_footfall ? Number(form.passenger_footfall) : null, tickets_issued: form.tickets_issued ? Number(form.tickets_issued) : null, earnings: form.earnings ? Number(form.earnings) : null, source: "manual" }) });
    setRows((current) => [saved, ...current.filter((row) => row.metric_month !== saved.metric_month)]); setForm({ passenger_footfall: "", tickets_issued: "", earnings: "" });
  };
  return <Panel title="Monthly station metrics" subtitle="Latest month is shown first. Add footfall, tickets and earnings as each month closes."><div className="grid gap-3 sm:grid-cols-3"><StationMetric label="Latest footfall" value={latest?.passenger_footfall?.toLocaleString?.("en-IN") || "—"} subtext={latest?.metric_month || "No monthly entry yet"} /><StationMetric label="Latest tickets" value={latest?.tickets_issued?.toLocaleString?.("en-IN") || "—"} subtext="Tickets issued" /><StationMetric label="Latest earnings" value={latest ? money(latest.earnings) : "—"} subtext="Monthly earnings" /></div><div className="mt-4 grid gap-2 rounded-lg border border-line p-3 sm:grid-cols-5"><input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="rounded-md border border-line bg-surface px-2 py-2 text-sm" /><input type="number" placeholder="Footfall" value={form.passenger_footfall} onChange={(e) => setForm({ ...form, passenger_footfall: e.target.value })} className="rounded-md border border-line bg-surface px-2 py-2 text-sm" /><input type="number" placeholder="Tickets" value={form.tickets_issued} onChange={(e) => setForm({ ...form, tickets_issued: e.target.value })} className="rounded-md border border-line bg-surface px-2 py-2 text-sm" /><input type="number" placeholder="Earnings" value={form.earnings} onChange={(e) => setForm({ ...form, earnings: e.target.value })} className="rounded-md border border-line bg-surface px-2 py-2 text-sm" /><Button size="sm" onClick={save}>Save month</Button></div><div className="mt-4 space-y-2">{rows.slice(0, 12).map((row) => <div key={row.metric_id} className="flex flex-wrap justify-between gap-2 border-b border-line/70 py-2 text-sm"><span className="font-bold text-ink">{row.metric_month}</span><span className="text-muted">Footfall {row.passenger_footfall?.toLocaleString?.("en-IN") || "—"} · Tickets {row.tickets_issued?.toLocaleString?.("en-IN") || "—"} · {money(row.earnings)}</span></div>)}</div></Panel>;
}

function StationRiskPanel({ record, stationAlerts = [], qualityRows = [] }) {
  const station = record.station || {};
  const code = station.station_code;
  const summary = record.amenity_summary || {};
  const amenities = record.amenities || {};
  const actionCentre = record.action_centre || {};
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
  const actionRows = [
    ...(actionCentre.contract_alerts || []).map((row) => ({ type: "Contract", title: row.contract_name, status: row.days_to_expiry == null ? "Payment attention" : `${row.days_to_expiry} days to expiry` })),
    ...(actionCentre.open_works || []).map((row) => ({ type: "Work", title: row.short_name || row.work_name || row.project_id, status: row.status || "Open" })),
    ...(actionCentre.amenity_flags || []).map((row) => ({ type: "Amenity", title: row.label, status: row.severity || "Review" })),
    ...(actionCentre.open_findings || []).map((row) => ({ type: "Deficiency", title: row.title, status: row.status || "Open" })),
  ];

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <StationMetric label="Alerts" value={alerts.length} subtext="License fee or contract alerts" tone={alerts.length ? "danger" : "accent"} />
        <StationMetric label="Data Flags" value={issues.length + quality.length} subtext="Missing links or quality issues" tone={issues.length + quality.length ? "danger" : "accent"} />
        <StationMetric label="Open PA Works" value={summary.open_pa_works ?? 0} subtext="Passenger amenity work tracker" tone={summary.open_pa_works ? "danger" : "accent"} />
      </div>
      <Panel title="Action Centre" subtitle="Exceptions requiring follow-up at this station.">
        <div className="space-y-2">
          {actionRows.length ? actionRows.slice(0, 8).map((row, index) => (
            <div key={`${row.type}-${row.title}-${index}`} className="soft-raised flex items-center gap-3 rounded-lg border border-line p-3">
              <Badge tone={row.type === "Deficiency" || row.type === "Work" ? "danger" : "warning"}>{row.type}</Badge>
              <div className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">{row.title || "Needs review"}</div>
              <span className="shrink-0 text-xs font-bold text-muted">{row.status}</span>
            </div>
          )) : <Badge tone="accent">No immediate exceptions</Badge>}
        </div>
      </Panel>
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
            <div key={`${row.unit_no}-${index}`} className="soft-raised rounded-lg border border-line p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-black text-blue">{row.unit_no}</span>
                <Badge tone={row.alert_bucket === "overdue" ? "danger" : "accent"}>{String(row.alert_bucket || "alert").replaceAll("_", " ")}</Badge>
              </div>
              <div className="mt-1 text-sm text-muted">{row.licensee_name || "NA"} | Contract to {row.contract_to || "NA"} | Pending {row.estimated_pending_amount || 0}</div>
            </div>
          )) : <div className="text-sm text-muted">No report alerts for this station.</div>}
        </div>
      </Panel>
      <Panel title="Station Timeline" subtitle="Recent works, payments, inspections, and deficiencies.">
        <div className="space-y-2">
          {(actionCentre.timeline || []).slice(0, 8).map((row, index) => (
            <div key={`${row.type}-${row.record_id}-${index}`} className="flex items-center gap-3 border-b border-line/70 py-2 last:border-0">
              <Badge tone="neutral">{row.type}</Badge>
              <div className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">{row.title || "Record update"}</div>
              <span className="text-xs text-muted">{row.status || "Updated"}</span>
            </div>
          ))}
          {!actionCentre.timeline?.length ? <div className="text-sm text-muted">No station timeline events are available.</div> : null}
        </div>
      </Panel>
      <Panel title="Inspection Comparison" subtitle="What changed since the previous station inspection.">
        {actionCentre.inspection_comparison?.available ? (
          <div className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-3">
              <div className="soft-raised rounded-lg border border-line p-3">
                <div className="text-[10px] font-black uppercase tracking-[0.12em] text-muted">Current score</div>
                <div className="mt-1 text-lg font-black text-ink">{actionCentre.inspection_comparison.current?.score ?? "NA"}</div>
              </div>
              <div className="soft-raised rounded-lg border border-line p-3">
                <div className="text-[10px] font-black uppercase tracking-[0.12em] text-muted">Previous score</div>
                <div className="mt-1 text-lg font-black text-ink">{actionCentre.inspection_comparison.previous?.score ?? "NA"}</div>
              </div>
              <div className="soft-raised rounded-lg border border-line p-3">
                <div className="text-[10px] font-black uppercase tracking-[0.12em] text-muted">Score change</div>
                <div className={`mt-1 text-lg font-black ${(actionCentre.inspection_comparison.score_delta || 0) < 0 ? "text-red-700" : "text-emerald-700"}`}>
                  {actionCentre.inspection_comparison.score_delta == null ? "NA" : `${actionCentre.inspection_comparison.score_delta > 0 ? "+" : ""}${actionCentre.inspection_comparison.score_delta}`}
                </div>
              </div>
            </div>
            {actionCentre.inspection_comparison.changed_items?.length ? (
              <div className="space-y-2">
                {actionCentre.inspection_comparison.changed_items.slice(0, 8).map((item, index) => (
                  <div key={`${item.section_code}-${item.question_code}-${index}`} className="soft-inset rounded-lg border border-line p-3 text-sm">
                    <div className="font-bold text-ink">{item.question_code || "Checklist item"}</div>
                    <div className="mt-1 text-xs text-muted">{item.previous || "Not recorded"} → {item.current || "Not recorded"}{item.platform ? ` · PF ${item.platform}` : ""}</div>
                  </div>
                ))}
              </div>
            ) : <div className="text-sm text-muted">No checklist changes were recorded.</div>}
          </div>
        ) : <div className="text-sm text-muted">A comparison will appear after two inspections are available for this station.</div>}
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
  openCommercialContract,
  openUnit,
  openWork,
  onCreateAmenityFindings,
  money,
}) {
  const station = record.station || {};
  const amenities = record.amenities || {};
  const summary = record.amenity_summary || {};
  const compliance = record.amenity_compliance || {};
  const totalPlatforms = platformTotal(amenities.platforms, summary.platforms);
  const tabs = [
    { value: "overview", label: "Overview", icon: TrainFront },
    { value: "platforms", label: "Platforms", icon: BarChart3 },
    { value: "amenities", label: "Amenities", icon: Database },
    { value: "contracts", label: "Contracts", icon: Wallet },
    { value: "commercial", label: "Commercial", icon: Database },
    { value: "publicity", label: "Publicity", icon: Wallet },
    { value: "works", label: "Works", icon: Wrench },
    { value: "alerts", label: "Risks", icon: CircleAlert },
    { value: "norms", label: "Norms", icon: CircleAlert },
  ];

  return (
    <div className="space-y-4">
      <div className="soft-inset flex flex-col gap-3 rounded-lg border border-line p-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-[11px] font-black uppercase tracking-[0.18em] text-accent">Operational profile</div>
          <div className="mt-1 text-sm font-semibold text-muted">Linked amenities, contracts, commercial assets, works, and risks.</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={onEdit}>Edit Station</Button>
          <Button variant="danger" size="sm" onClick={onDelete} disabled={saving}>Delete</Button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <StationMetric label="Contracts" value={record.contracts?.length ?? record.units?.length ?? 0} subtext="Linked by station code" />
        <StationMetric label="Commercial" value={record.commercial_contracts?.length ?? 0} subtext="OOH, parking, ATM, mobile" />
        <StationMetric label="Works" value={record.works?.length ?? 0} subtext="Sanctioned works linked" />
        <StationMetric label="Platforms" value={totalPlatforms} subtext={summary.total_platform_length ? `${summary.total_platform_length} m total length` : "Highest platform number"} />
        <StationMetric label="Amenity Risk" value={summary.open_pa_works ?? 0} subtext="Open PA works" tone={summary.open_pa_works ? "danger" : "accent"} />
        <StationMetric label="Norm Compliance" value={compliance.compliance_percent == null ? "NA" : `${compliance.compliance_percent}%`} subtext={`${compliance.missing?.length ?? 0} norms need review`} tone={compliance.missing?.length ? "danger" : "accent"} />
      </div>

      <Tabs tabs={tabs} value={activeTab} onChange={onTabChange} />

      {activeTab === "overview" ? (
        <div className="space-y-4">
          <MonthlyMetrics station={station} record={record} money={money} />
          <KeyValueGrid
            rows={[
              ["Division", station.division],
              ["Zone", station.zone],
              ["Section", station.section],
              ["Category", station.categorisation],
              ["Platform Type", station.platform_type],
              ["Daily Footfall", dailyFootfall(station)],
              ["Total Platforms", totalPlatforms],
              ["Earnings Per Day", station.earnings_per_day],
              ["Passenger Range", station.passenger_range],
              ["Wheel Chairs", summary.wheel_chairs],
              ["Trolley Path", summary.trolley_path],
              ["Ramp Feasible", boolText(summary.ramp_feasible)],
              ["PF Extension Proposed", boolText(summary.pf_extension_proposed)],
            ]}
          />
          <Panel
            title="Passenger Amenity Compliance"
            subtitle="Category norms compared with linked station amenity records."
            action={compliance.missing?.length && onCreateAmenityFindings ? <Button size="sm" variant="secondary" onClick={() => onCreateAmenityFindings(record)}>Create findings</Button> : null}
          >
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
              {(compliance.by_category || []).map((row) => (
                <div key={row.category} className="soft-raised rounded-lg border border-line p-3">
                  <div className="text-xs font-black uppercase tracking-[0.12em] text-muted">{row.category}</div>
                  <div className="mt-1 text-xl font-black text-ink">{row.compliance_percent}%</div>
                  <div className="text-xs text-muted">{row.matched} of {row.total} matched</div>
                </div>
              ))}
            </div>
            {compliance.missing?.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {compliance.missing.slice(0, 24).map((row, index) => (
                  <Badge key={`${row.category}-${row.amenity}-${index}`} tone="danger">{row.category}: {row.amenity || row.norm}</Badge>
                ))}
              </div>
            ) : <div className="mt-3 text-sm text-muted">No missing norms were identified.</div>}
          </Panel>
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
            { key: "earnings_total", label: "Paid", value: (row) => isAvailableUnit(row) ? "" : row.earnings_total || 0, render: (row) => <span className="font-semibold">{isAvailableUnit(row) ? "Not applicable" : money(row.earnings_total)}</span> },
            { key: "pending_receipts", label: "Pending", value: (row) => isAvailableUnit(row) ? "" : row.pending_receipts, render: (row) => isAvailableUnit(row) ? <span className="text-muted">Not applicable</span> : row.pending_receipts },
          ]}
          rows={record.contracts || record.units || []}
          getKey={(row, index) => `${row.unit_no}-${index}`}
          onRowClick={openUnit}
          emptyTitle="No catering contracts or available units found for this station."
          fileName={`${station.station_code}-contracts.csv`}
        />
      ) : null}

      {activeTab === "commercial" ? (
        <DataTable
          columns={columns.commercialContractColumns}
          rows={record.commercial_contracts || []}
          getKey={(row, index) => `${row.contract_key}-${row.station_code}-${index}`}
          onRowClick={openCommercialContract}
          emptyTitle="No non-catering commercial contracts found for this station."
          fileName={`${station.station_code}-commercial-contracts.csv`}
        />
      ) : null}

      {activeTab === "publicity" ? (
        <DataTable
          columns={[
            { key: "contract_name", label: "Contract", value: (row) => row.contract_name },
            { key: "contractor", label: "Contractor", value: (row) => row.contractor?.legal_name },
            { key: "status", label: "Status", value: (row) => row.status },
            { key: "policy_code", label: "Policy", value: (row) => row.policy_code },
            { key: "total_contract_value", label: "Value", value: (row) => money(row.financials?.total_contract_value), render: (row) => money(row.financials?.total_contract_value) },
          ]}
          rows={record.publicity_contracts || []}
          getKey={(row) => row.contract_id}
          emptyTitle="No publicity contracts linked to this station."
          fileName={`${station.station_code}-publicity-contracts.csv`}
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
