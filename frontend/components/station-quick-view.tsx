// @ts-nocheck
"use client";
// Station records retain source-specific fields; normalize them at the API boundary in the next pass.

import { BarChart3, ChevronRight, CircleAlert, Database, TrainFront, Users, Wallet, Wrench } from "lucide-react";
import { Badge, Button } from "./ui";

const valueText = (value) => value === null || value === undefined || value === "" ? "NA" : String(value);
const isAvailableUnit = (unit = {}) => String(unit.unit_status || "").trim().toLowerCase() === "available"
  || (!String(unit.licensee_name || "").trim() && !String(unit.contract_from || "").trim() && !String(unit.contract_to || "").trim());

const platformTotal = (rows = [], fallback = 0) => {
  const numbers = rows.flatMap((row) => String(row.platform || row.pf_no || "")
    .match(/\d+/g) || [])
    .map(Number)
    .filter(Number.isFinite);
  return numbers.length ? Math.max(...numbers) : Number(fallback || rows.length || 0);
};

const dailyFootfall = (station) => {
  const annual = Number(station.passenger_footfall || 0);
  return annual > 0 ? Math.round(annual / 30) : 0;
};

const compactNumber = (value) => {
  const number = Number(value || 0);
  if (!number) return "0";
  if (number >= 100000) return `${(number / 100000).toFixed(number >= 1000000 ? 1 : 2)} Lakh`;
  if (number >= 1000) return `${(number / 1000).toFixed(number >= 10000 ? 0 : 1)}K`;
  return number.toLocaleString("en-IN");
};

function SnapshotMetric({ icon: Icon, label, value, tone = "accent" }) {
  return (
    <div className="soft-raised flex min-w-0 items-center gap-3 rounded-lg border border-line p-3">
      <span className={tone === "danger" ? "rounded-md bg-red-500/10 p-2 text-red-600" : "rounded-md bg-accentSoft p-2 text-accentStrong"}>
        <Icon size={17} />
      </span>
      <span className="min-w-0">
        <span className="block text-[10px] font-black uppercase tracking-[0.14em] text-muted">{label}</span>
        <span className="mt-0.5 block truncate text-lg font-black text-ink">{value}</span>
      </span>
    </div>
  );
}

function PreviewList({ title, rows, empty, label, meta }) {
  return (
    <section className="soft-inset rounded-lg border border-line p-3">
      <h3 className="text-xs font-black uppercase tracking-[0.16em] text-ink">{title}</h3>
      <div className="mt-3 space-y-2">
        {rows.length ? rows.slice(0, 3).map((row, index) => (
          <div key={`${label(row)}-${index}`} className="border-b border-line/70 pb-2 last:border-0 last:pb-0">
            <div className="line-clamp-1 text-sm font-bold text-ink">{label(row)}</div>
            <div className="mt-0.5 line-clamp-1 text-xs text-muted">{meta(row)}</div>
          </div>
        )) : <p className="text-sm text-muted">{empty}</p>}
      </div>
    </section>
  );
}

export function StationQuickView({ record, loading, stationAlerts = [], onOpenDetail, money }) {
  const station = record?.station || {};
  const amenities = record?.amenities || {};
  const summary = record?.amenity_summary || {};
  const contracts = record?.contracts || record?.units || [];
  const commercial = record?.commercial_contracts || [];
  const works = record?.works || [];
  const alerts = stationAlerts.filter((row) => String(row.station_code || "") === String(station.station_code || ""));
  const platforms = platformTotal(amenities.platforms, summary.platforms);
  const access = [
    summary.wheel_chairs ? `${summary.wheel_chairs} wheelchair${Number(summary.wheel_chairs) === 1 ? "" : "s"}` : null,
    summary.ramp_feasible ? "Ramp feasible" : null,
    summary.lift_proposed ? "Lift proposed" : null,
    summary.trolley_path ? "Trolley path" : null,
  ].filter(Boolean);

  return (
    <div className="space-y-4">
      {loading ? (
        <div className="flex items-center gap-2 text-xs font-bold text-muted">
          <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
          Updating linked station data
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Badge tone="accent">{valueText(station.categorisation)}</Badge>
        <Badge>{valueText(station.division)} Division</Badge>
        <Badge>{valueText(station.section)}</Badge>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SnapshotMetric icon={Users} label="Daily footfall" value={compactNumber(dailyFootfall(station))} />
        <SnapshotMetric icon={BarChart3} label="Platforms" value={platforms} />
        <SnapshotMetric icon={Wallet} label="Contracts" value={contracts.length + commercial.length} />
        <SnapshotMetric icon={Wrench} label="Linked works" value={works.length} />
      </div>

      <div className="grid gap-3 lg:grid-cols-[1fr_1fr_0.9fr]">
        <PreviewList
          title="Current works"
          rows={works}
          empty="No station-linked works."
          label={(row) => valueText(row.short_name_of_work)}
          meta={(row) => `${valueText(row.status)} | ${money(row.cost)}`}
        />
        <PreviewList
          title="Contracts and available units"
          rows={[...contracts, ...commercial]}
          empty="No linked contracts."
          label={(row) => isAvailableUnit(row) ? `${valueText(row.unit_no)} · Available` : valueText(row.licensee_name || row.contract_name || row.unit_no)}
          meta={(row) => valueText(row.type_of_unit || row.policy || row.sub_category)}
        />
        <section className="soft-inset rounded-lg border border-line p-3">
          <h3 className="text-xs font-black uppercase tracking-[0.16em] text-ink">Access and attention</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {access.length ? access.map((item) => <Badge key={item} tone="accent">{item}</Badge>) : <Badge>No access details</Badge>}
            {summary.open_pa_works ? <Badge tone="danger">{summary.open_pa_works} open PA works</Badge> : null}
            {alerts.length ? <Badge tone="danger">{alerts.length} fee alerts</Badge> : null}
          </div>
        </section>
      </div>

      <div className="soft-inset grid gap-2 rounded-lg border border-line p-3 sm:grid-cols-2 lg:grid-cols-4">
        <Button variant="secondary" size="sm" onClick={() => onOpenDetail("platforms")}>
          <BarChart3 size={15} />
          Platforms
        </Button>
        <Button variant="secondary" size="sm" onClick={() => onOpenDetail("amenities")}>
          <TrainFront size={15} />
          Amenities
        </Button>
        <Button variant="secondary" size="sm" onClick={() => onOpenDetail("contracts")}>
          <Database size={15} />
          Contracts
        </Button>
        <Button variant={alerts.length || summary.open_pa_works ? "danger" : "secondary"} size="sm" onClick={() => onOpenDetail("alerts")}>
          <CircleAlert size={15} />
          Risks
        </Button>
      </div>

      <div className="flex justify-end">
        <Button onClick={() => onOpenDetail("overview")}>
          Detailed Station 360
          <ChevronRight size={16} />
        </Button>
      </div>
    </div>
  );
}
