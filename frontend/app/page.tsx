// @ts-nocheck
"use client";
// The main screen is being decomposed into typed feature modules incrementally.

import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Bot,
  CircleAlert,
  ChevronRight,
  Database,
  Download,
  FileText,
  Home,
  Moon,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings as SettingsIcon,
  Sun,
  Timer,
  TrainFront,
  TrendingUp,
  Trash2,
  UploadCloud,
  Users,
  Wallet,
  X,
  Wrench,
} from "lucide-react";
import { BottomSheet, DataTable } from "../components/ui";
import { Station360 } from "../components/station-360";
import { StationQuickView } from "../components/station-quick-view";
import { ReportTemplatesPanel } from "../components/reports/report-templates-panel";
import { API_URL, aiQueryUrl, amenityFindingsUrl, cateringSyncUrl, commercialContractDetailUrl, commercialContractStatementUrl, fetchJson, importCommercialContractsUrl, importPassengerAmenitiesUrl, importPfExtensionUrl, importSanctionedWorksUrl, previewPassengerAmenitiesUrl, previewSanctionedWorksUrl, reportPresetRunUrl, reportPresetsUrl, stationDetailUrl, workExpenditureUrl, workProgressUrl } from "../lib/api";
import { reportTemplates, templateFilterState, templatePreset } from "../lib/report-templates";
import { useRailDashboardData } from "../hooks/use-rail-dashboard-data";

const money = (value) => `INR ${Number(value || 0).toLocaleString("en-IN")}`;
const pretty = (value) => (value === null || value === undefined || value === "" ? "NA" : String(value));
const isAvailableUnit = (unit = {}) => {
  if (String(unit.unit_status || "").trim().toLowerCase() === "available") return true;
  return !String(unit.licensee_name || "").trim()
    && !String(unit.contract_from || "").trim()
    && !String(unit.contract_to || "").trim();
};
const toNumber = (value) => Number(value || 0);
const cx = (...classes) => classes.filter(Boolean).join(" ");
const normalizeText = (value) => pretty(value).toLowerCase().replace(/[–—]/g, "-").replace(/\s+/g, " ").trim();
const matchesQuery = (row, fields, query) => {
  const q = normalizeText(query);
  if (!q) return true;
  return fields.some((field) => normalizeText(typeof field === "function" ? field(row) : row[field]).includes(q));
};
const sameFilterValue = (value, filterValue) => filterValue === "All" || normalizeText(value) === normalizeText(filterValue);
const compactDate = (value) => {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString().slice(0, 10);
};
const parseContractDate = (value) => {
  if (!value) return null;
  const text = String(value).trim();
  const dayFirst = text.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})/);
  if (dayFirst) {
    const yearValue = Number(dayFirst[3]);
    const year = yearValue < 100 ? 2000 + yearValue : yearValue;
    return new Date(year, Number(dayFirst[2]) - 1, Number(dayFirst[1]));
  }
  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};
const contractDaysRemaining = (value) => {
  const due = parseContractDate(value);
  if (!due) return null;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(due.getFullYear(), due.getMonth(), due.getDate());
  return Math.round((target.getTime() - today.getTime()) / 86400000);
};
const contractRisk = (value) => {
  const days = contractDaysRemaining(value);
  if (days === null) return { days: null, label: "Validity missing", tone: "neutral" };
  if (days < 0) return { days, label: "Expired", tone: "danger" };
  if (days <= 10) return { days, label: days === 0 ? "Critical - today" : `Critical - ${days}d`, tone: "danger" };
  if (days <= 30) return { days, label: `Attention - ${days}d`, tone: "warning" };
  return { days, label: "Active", tone: "accent" };
};
const monthKey = (value) => compactDate(value).slice(0, 7);
const htmlEscape = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
const workReportSection = (row) => {
  const text = pretty(row.section).toLowerCase().trim();
  if (text.includes("north")) return "North";
  if (text.includes("south")) return "South";
  if (text.includes("east")) return "East";
  if (text.includes("west")) return "West";
  if (text === "div" || text.includes("division")) return "Division";
  if (text.includes("cao/cn") || text.includes("cao cn")) return "CAO/CN";
  if (text.includes("sr.dcm") || text.includes("sr dcm")) return "Sr.DCM";
  if (text.includes("sr.dste") || text.includes("sr dste")) return "Sr.DSTE";
  if (text.includes("sdee")) return "SDEE";
  if (text.includes("gsu") || text.includes("gati sakthi")) return "GSU/SBC";
  return pretty(row.section) === "NA" ? "Other" : pretty(row.section);
};

function StationMetricsReport() {
  const [rows, setRows] = useState([]);
  const [period, setPeriod] = useState("latest");
  useEffect(() => { fetchJson(`${API_URL}/api/station-metrics`).then((data) => setRows(data.items || [])).catch(() => setRows([])); }, []);
  const years = [...new Set(rows.map((row) => String(row.metric_month || "").slice(0, 4)).filter(Boolean))].sort().reverse();
  const visible = rows.filter((row) => period === "latest" ? row.metric_month === rows[0]?.metric_month : String(row.metric_month || "").startsWith(period));
  const totals = visible.reduce((sum, row) => ({ footfall: sum.footfall + Number(row.passenger_footfall || 0), tickets: sum.tickets + Number(row.tickets_issued || 0), earnings: sum.earnings + Number(row.earnings || 0) }), { footfall: 0, tickets: 0, earnings: 0 });
  return <Panel title="Station monthly metrics" subtitle="Latest month by default. Switch to a year or month to compare station inputs."><div className="flex flex-wrap items-end gap-3"><label className="space-y-1"><span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">Period</span><select value={period} onChange={(event) => setPeriod(event.target.value)} className="soft-inset h-11 rounded-lg border border-line px-3 text-sm"><option value="latest">Latest month</option>{years.map((year) => <optgroup key={year} label={year}>{Array.from({ length: 12 }, (_, index) => { const month = `${year}-${String(index + 1).padStart(2, "0")}`; return <option key={month} value={month}>{month}</option>; })}</optgroup>)}</select></label><Badge tone="accent">{visible.length} station entries</Badge></div><div className="mt-4 grid gap-3 sm:grid-cols-3"><Card icon={Users} label="Footfall" value={totals.footfall.toLocaleString("en-IN")} subtext="Selected period" /><Card icon={FileText} label="Tickets" value={totals.tickets.toLocaleString("en-IN")} subtext="Selected period" /><Card icon={Wallet} label="Earnings" value={money(totals.earnings)} subtext="Selected period" /></div></Panel>;
}
const workReportType = (row) => {
  const text = normalizeText(`${row.short_name_of_work || ""} ${row.work_name || ""} ${row.remarks || ""} ${row.category || ""} ${row.parent_work || ""} ${row.block_section_station || ""} ${row.scope_type || ""} ${row.scope_value || ""} ${row.match_status || ""} ${row.section || ""}`);
  const scope = normalizeText(`${row.scope_type || ""} ${row.scope_value || ""} ${row.match_status || ""} ${row.block_section_station || ""}`);
  if (scope.includes("abss")) return "ABSS works";
  if (text.includes("cao/cn") || text.includes("cao cn")) return "CAO/CN works";
  if (text.includes("goods") || text.includes("csgr") || text.includes("goods shed")) return "Goods / CSGR works";
  if (text.includes("fob") || text.includes("foot over")) return "FOB works";
  if (text.includes("platform shelter") || text.includes("shelter")) return "Platform shelter works";
  if (text.includes("platform") || text.includes("pf ext") || text.includes("raising")) return "Platform extension works";
  if (text.includes("divyang") || text.includes("ramp") || text.includes("accessible") || text.includes("lift")) return "Divyangjan works";
  if (text.includes("toilet") || text.includes("water") || text.includes("waiting hall") || text.includes("amenit")) return "Passenger amenity works";
  return "Other works";
};
const workDeletionRecommended = (row) => /proposal dropped|proposed for deletion|recommended for deletion|work deleted|deletion recommended/i.test(`${row.remarks || ""} ${row.engg_remarks || ""} ${row.status || ""}`);

const buttonClasses = {
  primary: "border border-accent bg-accent text-white shadow-raised hover:bg-accentStrong active:shadow-pressed",
  secondary: "soft-control text-ink hover:border-accent hover:text-accentStrong active:shadow-pressed",
  ghost: "border border-transparent text-muted hover:border-line hover:bg-surfaceStrong hover:text-ink",
  danger: "soft-control border-red-400/70 text-red-600 hover:bg-red-500/10 active:shadow-pressed",
};

function Button({ children, variant = "primary", size = "md", className = "", ...props }) {
  return (
    <button
      type="button"
      className={cx(
        "focus-ring inline-flex items-center justify-center gap-2 rounded-lg font-extrabold transition disabled:cursor-not-allowed disabled:opacity-60",
        size === "sm" ? "h-9 px-3 text-xs" : "h-11 px-4 text-sm",
        buttonClasses[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

function Badge({ children, tone = "neutral" }) {
  const tones = {
    neutral: "border-line bg-surfaceStrong text-muted",
    accent: "border-accent/30 bg-accentSoft text-accentStrong",
    success: "border-emerald-300/70 bg-emerald-500/10 text-emerald-700",
    warning: "border-amber-300/70 bg-amber-500/10 text-amber-700",
    danger: "border-red-300/70 bg-red-500/10 text-red-600",
  };
  return (
    <span className={cx("inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-black uppercase tracking-[0.12em]", tones[tone])}>
      {children}
    </span>
  );
}

function ListShell({ children }) {
  return (
    <div className="soft-scroll max-h-[62vh] overflow-auto pr-1">
      {children}
    </div>
  );
}

function ListFooter({ shown, total, onMore, onLess }) {
  if (total <= shown && shown <= 24) return null;
  return (
    <div className="soft-inset mt-4 flex flex-col items-center justify-between gap-3 rounded-lg border border-line px-4 py-3 text-sm text-muted sm:flex-row">
      <span>{Math.min(shown, total)} of {total} shown</span>
      <div className="flex gap-2">
        {shown < total ? (
          <Button variant="secondary" size="sm" onClick={onMore}>
            <ChevronRight size={14} />
            Show more
          </Button>
        ) : null}
        {shown > 24 ? (
          <Button variant="ghost" size="sm" onClick={onLess}>
            Show less
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function Tabs({ tabs, value, onChange }) {
  return (
    <div className="soft-inset soft-scroll flex gap-2 overflow-x-auto rounded-lg border border-line p-1.5">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const active = value === tab.value;
        return (
          <button
            key={tab.value}
            type="button"
            onClick={() => onChange(tab.value)}
            className={cx(
              "focus-ring inline-flex h-10 shrink-0 items-center gap-2 rounded-md px-3 text-xs font-black uppercase tracking-[0.12em] transition",
              active ? "bg-accent text-white shadow-raised" : "text-muted hover:bg-surfaceStrong hover:text-ink",
            )}
          >
            <Icon size={14} />
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

function Card({ icon: Icon, label, value, subtext }) {
  return (
    <div className="soft-surface rounded-lg border p-5 transition hover:-translate-y-0.5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-black uppercase tracking-[0.18em] text-muted">{label}</div>
          <div className="mt-2 text-2xl font-black text-ink">{value}</div>
        </div>
        <div className="soft-raised rounded-lg border border-accent/20 bg-accentSoft p-3 text-accentStrong">
          <Icon size={18} />
        </div>
      </div>
      <div className="mt-3 text-xs font-semibold text-muted">{subtext}</div>
    </div>
  );
}

function Panel({ title, subtitle, action, children }) {
  return (
    <section className="soft-surface rounded-lg border p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-black uppercase tracking-[0.18em] text-ink">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm text-muted">{subtitle}</p> : null}
        </div>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function EmptyState({ title, description }) {
  return (
    <div className="soft-inset rounded-lg border border-line px-5 py-8 text-center">
      <CircleAlert size={22} className="mx-auto text-muted" />
      <div className="mt-2 text-sm font-black text-ink">{title}</div>
      {description ? <div className="mt-1 text-xs text-muted">{description}</div> : null}
    </div>
  );
}

function ReportList({ rows = [], moneyValues = false, onSelect }) {
  return (
    <div className="space-y-2">
      {rows.length ? rows.map((row) => (
        <button
          key={row.label}
          type="button"
          onClick={() => onSelect?.(row)}
          className={cx(
            "soft-raised flex w-full items-center justify-between gap-3 rounded-lg border border-line px-3 py-2.5 text-left text-sm transition",
            onSelect ? "hover:border-accent hover:bg-surfaceStrong" : "cursor-default",
          )}
        >
          <span className="min-w-0 truncate text-muted">{row.label}</span>
          <span className="shrink-0 font-black text-ink">{moneyValues ? money(row.value) : row.value}</span>
        </button>
      )) : <div className="text-sm text-muted">No report rows available.</div>}
    </div>
  );
}

function SparkBars({ data, color = "#0f766e" }) {
  const max = Math.max(...(data.length ? data.map((d) => d.value) : [1]), 1);
  return (
    <div className="flex h-40 items-end gap-2">
      {data.map((item) => (
        <div key={item.label} className="flex min-w-0 flex-1 flex-col items-center gap-2">
          <div className="flex h-32 w-full items-end">
            <div className="w-full rounded-t-md" style={{ height: `${Math.max(10, (item.value / max) * 100)}%`, background: color }} />
          </div>
          <div className="w-full truncate text-center text-[11px] font-semibold text-muted">{item.label}</div>
        </div>
      ))}
    </div>
  );
}

function Donut({ series, totalLabel }) {
  const total = series.reduce((sum, item) => sum + item.value, 0) || 1;
  let cumulative = 0;
  const circumference = 2 * Math.PI * 42;
  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center">
      <svg viewBox="0 0 100 100" className="h-40 w-40">
        <circle cx="50" cy="50" r="42" fill="none" className="stroke-line" strokeWidth="12" />
        {series.map((slice) => {
          const start = cumulative / total;
          cumulative += slice.value;
          const dash = (slice.value / total) * circumference;
          return (
            <circle
              key={slice.label}
              cx="50"
              cy="50"
              r="42"
              fill="none"
              stroke={slice.color}
              strokeWidth="12"
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-start * circumference}
              transform="rotate(-90 50 50)"
            />
          );
        })}
      </svg>
      <div className="space-y-2">
        <div className="text-sm font-black text-ink">{totalLabel}</div>
        {series.map((slice) => (
          <div key={slice.label} className="flex items-center gap-2 text-xs text-muted">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: slice.color }} />
            <span>{slice.label}</span>
            <span className="font-semibold text-ink">{slice.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrendLine({ data, color = "#0f766e" }) {
  const width = 420;
  const height = 160;
  const padding = 20;
  const max = Math.max(...(data.length ? data.map((item) => item.value) : [0]), 1);
  const points = data
    .map((item, index) => {
      const x = padding + (index * (width - padding * 2)) / Math.max(data.length - 1, 1);
      const y = height - padding - (item.value / max) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-40 w-full">
      <polyline fill="none" stroke={color} strokeWidth="3" points={points} strokeLinecap="round" strokeLinejoin="round" />
      {data.map((item, index) => {
        const x = padding + (index * (width - padding * 2)) / Math.max(data.length - 1, 1);
        const y = height - padding - (item.value / max) * (height - padding * 2);
        return <circle key={item.label} cx={x} cy={y} r="4" fill={color} />;
      })}
    </svg>
  );
}

function NavButton({ active, icon: Icon, label, hint, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`focus-ring flex min-w-[184px] items-start gap-3 rounded-lg border px-3 py-3 text-left transition lg:w-full lg:min-w-0 ${active ? "border-accent bg-accentSoft text-accentStrong shadow-pressed" : "soft-raised border-line text-ink hover:border-accent hover:text-accentStrong"
        }`}
    >
      <span className="rounded-md border border-line bg-surfaceStrong p-1.5">
        <Icon size={16} className="shrink-0" />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-black">{label}</span>
        <span className="mt-0.5 block text-[11px] font-semibold text-muted">{hint}</span>
      </span>
    </button>
  );
}

function SearchInput({ value, onChange, placeholder = "Search current view" }) {
  return (
    <label className="relative block w-full">
      <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="soft-inset h-11 w-full rounded-lg border border-line pl-10 pr-3 text-sm outline-none placeholder:text-muted focus:border-accent"
        placeholder={placeholder}
      />
    </label>
  );
}

function FilterSelect({ label, value, onChange, options }) {
  return (
    <label className="grid gap-1">
      <span className="text-[11px] font-black uppercase tracking-[0.18em] text-muted">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="soft-inset h-11 rounded-lg border border-line px-3 text-sm outline-none focus:border-accent">
        {options.map((item) => (
          <option key={item} value={item}>{item}</option>
        ))}
      </select>
    </label>
  );
}

function Breadcrumbs({ title }) {
  return (
    <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-muted">
      <span className="inline-flex items-center gap-1 text-accent">
        <Home size={13} />
        Rail Dashboard
      </span>
      <ChevronRight size={13} />
      <span className="text-ink">{title}</span>
    </nav>
  );
}

function ThemeToggle({ theme, onToggle }) {
  const isDark = theme === "dark";
  return (
    <button
      type="button"
      onClick={onToggle}
      className="soft-control inline-flex h-11 items-center justify-center gap-2 rounded-lg px-3 text-sm font-extrabold text-ink transition hover:border-accent active:shadow-pressed"
      aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
    >
      {isDark ? <Sun size={16} /> : <Moon size={16} />}
      <span>{isDark ? "Light" : "Dark"}</span>
    </button>
  );
}

function Modal({ open, title, subtitle, onClose, children }) {
  useEffect(() => {
    if (!open) return;
    const handler = (e) => e.key === "Escape" && onClose();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handler);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handler);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-3">
      <div role="dialog" aria-modal="true" aria-label={title} className="max-h-[92vh] w-full max-w-5xl overflow-hidden rounded-lg border border-line bg-surface shadow-overlay">
        <div className="flex items-start justify-between gap-4 border-b border-line bg-surfaceStrong px-4 py-4">
          <div>
            <div className="text-[11px] font-black uppercase tracking-[0.2em] text-accent">Detail view</div>
            <h3 className="mt-1 text-xl font-black text-ink">{title}</h3>
            {subtitle ? <p className="mt-1 text-sm text-muted">{subtitle}</p> : null}
          </div>
          <button type="button" onClick={onClose} className="focus-ring soft-control rounded-full p-2 text-ink transition hover:border-accent active:shadow-pressed">
            <X size={18} />
          </button>
        </div>
        <div className="max-h-[calc(92vh-88px)] overflow-auto p-4">{children}</div>
      </div>
    </div>
  );
}

function KeyValueGrid({ rows }) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {rows.map(([label, value]) => (
        <div key={label} className="soft-raised rounded-lg border border-line p-3">
          <dt className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">{label}</dt>
          <dd className="mt-1 text-sm font-semibold text-ink">{pretty(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function RecordForm({ fields, value, onChange, onSubmit, onCancel, saving, mode, error }) {
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        {fields.map((field) => (
          <label key={field.name} className="grid gap-1">
            <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">{field.label}</span>
            <input
              type={field.type || "text"}
              value={value[field.name] ?? ""}
              onChange={(event) => onChange({ ...value, [field.name]: event.target.value })}
              disabled={field.readOnly && mode === "edit"}
              required={field.required}
              className="soft-inset h-11 rounded-lg border border-line px-3 text-sm outline-none disabled:bg-surfaceStrong disabled:text-muted focus:border-accent"
            />
          </label>
        ))}
      </div>
      {error ? (
        <div className="rounded-lg border border-red-300/70 bg-red-500/10 px-3 py-2 text-sm font-semibold text-red-500">
          {error}
        </div>
      ) : null}
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>
    </form>
  );
}

function DetailActions({ onEdit, onDelete, saving }) {
  return (
    <div className="flex flex-wrap justify-end gap-2">
      <Button variant="secondary" size="sm" onClick={onEdit}>
        <Pencil size={14} />
        Edit
      </Button>
      <Button variant="danger" size="sm" onClick={onDelete} disabled={saving}>
        <Trash2 size={14} />
        Delete
      </Button>
    </div>
  );
}

export default function Page() {
  const crudFields = {
    stations: [
      { name: "station_code", label: "Station Code", required: true, readOnly: true },
      { name: "station_name", label: "Station Name", required: true },
      { name: "division", label: "Division" },
      { name: "zone", label: "Zone" },
      { name: "section", label: "Section" },
      { name: "categorisation", label: "Category" },
      { name: "platform_type", label: "Platform Type" },
      { name: "passenger_footfall", label: "Passenger Footfall", type: "number" },
      { name: "earnings_per_day", label: "Earnings Per Day", type: "number" },
      { name: "footfalls_per_day", label: "Footfalls Per Day", type: "number" },
    ],
    units: [
      { name: "unit_no", label: "Unit No.", required: true, readOnly: true },
      { name: "station_code", label: "Station Code" },
      { name: "type_of_unit", label: "Type of Unit" },
      { name: "station_category", label: "Station Category" },
      { name: "licensee_name", label: "Licensee Name" },
      { name: "license_fee", label: "License Fee" },
      { name: "unit_status", label: "Unit Status" },
      { name: "remarks", label: "Remarks" },
      { name: "contract_from", label: "Contract From" },
      { name: "contract_to", label: "Contract To" },
      { name: "pf_no", label: "PF No." },
    ],
    earnings: [
      { name: "receipt_key", label: "Receipt Key", readOnly: true },
      { name: "unit_no", label: "Unit No.", required: true },
      { name: "station_code", label: "Station Code" },
      { name: "licensee_name", label: "Licensee Name" },
      { name: "date_of_receipt", label: "Date of Receipt" },
      { name: "payment_head", label: "Payment Head" },
      { name: "payment_sub_head", label: "Payment Sub-head" },
      { name: "amount", label: "Amount", type: "number" },
      { name: "gst", label: "GST", type: "number" },
      { name: "receipt_type", label: "Receipt Type" },
      { name: "mr_no", label: "MR No." },
      { name: "mr_date", label: "MR Date" },
    ],
    works: [
      { name: "project_id", label: "Project ID", required: true, readOnly: true },
      { name: "source_project_id", label: "Original Project ID" },
      { name: "source_sn", label: "Sheet SN", type: "number" },
      { name: "short_name_of_work", label: "Short Name of Work", required: true },
      { name: "status", label: "Status" },
      { name: "date_of_sanction", label: "Date of Sanction" },
      { name: "block_section_station", label: "Block Section Station" },
      { name: "section", label: "Section" },
      { name: "allocation", label: "Allocation" },
      { name: "cost", label: "Cost", type: "number" },
      { name: "expenditure_upto_date", label: "Expenditure Upto Date", type: "number" },
      { name: "physical_progress", label: "Physical Progress" },
      { name: "financial_progress", label: "Financial Progress" },
      { name: "anticipated_expenditure", label: "Anticipated Expenditure", type: "number" },
      { name: "tdc", label: "Target Completion (TDC)" },
      { name: "remarks", label: "Remarks" },
      { name: "engg_remarks", label: "Engineering Remarks" },
    ],
    "commercial-contracts": [
      { name: "contract_key", label: "Contract Key", readOnly: true },
      { name: "contract_name", label: "Contract Name", required: true },
      { name: "licensee_name", label: "Licensee Name" },
      { name: "policy", label: "Policy" },
      { name: "sub_category", label: "Sub Category" },
      { name: "asset_scope", label: "Asset Scope" },
      { name: "raw_station_value", label: "Raw Station Value" },
      { name: "station_match_status", label: "Station Match Status" },
      { name: "allocation_code", label: "Allocation Code" },
      { name: "contract_allotted_on", label: "Allotted On" },
      { name: "contract_period_from", label: "Contract From" },
      { name: "contract_upto", label: "Contract Upto" },
      { name: "space_sq_ft", label: "Space Sq Ft", type: "number" },
      { name: "annual_license_fee", label: "Annual License Fee", type: "number" },
      { name: "quarterly_license_fee", label: "Quarterly License Fee", type: "number" },
      { name: "remarks", label: "Remarks" },
    ],
  };

  const resourcePath = { stations: "stations", units: "units", earnings: "earnings", works: "works", "commercial-contracts": "commercial-contracts" };
  const keyField = { stations: "station_code", units: "unit_no", earnings: "receipt_key", works: "project_id", "commercial-contracts": "contract_key" };

  const {
    stats,
    dataCentre,
    actionCentre,
    stations,
    units,
    earnings,
    works,
    workMonitoring,
    commercialContracts,
    commercialContractReports,
    contractAlerts,
    paSummary,
    paInfra,
    paPlatforms,
    paWheelchairs,
    paTrolley,
    paWorks,
    paPfExtension,
    paNorms,
    paReports,
    reports,
    loading,
    setLoading,
    activityStatus,
    setActivityStatus,
    lastRefreshAt,
    loadFromDb,
    loadData,
  } = useRailDashboardData();
  const [view, setView] = useState("dashboard");
  const [theme, setTheme] = useState("light");
  const [search, setSearch] = useState({ dashboard: "", stations: "", contracts: "", commercial: "", units: "", earnings: "", works: "", amenities: "", reports: "", ai: "", settings: "" });
  const [visibleLimit, setVisibleLimit] = useState({ stations: 24, units: 24, earnings: 24, works: 24, reports: 24, commercial: 24 });
  const [amenityTab, setAmenityTab] = useState("summary");
  const [contractTab, setContractTab] = useState("units");
  const [workTab, setWorkTab] = useState("station");
  const [stationModalTab, setStationModalTab] = useState("overview");
  const [reportTab, setReportTab] = useState("overview");
  const [contractExpiryWindow, setContractExpiryWindow] = useState(30);
  const [reportFilters, setReportFilters] = useState({
    month: "",
    dateFrom: "",
    dateTo: "",
    station: "All",
    division: "All",
    section: "All",
    needsActionOnly: false,
  });
  const [reportPresets, setReportPresets] = useState([]);
  const [reportPresetName, setReportPresetName] = useState("");
  const [reportPresetSchedule, setReportPresetSchedule] = useState("");
  const [reportWorkSection, setReportWorkSection] = useState("All");
  const [reportWorkType, setReportWorkType] = useState("All");
  const [drillDown, setDrillDown] = useState({ open: false, title: "", rows: [], columns: [], type: null });
  const [filters, setFilters] = useState({
    stationCategory: "All",
    stationDivision: "All",
    stationSection: "All",
    stationPlatform: "All",
    unitCategory: "All",
    unitType: "All",
    unitStatus: "All",
    workStation: "All",
    workScope: "All",
    workStatus: "All",
    commercialStation: "All",
    commercialAllocation: "All",
    commercialPolicy: "All",
    commercialSubCategory: "All",
    commercialAssetScope: "All",
    commercialStationStatus: "All",
  });
  const [modal, setModal] = useState({ open: false, type: null, record: null });
  const [stationSheet, setStationSheet] = useState({ open: false, record: null, loading: false });
  const [formModal, setFormModal] = useState({ open: false, type: "stations", mode: "create", data: {} });
  const [formError, setFormError] = useState("");
  const [importModal, setImportModal] = useState({ open: false, resource: "stations", csvText: "", url: "", result: null });
  const [saving, setSaving] = useState(false);
  const [progressDraft, setProgressDraft] = useState({ update_date: new Date().toISOString().slice(0, 10), progress_percent: "", expenditure_upto_date: "", status: "", remarks: "" });
  const [aiQuestion, setAiQuestion] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [aiError, setAiError] = useState("");
  const [cateringSyncResult, setCateringSyncResult] = useState(null);

  const aiSuggestions = [
    "Tell me everything about KSM",
    "Show pending license fee alerts",
    "Which works are still pending?",
    "Which stations need ramp or lift attention?",
    "Show units with missing license fee",
    "Give station coverage summary",
    "Show inconsistent work statuses",
    "Show duplicate receipts",
    "Show duplicate contracts",
    "Show missing station links",
    "Draft an action letter for SBC",
  ];

  const importPassengerAmenities = async () => {
    setLoading(true);
    setActivityStatus("Importing Passenger Amenity data from PA Infra Master...");
    try {
      const result = await fetchJson(importPassengerAmenitiesUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tab: "all" }),
      });
      await loadFromDb();
      const total = Object.values(result || {}).reduce((sum, item) => sum + (item?.upserted || 0), 0);
      setActivityStatus(`Passenger Amenity data imported: ${total} rows`);
    } catch (error) {
      setActivityStatus(error?.message || "Passenger Amenity import failed");
    } finally {
      setLoading(false);
    }
  };

  const syncCateringData = async () => {
    setLoading(true);
    setCateringSyncResult(null);
    setActivityStatus("Validating and synchronizing catering units and receipts...");
    try {
      const result = await fetchJson(cateringSyncUrl(), { method: "POST" });
      setCateringSyncResult(result);
      await loadFromDb();
      const source = result?.source || {};
      const applied = result?.applied || {};
      setActivityStatus(`Catering synchronized: ${source.units || 0} units, ${source.earnings || 0} unique receipts, ${source.duplicate_earning_rows || 0} duplicates removed`);
      return applied;
    } catch (error) {
      setActivityStatus(error?.message || "Catering synchronization failed");
      return null;
    } finally {
      setLoading(false);
    }
  };

  const importPfExtensionWorkbook = async () => {
    setLoading(true);
    setActivityStatus("Importing PF extension and ramp/lift workbook...");
    try {
      const result = await fetchJson(importPfExtensionUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      await loadFromDb();
      setActivityStatus(`PF extension imported: ${result?.station_status_upserted || 0} station statuses`);
    } catch (error) {
      setActivityStatus(error?.message || "PF extension import failed");
    } finally {
      setLoading(false);
    }
  };

  const importCommercialContractsWorkbook = async () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".xlsx,.xls";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      setLoading(true);
      setActivityStatus("Importing commercial contracts workbook...");
      try {
        const formData = new FormData();
        formData.append("file", file);
        const result = await fetchJson(importCommercialContractsUrl(), {
          method: "POST",
          body: formData,
        });
        await loadFromDb();
        setActivityStatus(`Commercial contracts imported: ${result?.upserted || 0} contracts, ${result?.payments || 0} payments`);
      } catch (error) {
        setActivityStatus(error?.message || "Commercial contracts import failed");
      } finally {
        setLoading(false);
      }
    };
    input.click();
  };

  const importSanctionedWorks = async () => {
    setLoading(true);
    setActivityStatus("Comparing sanctioned works source with PostgreSQL...");
    try {
      const preview = await fetchJson(previewSanctionedWorksUrl(), { method: "POST" });
      const summary = `Source ${preview.source_count}, database ${preview.postgres_count}; +${preview.added?.count || 0} added, ${preview.changed?.count || 0} changed, ${preview.removed?.count || 0} removed`;
      if (!window.confirm(`${summary}. Apply this validated source to PostgreSQL?`)) {
        setActivityStatus("Works refresh cancelled; PostgreSQL was not changed.");
        return;
      }
      setActivityStatus("Applying validated sanctioned works transaction...");
      const result = await fetchJson(importSanctionedWorksUrl(), { method: "POST" });
      await loadFromDb();
      setActivityStatus(`Sanctioned works imported: ${result?.rows || 0} rows`);
    } catch (error) {
      setActivityStatus(error?.message || "Sanctioned works import failed");
    } finally {
      setLoading(false);
    }
  };

  const refreshAllSources = async () => {
    setLoading(true);
    setCateringSyncResult(null);
    const outcomes = [];
    setActivityStatus("Refreshing all validated sources...");
    try {
      try {
        const result = await fetchJson(cateringSyncUrl(), { method: "POST" });
        setCateringSyncResult(result);
        outcomes.push(`catering ${result?.source?.units || 0} units`);
      } catch (error) {
        outcomes.push(`catering failed: ${error?.message || "error"}`);
      }

      try {
        const preview = await fetchJson(previewPassengerAmenitiesUrl(), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tab: "all" }),
        });
        const tabs = Object.values(preview?.tabs || {});
        const summary = tabs.reduce((total, item) => total + Number(item?.added?.count || 0) + Number(item?.changed?.count || 0), 0);
        if (window.confirm(`Passenger amenities: ${summary} added or changed rows across ${tabs.length} tabs. Apply the validated transaction?`)) {
          const result = await fetchJson(importPassengerAmenitiesUrl(), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tab: "all" }),
          });
          const total = Object.values(result || {}).reduce((sum, item) => sum + (item?.upserted || 0), 0);
          outcomes.push(`amenities ${total} rows`);
        } else {
          outcomes.push("amenities skipped by user");
        }
      } catch (error) {
        outcomes.push(`amenities failed: ${error?.message || "error"}`);
      }

      try {
        const preview = await fetchJson(previewSanctionedWorksUrl(), { method: "POST" });
        const summary = `Works source ${preview.source_count}, database ${preview.postgres_count}; +${preview.added?.count || 0} added, ${preview.changed?.count || 0} changed, ${preview.removed?.count || 0} removed, ${preview.unmatched?.count || 0} unmatched.`;
        if (window.confirm(`${summary}\n\nApply the validated works transaction?`)) {
          const result = await fetchJson(importSanctionedWorksUrl(), { method: "POST" });
          outcomes.push(`works ${result?.rows || 0} rows`);
        } else {
          outcomes.push("works skipped by user");
        }
      } catch (error) {
        outcomes.push(`works failed: ${error?.message || "error"}`);
      }

      await loadFromDb();
      setActivityStatus(`Refresh finished: ${outcomes.join(" · ")}`);
    } finally {
      setLoading(false);
    }
  };

  const submitAiQuery = async (question = aiQuestion) => {
    const text = question.trim();
    if (!text) return;
    setAiLoading(true);
    setAiError("");
    setAiQuestion(text);
    setActivityStatus("Asking AI...");
    try {
      const result = await fetchJson(aiQueryUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, context: {} }),
      });
      setAiResult(result);
      setActivityStatus("AI answer ready");
    } catch (error) {
      setAiError(error?.message || "AI query failed");
      setActivityStatus(error?.message || "AI query failed");
    } finally {
      setAiLoading(false);
    }
  };

  useEffect(() => {
    setActivityStatus("Ready");
  }, []);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    const stored = window.localStorage.getItem("rail-dashboard-theme");
    if (stored === "dark" || stored === "light") {
      setTheme(stored);
    }
    try {
      setReportPresets(JSON.parse(window.localStorage.getItem("rail-report-presets") || "[]"));
    } catch {
      setReportPresets([]);
    }
    fetchJson(reportPresetsUrl())
      .then((rows) => {
        if (Array.isArray(rows) && rows.length) {
          setReportPresets(rows.map((row) => ({
            id: row.preset_id,
            name: row.name,
            reportTab: row.report_tab,
            reportFilters: row.filters || {},
            schedule: row.schedule || "",
          })));
        }
      })
      .catch(() => {
        // Local presets remain available when the API is offline.
      });
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("rail-dashboard-theme", theme);
  }, [theme]);

  useEffect(() => {
    window.localStorage.setItem("rail-report-presets", JSON.stringify(reportPresets));
  }, [reportPresets]);

  useEffect(() => {
    if (!["station", "abss", "division"].includes(workTab)) {
      setWorkTab("station");
    }
  }, [workTab]);

  const toggleTheme = () => setTheme((current) => (current === "dark" ? "light" : "dark"));

  const completedWorks = useMemo(() => works.filter((work) => /complete|done/i.test(String(work.status || ""))).length, [works]);
  const pendingWorks = useMemo(() => works.filter((work) => !/complete|done/i.test(String(work.status || ""))).length, [works]);
  const paidEarnings = useMemo(() => earnings.filter((entry) => /paid|received/i.test(String(entry.receipt_type || ""))).length, [earnings]);
  const pendingEarnings = useMemo(() => earnings.filter((entry) => /pending/i.test(String(entry.receipt_type || ""))).length, [earnings]);

  const worksByStation = useMemo(() => {
    const counts = new Map();
    works.forEach((work) => {
      const key = work.station_code || work.scope_value || "Other";
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return Array.from(counts.entries()).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value).slice(0, 8);
  }, [works]);

  const worksByCategory = useMemo(() => {
    const counts = new Map();
    works.forEach((work) => {
      const key = work.scope_type || "Other";
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return Array.from(counts.entries()).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
  }, [works]);

  const revenueTrend = useMemo(() => {
    const buckets = new Map();
    earnings.forEach((entry) => {
      const raw = entry.date_of_receipt || entry.mr_date || "";
      const month = raw ? raw.slice(0, 7) : "Unknown";
      buckets.set(month, (buckets.get(month) || 0) + toNumber(entry.amount));
    });
    return Array.from(buckets.entries()).map(([label, value]) => ({ label, value })).slice(-8);
  }, [earnings]);

  const statusDistribution = useMemo(() => {
    const counts = new Map();
    works.forEach((work) => {
      const key = work.status || "Unknown";
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    const palette = ["#0f766e", "#2563eb", "#8b5cf6", "#f59e0b", "#ef4444", "#14b8a6"];
    return Array.from(counts.entries()).map(([label, value], index) => ({ label, value, color: palette[index % palette.length] }));
  }, [works]);

  const recentActivity = useMemo(() => {
    const latestReceipts = earnings.slice(0, 4).map((entry) => ({
      label: `${entry.unit_no || "No unit"} • ${entry.receipt_type || "Receipt"}`,
      value: money(entry.amount),
    }));
    const latestWorks = works.slice(0, 4).map((work) => ({
      label: `${work.project_id || "Work"} • ${work.short_name_of_work || "Unnamed"}`,
      value: pretty(work.status),
    }));
    return [...latestReceipts, ...latestWorks].slice(0, 8);
  }, [earnings, works]);

  const filteredStations = useMemo(() => {
    const q = search.stations;
    return stations.filter((row) => {
      const searchOk = matchesQuery(row, ["station_code", "station_name", "division", "section", "categorisation", "platform_type"], q);
      const catOk = sameFilterValue(row.categorisation, filters.stationCategory);
      const divOk = sameFilterValue(row.division, filters.stationDivision);
      const secOk = sameFilterValue(row.section, filters.stationSection);
      const platOk = sameFilterValue(row.platform_type, filters.stationPlatform);
      return searchOk && catOk && divOk && secOk && platOk;
    });
  }, [stations, search.stations, filters]);

  const filteredUnits = useMemo(() => {
    const q = search.units;
    return units.filter((row) => {
      const searchOk = matchesQuery(row, ["unit_no", "station_code", "station_name", "licensee_name", "unit_status", "remarks", "station_category", "type_of_unit", "pf_no"], q);
      const catOk = sameFilterValue(row.station_category, filters.unitCategory);
      const typeOk = sameFilterValue(row.type_of_unit, filters.unitType);
      const statusOk = sameFilterValue(row.unit_status, filters.unitStatus);
      return searchOk && catOk && typeOk && statusOk;
    });
  }, [units, search.units, filters]);

  const filteredEarnings = useMemo(() => {
    const q = search.earnings;
    return earnings.filter((row) => matchesQuery(row, ["unit_no", "station_code", "licensee_name", "payment_head", "payment_sub_head", "receipt_type", "mr_no", "amount"], q));
  }, [earnings, search.earnings]);

  const filteredContracts = useMemo(() => {
    const q = search.contracts || "";
    return {
      units: units.filter((row) => matchesQuery(row, ["unit_no", "station_code", "station_name", "licensee_name", "unit_status", "remarks", "station_category", "type_of_unit", "pf_no"], q)),
      earnings: earnings.filter((row) => matchesQuery(row, ["unit_no", "station_code", "licensee_name", "payment_head", "payment_sub_head", "receipt_type", "mr_no", "amount"], q)),
    };
  }, [units, earnings, search.contracts]);

  const filteredCommercialContracts = useMemo(() => {
    const q = search.commercial || "";
    return commercialContracts.filter((row) => {
      const searchOk = matchesQuery(row, ["contract_name", "licensee_name", "allocation_code", "policy", "sub_category", "asset_scope", "station_code", "station_name", "raw_station_value", "station_match_status", "annual_license_fee"], q);
      const policyOk = sameFilterValue(row.policy, filters.commercialPolicy);
      const stationOk = sameFilterValue(row.station_code, filters.commercialStation);
      const allocationOk = sameFilterValue(row.allocation_code, filters.commercialAllocation);
      const subOk = sameFilterValue(row.sub_category, filters.commercialSubCategory);
      const scopeOk = sameFilterValue(row.asset_scope, filters.commercialAssetScope);
      const stationStatusOk = sameFilterValue(row.station_match_status, filters.commercialStationStatus);
      return searchOk && stationOk && allocationOk && policyOk && subOk && scopeOk && stationStatusOk;
    });
  }, [commercialContracts, search.commercial, filters]);

  const filteredWorks = useMemo(() => {
    const q = search.works;
    const baseRows = works.filter((row) => {
      const searchOk = matchesQuery(row, ["project_id", "source_project_id", "source_sn", "short_name_of_work", "block_section_station", "section", "status", "station_code", "scope_value", "allocation", "physical_progress"], q);
      const statusOk = sameFilterValue(row.status, filters.workStatus);
      return searchOk && statusOk;
    });
    const stationRows = baseRows.filter((row) => sameFilterValue(row.scope_type, "Station") && row.station_code);
    const abssRows = baseRows.filter((row) => sameFilterValue(row.scope_type, "ABSS"));
    const divisionRows = baseRows.filter((row) => sameFilterValue(row.scope_type, "Division"));
    const stationFilteredRows = stationRows.filter((row) => sameFilterValue(row.station_code, filters.workStation));
    return {
      station: stationFilteredRows,
      abss: abssRows,
      division: divisionRows,
      all: baseRows,
    };
  }, [works, search.works, filters.workStation, filters.workStatus]);

  const filteredAmenities = useMemo(() => {
    const q = search.amenities;
    const filterRows = (rows, fields) => rows.filter((row) => matchesQuery(row, fields, q));
    return {
      summary: filterRows(paSummary, ["station_code", "station_name", "division", "section", "category", "trolley_path", "fob_details"]),
      infra: filterRows(paInfra, ["station_code", "station_name", "division", "section", "category", "fob_details", "shelter_details"]),
      platforms: filterRows(paPlatforms, ["station_code", "station_name", "division", "section", "platform"]),
      wheelchairs: filterRows(paWheelchairs, ["station_code", "station_name", "division", "section", "category"]),
      trolley: filterRows(paTrolley, ["station_code", "station_name", "division", "section", "categorisation", "trolley_path"]),
      paWorks: filterRows(paWorks, ["station_code", "station_name", "work_type", "work_name", "progress", "tender_status", "executive_agency"]),
      pfExtension: filterRows(paPfExtension, ["station_code", "station_name", "division", "section", "category", "status_text", "remarks"]),
      norms: filterRows(paNorms, ["category", "amenity", "norm", "norm_quantity"]),
      sanctionedWorks: filteredWorks.station,
    };
  }, [search.amenities, paSummary, paInfra, paPlatforms, paWheelchairs, paTrolley, paWorks, paPfExtension, paNorms, filteredWorks]);

  const stationByCode = useMemo(() => {
    const map = new Map();
    stations.forEach((station) => map.set(pretty(station.station_code), station));
    return map;
  }, [stations]);

  const matchesReportScope = (row) => {
    const code = pretty(row.station_code || row.scope_value);
    const station = stationByCode.get(code);
    const division = pretty(row.division || station?.division);
    const section = pretty(row.section || station?.section);
    const stationOk = sameFilterValue(code, reportFilters.station);
    const divisionOk = sameFilterValue(division, reportFilters.division);
    const sectionOk = sameFilterValue(section, reportFilters.section);
    return stationOk && divisionOk && sectionOk;
  };

  const matchesReportDate = (row, keys) => {
    const raw = keys.map((key) => row[key]).find(Boolean);
    if (!raw || (!reportFilters.month && !reportFilters.dateFrom && !reportFilters.dateTo)) return true;
    const day = compactDate(raw);
    if (!day) return true;
    if (reportFilters.month && monthKey(day) !== reportFilters.month) return false;
    if (reportFilters.dateFrom && day < reportFilters.dateFrom) return false;
    if (reportFilters.dateTo && day > reportFilters.dateTo) return false;
    return true;
  };

  const filteredReportStations = useMemo(() => {
    const q = search.reports;
    return stations.filter((row) => {
      const textOk = matchesQuery(row, ["station_code", "station_name", "division", "section", "categorisation", "platform_type"], q);
      return textOk && matchesReportScope(row);
    });
  }, [stations, search.reports, reportFilters, stationByCode]);

  const filteredReportUnits = useMemo(() => {
    const q = search.reports;
    return units.filter((row) => {
      const textOk = matchesQuery(row, ["unit_no", "station_code", "station_name", "licensee_name", "type_of_unit", "unit_status", "remarks", "station_category"], q);
      const actionOk = !reportFilters.needsActionOnly || !row.license_fee || !row.station_code || !/active/i.test(pretty(row.unit_status));
      return textOk && actionOk && matchesReportScope(row) && matchesReportDate(row, ["contract_to", "contract_from"]);
    });
  }, [units, search.reports, reportFilters, stationByCode]);

  const filteredReportEarnings = useMemo(() => {
    const q = search.reports;
    return earnings.filter((row) => {
      const textOk = matchesQuery(row, ["unit_no", "station_code", "licensee_name", "payment_head", "payment_sub_head", "receipt_type", "mr_no", "amount"], q);
      const actionOk = !reportFilters.needsActionOnly || /pending/i.test(pretty(row.receipt_type));
      return textOk && actionOk && matchesReportScope(row) && matchesReportDate(row, ["date_of_receipt", "mr_date", "period_to"]);
    });
  }, [earnings, search.reports, reportFilters, stationByCode]);

  const filteredReportWorks = useMemo(() => {
    const q = search.reports;
    return works.filter((row) => {
      const textOk = matchesQuery(row, ["project_id", "source_project_id", "source_sn", "short_name_of_work", "station_code", "section", "status", "scope_type", "scope_value", "allocation"], q);
      const actionOk = !reportFilters.needsActionOnly || !/complete|done/i.test(pretty(row.status));
      const sectionOk = reportWorkSection === "All" || workReportSection(row) === reportWorkSection;
      const typeOk = reportWorkType === "All" || workReportType(row) === reportWorkType;
      return textOk && actionOk && sectionOk && typeOk && matchesReportScope(row) && matchesReportDate(row, ["date_of_sanction"]);
    }).map((row, index) => ({
      ...row,
      sl_no: row.source_sn || index + 1,
      report_section: workReportSection(row),
      report_group: workReportType(row),
      deletion_recommended: workDeletionRecommended(row),
    }));
  }, [works, search.reports, reportFilters, stationByCode, reportWorkSection, reportWorkType]);

  const filteredReportCommercial = useMemo(() => {
    const q = search.reports;
    return commercialContracts.filter((row) => {
      const textOk = matchesQuery(row, ["contract_name", "licensee_name", "policy", "sub_category", "asset_scope", "station_code", "station_name", "station_match_status", "allocation_code"], q);
      const actionOk = !reportFilters.needsActionOnly || /unmatched|asset/i.test(pretty(row.station_match_status));
      return textOk && actionOk && matchesReportScope(row) && matchesReportDate(row, ["contract_upto", "contract_period_from"]);
    });
  }, [commercialContracts, search.reports, reportFilters, stationByCode]);

  const contractExpiryRows = useMemo(() => {
    const unique = new Map();
    const add = (row) => {
      const days = contractDaysRemaining(row.valid_to);
      if (days === null) return;
      if (!matchesReportScope(row)) return;
      if (!matchesQuery(row, ["contract_name", "licensee_name", "station_code", "station_name", "contract_type", "valid_to"], search.reports)) return;
      const existing = unique.get(row.key);
      if (!existing || days < existing.days_remaining) {
        unique.set(row.key, { ...row, days_remaining: days });
      }
    };
    units.filter((row) => !isAvailableUnit(row)).forEach((row) => add({
      ...row,
      key: `unit:${pretty(row.station_code)}:${pretty(row.unit_no)}`,
      source_type: "unit",
      contract_code: pretty(row.unit_no),
      contract_name: pretty(row.licensee_name) === "NA" ? pretty(row.unit_no) : pretty(row.licensee_name),
      contract_type: pretty(row.type_of_unit) === "NA" ? "Catering" : pretty(row.type_of_unit),
      valid_to: row.valid_to || row.contract_to,
    }));
    commercialContracts.forEach((row) => add({
      ...row,
      key: `commercial:${pretty(row.station_code)}:${pretty(row.contract_key || row.allocation_code || row.contract_name)}`,
      source_type: "commercial",
      contract_code: pretty(row.allocation_code || row.contract_key),
      contract_name: pretty(row.contract_name),
      contract_type: pretty(row.sub_category || row.policy),
      valid_to: row.valid_to || row.contract_upto,
    }));
    return [...unique.values()].sort((a, b) => a.days_remaining - b.days_remaining || pretty(a.contract_name).localeCompare(pretty(b.contract_name)));
  }, [units, commercialContracts, search.reports, reportFilters, stationByCode]);

  const visibleContractExpiryRows = useMemo(
    () => contractExpiryRows.filter((row) => contractExpiryWindow === 51 ? row.days_remaining > 50 : contractExpiryWindow === 0 ? row.days_remaining === 0 : row.days_remaining <= contractExpiryWindow),
    [contractExpiryRows, contractExpiryWindow],
  );
  const contractExpiryCount = (days) => contractExpiryRows.filter((row) => days === 51 ? row.days_remaining > 50 : days === 0 ? row.days_remaining === 0 : row.days_remaining <= days).length;

  const reportAlerts = reports?.license_fee_alerts?.rows || [];
  const filteredReportAlerts = useMemo(() => {
    const q = search.reports;
    return reportAlerts.filter((row) => matchesQuery(row, ["unit_no", "station_code", "station_name", "licensee_name", "type_of_unit", "unit_status", "alert_bucket"], q) && matchesReportScope(row) && matchesReportDate(row, ["contract_to", "last_paid_through"]));
  }, [reportAlerts, search.reports, reportFilters, stationByCode]);

  const reportActionRows = useMemo(() => {
    const serverActionRows = (actionCentre?.items || []).map((row) => {
      const source = row.source_module;
      const module = source === "catering" ? "units" : source === "amenities" ? "stations" : source;
      return {
        ...row,
        module,
        action_type: row.type,
        action_key: source === "commercial" ? row.title : row.record_id,
        problem: row.message,
      };
    });
    if (serverActionRows.length) return serverActionRows;
    const rows = [
      ...filteredReportAlerts.map((row) => ({ ...row, action_type: "License Fee Alert", module: "units", action_key: row.unit_no, problem: pretty(row.alert_bucket).replaceAll("_", " ") })),
      ...filteredReportUnits.filter((row) => !row.station_code || !row.license_fee).map((row) => ({ ...row, action_type: "Unit Data Issue", module: "units", action_key: row.unit_no, problem: !row.station_code ? "Missing station code" : "Missing license fee" })),
      ...filteredReportEarnings.filter((row) => /pending/i.test(pretty(row.receipt_type))).map((row) => ({ ...row, action_type: "Pending Receipt", module: "earnings", action_key: row.receipt_key || row.earning_key, problem: "Receipt pending" })),
      ...filteredReportWorks.filter((row) => !/complete|done/i.test(pretty(row.status))).map((row) => ({ ...row, action_type: "Open Work", module: "works", action_key: row.project_id, problem: pretty(row.status) })),
      ...filteredReportCommercial.filter((row) => /unmatched|asset/i.test(pretty(row.station_match_status))).map((row) => ({ ...row, action_type: "Commercial Link Review", module: "commercial", action_key: row.contract_name, problem: pretty(row.station_match_status) })),
      ...(contractAlerts?.rows || []).map((row) => ({ ...row, action_type: row.pending_amount ? "Contract Payment Risk" : "Contract Expiry", module: row.source_module || "contracts", action_key: row.contract_key || row.unit_no, problem: row.days_to_expiry == null ? "Validity date missing" : row.days_to_expiry < 0 ? "Expired" : `${row.days_to_expiry} days remaining` })),
      ...(reports?.inspections?.overdue_findings || []).map((row) => ({ ...row, action_type: "Overdue Inspection Finding", module: "inspections", action_key: row.finding_id, problem: `${row.days_overdue} days overdue` })),
      ...(dataCentre?.failures || []).map((row, index) => ({ ...row, action_type: "Sync Failure", module: "data-centre", action_key: `${row.resource}-${index}`, problem: row.message || "Source synchronization failed" })),
      ...(dataCentre?.recent_sync || []).filter((row) => /import|replace|sync/i.test(String(row.action || ""))).slice(0, 5).map((row, index) => ({ ...row, action_type: "Source Refresh", module: "data-centre", action_key: `${row.resource}-${row.at || index}`, problem: `${row.resource} refreshed from ${row.source || "source"}` })),
    ];
    return rows;
  }, [actionCentre, filteredReportAlerts, filteredReportUnits, filteredReportEarnings, filteredReportWorks, filteredReportCommercial, reports, commercialContractReports, contractAlerts, dataCentre]);

  const reportCards = [
    { icon: TrainFront, label: "Stations Covered", value: reports?.stations?.total ?? 0, subtext: `${reports?.stations?.with_units ?? 0} with units, ${reports?.stations?.with_works ?? 0} with works` },
    { icon: Users, label: "Active Units", value: reports?.units?.active ?? 0, subtext: "Units treated as active for fee reporting" },
    { icon: Wallet, label: "License Fee Collected", value: money(reports?.earnings?.license_fee_collected ?? 0), subtext: "All license fee receipts captured" },
    { icon: Database, label: "Commercial Annual Fee", value: money(commercialContractReports?.annual_license_fee ?? reports?.commercial_contracts?.annual_license_fee ?? 0), subtext: "Non-catering contract annual value" },
    { icon: Wrench, label: "Open Works", value: reports?.works?.pending ?? 0, subtext: "Works not marked complete/done" },
    { icon: CircleAlert, label: "Critical Alerts", value: (contractAlerts?.critical ?? 0) + (reports?.overview?.critical_alerts ?? 0), subtext: "Contract, payment, sync, and inspection risks" },
    { icon: TrendingUp, label: "Overdue Estimate", value: money(reports?.license_fee_alerts?.estimated_overdue_amount ?? 0), subtext: "Estimated from license fee and pending months" },
  ];

  const reportTabs = [
    { value: "overview", label: "Overview", icon: BarChart3 },
    { value: "contract-expiry", label: "Contract Expiry", icon: Timer },
    { value: "stations", label: "Stations", icon: TrainFront },
    { value: "units", label: "Units", icon: Users },
    { value: "earnings", label: "Earnings", icon: Wallet },
    { value: "commercial", label: "Commercial", icon: Database },
    { value: "works", label: "Works", icon: Wrench },
    { value: "inspections", label: "Inspections", icon: CircleAlert },
    { value: "actions", label: "Needs Action", icon: CircleAlert },
    { value: "quality", label: "Quality", icon: CircleAlert },
    { value: "alerts", label: "Alerts", icon: Timer },
  ];

  const dashboardCards = [
    { key: "stations", icon: TrainFront, label: "Stations", subtext: "Registered stations in the database" },
    { key: "units", icon: Users, label: "Contracts", subtext: "Catering stalls and vending contracts" },
    { key: "commercialContracts", icon: Database, label: "Commercial", subtext: "OOH, parking, ATM and mobile asset contracts" },
    { key: "works", icon: Wrench, label: "Works", subtext: "Sanctioned work records" },
    { key: "earningsTotal", icon: Wallet, label: "Contract Revenue", subtext: "Payments captured inside catering units", money: true },
    { key: "completedWorks", icon: BarChart3, label: "Completed Works", subtext: "Works with complete/done status" },
    { key: "pendingWorks", icon: CircleAlert, label: "Pending Works", subtext: "Open or unfinished work items" },
    { key: "openFindings", icon: CircleAlert, label: "Open Findings", subtext: "Inspection deficiencies needing action" },
    { key: "overdueFindings", icon: Timer, label: "Overdue Findings", subtext: "Inspection actions past target date" },
  ];

  const amenityCount = filteredAmenities[amenityTab]?.length || 0;
  const contractCount = filteredContracts[contractTab]?.length || 0;
  const aiRows = Array.isArray(aiResult?.rows) ? aiResult.rows : [];
  const activeWorkRows = filteredWorks[workTab] || [];
  const dashboardCount = view === "stations" ? filteredStations.length : view === "contracts" ? contractCount : view === "commercial" ? filteredCommercialContracts.length : view === "units" ? filteredUnits.length : view === "earnings" ? filteredEarnings.length : view === "works" ? activeWorkRows.length : view === "amenities" ? amenityCount : view === "reports" ? filteredReportAlerts.length : view === "ai" ? aiRows.length : stats?.stations ?? 0;
  const activeSearch = search[view] ?? "";
  const setActiveSearch = (value) => {
    setSearch((prev) => ({ ...prev, [view]: value }));
    if (visibleLimit[view]) {
      setVisibleLimit((prev) => ({ ...prev, [view]: 24 }));
    }
  };
  const currentLimit = visibleLimit[view] || 24;
  const stationColumns = [
    { key: "station_code", label: "Code", value: (row) => pretty(row.station_code), render: (row) => <span className="font-black text-blue">{pretty(row.station_code)}</span> },
    { key: "station_name", label: "Station", value: (row) => pretty(row.station_name), render: (row) => <span className="font-semibold text-ink">{pretty(row.station_name)}</span> },
    { key: "division", label: "Division" },
    { key: "section", label: "Section" },
    { key: "categorisation", label: "Category", value: (row) => pretty(row.categorisation), render: (row) => <Badge tone="accent">{pretty(row.categorisation)}</Badge> },
    { key: "platform_type", label: "Platform" },
    { key: "passenger_footfall", label: "Footfall" },
  ];
  const unitColumns = [
    { key: "unit_no", label: "Unit", value: (row) => pretty(row.unit_no), render: (row) => <span className="font-black text-blue">{pretty(row.unit_no)}</span> },
    { key: "licensee_name", label: "Licensee", value: (row) => isAvailableUnit(row) ? "Available unit" : pretty(row.licensee_name), render: (row) => <span className="font-semibold text-ink">{isAvailableUnit(row) ? "Available unit" : pretty(row.licensee_name)}</span> },
    { key: "station_code", label: "Station" },
    { key: "type_of_unit", label: "Type" },
    { key: "station_category", label: "Category" },
    { key: "license_fee", label: "Fee" },
    { key: "paid_upto", label: "Paid Upto" },
    { key: "contract_to", label: "Validity Risk", value: (row) => isAvailableUnit(row) ? "Not allotted" : contractRisk(row.valid_to || row.contract_to).label, render: (row) => { if (isAvailableUnit(row)) return <Badge tone="neutral">Not allotted</Badge>; const risk = contractRisk(row.valid_to || row.contract_to); return <Badge tone={risk.tone}>{risk.label}</Badge>; } },
    { key: "unit_status", label: "Status", value: (row) => isAvailableUnit(row) ? "Available" : pretty(row.unit_status), render: (row) => <Badge tone={isAvailableUnit(row) || /active/i.test(pretty(row.unit_status)) ? "accent" : "neutral"}>{isAvailableUnit(row) ? "Available" : pretty(row.unit_status)}</Badge> },
    { key: "remarks", label: "Remarks", value: (row) => pretty(row.remarks), render: (row) => <span className="text-sm text-muted">{pretty(row.remarks)}</span> },
  ];
  const earningColumns = [
    { key: "unit_no", label: "Unit", value: (row) => pretty(row.unit_no), render: (row) => <span className="font-black text-blue">{pretty(row.unit_no)}</span> },
    { key: "licensee_name", label: "Licensee", value: (row) => pretty(row.licensee_name), render: (row) => <span className="font-semibold text-ink">{pretty(row.licensee_name)}</span> },
    { key: "station_code", label: "Station" },
    { key: "date_of_receipt", label: "Receipt Date" },
    { key: "payment_head", label: "Head" },
    { key: "receipt_type", label: "Receipt", value: (row) => pretty(row.receipt_type), render: (row) => <Badge tone={/pending/i.test(pretty(row.receipt_type)) ? "danger" : "accent"}>{pretty(row.receipt_type)}</Badge> },
    { key: "amount", label: "Amount", value: (row) => row.amount || 0, render: (row) => <span className="font-semibold">{money(row.amount)}</span> },
  ];
  const workColumns = [
    { key: "source_sn", label: "SN" },
    { key: "source_project_id", label: "Project", value: (row) => pretty(row.source_project_id || row.project_id), render: (row) => <span className="font-black text-blue">{pretty(row.source_project_id || row.project_id)}</span> },
    { key: "short_name_of_work", label: "Work", value: (row) => pretty(row.short_name_of_work), render: (row) => <span className="line-clamp-2 font-medium text-ink">{pretty(row.short_name_of_work)}</span> },
    { key: "status", label: "Status", value: (row) => pretty(row.status), render: (row) => <Badge tone={/complete|done/i.test(pretty(row.status)) ? "accent" : "neutral"}>{pretty(row.status)}</Badge> },
    { key: "scope_type", label: "Scope" },
    { key: "station_code", label: "Station" },
    { key: "section", label: "Section" },
    { key: "cost", label: "Cost", value: (row) => row.cost || 0, render: (row) => <span className="font-semibold">{money(row.cost)}</span> },
    { key: "physical_progress", label: "Physical" },
  ];
  const reportWorkColumns = [
    { key: "sl_no", label: "Sl.no" },
    { key: "project_id", label: "PID", value: (row) => pretty(row.project_id || row.source_project_id), render: (row) => <span className="font-black text-blue">{pretty(row.project_id || row.source_project_id)}</span> },
    { key: "date_of_sanction", label: "Date of Sanction" },
    { key: "short_name_of_work", label: "Name of work", value: (row) => pretty(row.short_name_of_work), render: (row) => <div className="space-y-1"><span className="line-clamp-2 font-medium text-ink">{pretty(row.short_name_of_work)}</span>{row.deletion_recommended ? <Badge tone="danger">Deletion recommended</Badge> : null}</div> },
    { key: "cost", label: "Cost", value: (row) => row.cost || 0, render: (row) => <span className="font-semibold">{money(row.cost)}</span> },
    { key: "remarks", label: "Remarks", render: (row) => <div className="max-w-md line-clamp-3">{pretty(row.remarks)}</div> },
  ];
  const commercialContractColumns = [
    { key: "contract_name", label: "Contract", value: (row) => pretty(row.contract_name), render: (row) => <span className="font-black text-blue">{pretty(row.contract_name)}</span> },
    { key: "licensee_name", label: "Licensee", value: (row) => pretty(row.licensee_name), render: (row) => <span className="font-semibold text-ink">{pretty(row.licensee_name)}</span> },
    { key: "allocation_code", label: "Allocation" },
    { key: "policy", label: "Policy", value: (row) => pretty(row.policy), render: (row) => <Badge tone="accent">{pretty(row.policy)}</Badge> },
    { key: "sub_category", label: "Sub Category" },
    { key: "asset_scope", label: "Scope" },
    { key: "station_code", label: "Station" },
    { key: "annual_license_fee", label: "Annual Fee", value: (row) => row.annual_license_fee || 0, render: (row) => <span className="font-semibold">{money(row.annual_license_fee)}</span> },
    { key: "contract_upto", label: "Upto" },
    { key: "validity_risk", label: "Validity Risk", value: (row) => contractRisk(row.valid_to || row.contract_upto).label, render: (row) => { const risk = contractRisk(row.valid_to || row.contract_upto); return <Badge tone={risk.tone}>{risk.label}</Badge>; } },
    { key: "station_match_status", label: "Link", value: (row) => pretty(row.station_match_status), render: (row) => <Badge tone={/unmatched|asset/i.test(pretty(row.station_match_status)) ? "danger" : "accent"}>{pretty(row.station_match_status)}</Badge> },
  ];
  const commercialPaymentColumns = [
    { key: "payment_month", label: "Month", value: (row) => pretty(row.payment_month), render: (row) => <span className="font-black text-blue">{pretty(row.payment_month)}</span> },
    { key: "amount_due", label: "Due", value: (row) => row.amount_due || 0, render: (row) => <span className="font-semibold">{money(row.amount_due)}</span> },
    { key: "amount_paid", label: "Paid", value: (row) => row.amount_paid || 0, render: (row) => <span className="font-semibold">{money(row.amount_paid)}</span> },
    { key: "payment_status", label: "Status", value: (row) => pretty(row.payment_status), render: (row) => <Badge tone="accent">{pretty(row.payment_status)}</Badge> },
    { key: "source_column", label: "Source Column" },
  ];
  const amenitySummaryColumns = [
    { key: "station_code", label: "Station", value: (row) => pretty(row.station_code), render: (row) => <span className="font-black text-blue">{pretty(row.station_code)}</span> },
    { key: "station_name", label: "Name" },
    { key: "category", label: "Category", value: (row) => pretty(row.category), render: (row) => <Badge tone="accent">{pretty(row.category)}</Badge> },
    { key: "platform_count", label: "PFs" },
    { key: "platform_detail_count", label: "PF Rows" },
    { key: "wheel_chairs", label: "Wheel Chairs" },
    { key: "trolley_path", label: "Trolley Path" },
    { key: "pa_works", label: "PA Works" },
  ];
  const infraColumns = [
    { key: "station_code", label: "Station", value: (row) => pretty(row.station_code), render: (row) => <span className="font-black text-blue">{pretty(row.station_code)}</span> },
    { key: "station_name", label: "Name" },
    { key: "category", label: "Category" },
    { key: "platform_list", label: "Platforms" },
    { key: "platform_count", label: "Count" },
    { key: "platform_level", label: "Level" },
    { key: "fob_details", label: "FOB / Access" },
  ];
  const platformColumns = [
    { key: "station_code", label: "Station", value: (row) => pretty(row.station_code), render: (row) => <span className="font-black text-blue">{pretty(row.station_code)}</span> },
    { key: "station_name", label: "Name" },
    { key: "platform", label: "Platform" },
    { key: "length_m", label: "Length" },
    { key: "lifts", label: "Lifts" },
    { key: "escalators", label: "Escalators" },
    { key: "ramp", label: "Ramp" },
  ];
  const wheelchairColumns = [
    { key: "station_code", label: "Station", value: (row) => pretty(row.station_code), render: (row) => <span className="font-black text-blue">{pretty(row.station_code)}</span> },
    { key: "station_name", label: "Name" },
    { key: "division", label: "Division" },
    { key: "section", label: "Section" },
    { key: "category", label: "Category" },
    { key: "available_good_condition", label: "Good Condition" },
  ];
  const trolleyColumns = [
    { key: "station_code", label: "Station", value: (row) => pretty(row.station_code), render: (row) => <span className="font-black text-blue">{pretty(row.station_code)}</span> },
    { key: "station_name", label: "Name" },
    { key: "section", label: "Section" },
    { key: "categorisation", label: "Category" },
    { key: "passenger_footfall", label: "Footfall" },
    { key: "platforms", label: "Platforms" },
    { key: "platform_type", label: "Level" },
    { key: "trolley_path", label: "Trolley Path" },
  ];
  const paWorkColumns = [
    { key: "work_type", label: "Type", value: (row) => pretty(row.work_type), render: (row) => <Badge tone="accent">{pretty(row.work_type)}</Badge> },
    { key: "station_code", label: "Station", value: (row) => pretty(row.station_code), render: (row) => <span className="font-black text-blue">{pretty(row.station_code)}</span> },
    { key: "station_name", label: "Name" },
    { key: "work_name", label: "Work" },
    { key: "tender_status", label: "Tender" },
    { key: "progress", label: "Progress" },
    { key: "tdc", label: "TDC" },
  ];
  const pfExtensionColumns = [
    { key: "station_code", label: "Station", value: (row) => pretty(row.station_code), render: (row) => <span className="font-black text-blue">{pretty(row.station_code)}</span> },
    { key: "station_name", label: "Name" },
    { key: "category", label: "Category", value: (row) => pretty(row.category || row.categorisation), render: (row) => <Badge tone="accent">{pretty(row.category || row.categorisation)}</Badge> },
    { key: "pf_extension_wip", label: "PF WIP", value: (row) => row.pf_extension_wip ? "Yes" : "No", render: (row) => <Badge tone={row.pf_extension_wip ? "accent" : "neutral"}>{row.pf_extension_wip ? "Yes" : "No"}</Badge> },
    { key: "pf_extension_proposed", label: "PF Proposed", value: (row) => row.pf_extension_proposed ? "Yes" : "No", render: (row) => <Badge tone={row.pf_extension_proposed ? "accent" : "neutral"}>{row.pf_extension_proposed ? "Yes" : "No"}</Badge> },
    { key: "raising_extension_proposed", label: "Raising", value: (row) => row.raising_extension_proposed ? "Yes" : "No", render: (row) => <Badge tone={row.raising_extension_proposed ? "accent" : "neutral"}>{row.raising_extension_proposed ? "Yes" : "No"}</Badge> },
    { key: "ramp_feasible", label: "Ramp Feasible", value: (row) => row.ramp_feasible ? "Yes" : "No", render: (row) => <Badge tone={row.ramp_feasible ? "accent" : "neutral"}>{row.ramp_feasible ? "Yes" : "No"}</Badge> },
    { key: "lift_proposed", label: "Lift Proposed", value: (row) => row.lift_proposed ? "Yes" : "No", render: (row) => <Badge tone={row.lift_proposed ? "accent" : "neutral"}>{row.lift_proposed ? "Yes" : "No"}</Badge> },
    { key: "ramp_proposed", label: "Ramp Proposed", value: (row) => row.ramp_proposed ? "Yes" : "No", render: (row) => <Badge tone={row.ramp_proposed ? "accent" : "neutral"}>{row.ramp_proposed ? "Yes" : "No"}</Badge> },
    { key: "status_text", label: "Source Detail" },
  ];
  const normColumns = [
    { key: "category", label: "Category", value: (row) => pretty(row.category), render: (row) => <Badge tone="accent">{pretty(row.category)}</Badge> },
    { key: "amenity", label: "Amenity" },
    { key: "norm", label: "Norm" },
    { key: "norm_quantity", label: "Quantity" },
  ];
  const amenityTabs = [
    { value: "summary", label: "Station View", icon: TrainFront },
    { value: "infra", label: "Infra", icon: Database },
    { value: "platforms", label: "Platforms", icon: BarChart3 },
    { value: "wheelchairs", label: "Wheel Chairs", icon: Users },
    { value: "trolley", label: "Trolley Path", icon: Wrench },
    { value: "paWorks", label: "PA Works", icon: Wrench },
    { value: "pfExtension", label: "PF Extn/Raising", icon: BarChart3 },
    { value: "sanctionedWorks", label: "Sanctioned Works", icon: FileText },
    { value: "norms", label: "Norms", icon: CircleAlert },
  ];
  const contractTabs = [
    { value: "units", label: "Catering Units", icon: Users },
    { value: "earnings", label: "Payments", icon: Wallet },
  ];
  const activeContract = contractTab === "earnings"
    ? { rows: filteredContracts.earnings, columns: earningColumns, fileName: "contract-payments.csv" }
    : { rows: filteredContracts.units, columns: unitColumns, fileName: "catering-contracts.csv" };
  const activeAmenity = (() => {
    if (amenityTab === "infra") return { rows: filteredAmenities.infra, columns: infraColumns, fileName: "pa-infra.csv" };
    if (amenityTab === "platforms") return { rows: filteredAmenities.platforms, columns: platformColumns, fileName: "pa-platforms.csv" };
    if (amenityTab === "wheelchairs") return { rows: filteredAmenities.wheelchairs, columns: wheelchairColumns, fileName: "pa-wheelchairs.csv" };
    if (amenityTab === "trolley") return { rows: filteredAmenities.trolley, columns: trolleyColumns, fileName: "pa-trolley-path.csv" };
    if (amenityTab === "paWorks") return { rows: filteredAmenities.paWorks, columns: paWorkColumns, fileName: "pa-works.csv" };
    if (amenityTab === "pfExtension") return { rows: filteredAmenities.pfExtension, columns: pfExtensionColumns, fileName: "pf-extension-raising.csv" };
    if (amenityTab === "sanctionedWorks") return { rows: filteredAmenities.sanctionedWorks, columns: workColumns, fileName: "sanctioned-works.csv" };
    if (amenityTab === "norms") return { rows: filteredAmenities.norms, columns: normColumns, fileName: "pa-norms.csv" };
    return { rows: filteredAmenities.summary, columns: amenitySummaryColumns, fileName: "pa-station-summary.csv" };
  })();
  const alertColumns = [
    { key: "alert_bucket", label: "Alert", value: (row) => pretty(row.alert_bucket), render: (row) => <Badge tone={row.alert_bucket === "overdue" ? "danger" : "accent"}>{pretty(row.alert_bucket).replaceAll("_", " ")}</Badge> },
    { key: "unit_no", label: "Unit", value: (row) => pretty(row.unit_no), render: (row) => <span className="font-black text-blue">{pretty(row.unit_no)}</span> },
    { key: "licensee_name", label: "Licensee" },
    { key: "station_code", label: "Station" },
    { key: "last_paid_through", label: "Paid Through" },
    { key: "contract_to", label: "Contract To" },
    { key: "estimated_pending_amount", label: "Pending", value: (row) => row.estimated_pending_amount || 0, render: (row) => <span className="font-semibold">{money(row.estimated_pending_amount)}</span> },
  ];
  const actionColumns = [
    { key: "action_type", label: "Action Type", value: (row) => pretty(row.action_type), render: (row) => <Badge tone="danger">{pretty(row.action_type)}</Badge> },
    { key: "problem", label: "Problem" },
    { key: "action_key", label: "Record", value: (row) => pretty(row.action_key), render: (row) => <span className="font-black text-blue">{pretty(row.action_key)}</span> },
    { key: "unit_no", label: "Unit" },
    { key: "station_code", label: "Station" },
    { key: "licensee_name", label: "Licensee" },
    { key: "amount", label: "Amount", value: (row) => row.amount || row.estimated_pending_amount || 0, render: (row) => <span className="font-semibold">{money(row.amount || row.estimated_pending_amount)}</span> },
  ];
  const qualityColumns = [
    { key: "module", label: "Module", value: (row) => pretty(row.module), render: (row) => <Badge>{pretty(row.module)}</Badge> },
    { key: "record", label: "Record", value: (row) => pretty(row.record), render: (row) => <span className="font-black text-blue">{pretty(row.record)}</span> },
    { key: "problem", label: "Problem" },
    { key: "station_code", label: "Station" },
  ];

  const qualityRows = [
    ...filteredReportUnits.filter((row) => !row.station_code).map((row) => ({ module: "Units", record: row.unit_no, problem: "Missing station code", station_code: row.station_code })),
    ...filteredReportUnits.filter((row) => !row.license_fee).map((row) => ({ module: "Units", record: row.unit_no, problem: "Missing license fee", station_code: row.station_code })),
    ...filteredReportEarnings.filter((row) => !row.unit_no).map((row) => ({ module: "Earnings", record: row.receipt_key || row.earning_key, problem: "Missing unit number", station_code: row.station_code })),
    ...filteredReportEarnings.filter((row) => !row.station_code).map((row) => ({ module: "Earnings", record: row.receipt_key || row.earning_key, problem: "Missing station code", station_code: row.station_code })),
    ...filteredReportWorks.filter((row) => row.scope_type === "Station" && !row.station_code).map((row) => ({ module: "Works", record: row.project_id, problem: "Station scope without station code", station_code: row.station_code })),
    ...filteredCommercialContracts.filter((row) => /unmatched|asset/i.test(pretty(row.station_match_status))).map((row) => ({ module: "Commercial", record: row.contract_name, problem: `Station link: ${pretty(row.station_match_status)}`, station_code: row.station_code })),
  ];

  const contractExpiryColumns = [
    { key: "contract_code", label: "Code" },
    { key: "contract_name", label: "Contract" },
    { key: "contract_type", label: "Type" },
    { key: "station_code", label: "Station" },
    { key: "valid_to", label: "Valid Till" },
    { key: "days_remaining", label: "Days Remaining" },
  ];

  const activeReport = (() => {
    if (reportTab === "contract-expiry") return { rows: visibleContractExpiryRows, columns: contractExpiryColumns, fileName: contractExpiryWindow === 51 ? "contract-validity-50-plus-days.xls" : `contract-expiry-${contractExpiryWindow}-days.xls` };
    if (reportTab === "stations") return { rows: filteredReportStations, columns: stationColumns, fileName: "station-report.xls" };
    if (reportTab === "units") return { rows: filteredReportUnits, columns: unitColumns, fileName: "unit-report.xls" };
    if (reportTab === "earnings") return { rows: filteredReportEarnings, columns: earningColumns, fileName: "earnings-report.xls" };
    if (reportTab === "commercial") return { rows: filteredReportCommercial, columns: commercialContractColumns, fileName: "commercial-contracts-report.xls" };
    if (reportTab === "works") return { rows: filteredReportWorks, columns: reportWorkColumns, fileName: "works-report.xls" };
    if (reportTab === "actions") return { rows: reportActionRows, columns: actionColumns, fileName: "needs-action-report.xls" };
    if (reportTab === "quality") return { rows: qualityRows, columns: qualityColumns, fileName: "quality-report.xls" };
    if (reportTab === "alerts") return { rows: filteredReportAlerts, columns: alertColumns, fileName: "license-fee-alerts.xls" };
    return { rows: reportActionRows, columns: actionColumns, fileName: "report-overview.xls" };
  })();

  const aiColumns = useMemo(() => {
    const keys = Array.from(new Set(aiRows.flatMap((row) => Object.keys(row || {})))).filter((key) => !["source_hash", "created_at", "updated_at", "first_seen_at", "last_seen_at", "is_active"].includes(key));
    const visibleKeys = keys.length ? keys.slice(0, 10) : ["answer"];
    return visibleKeys.map((key) => ({
      key,
      label: key.replaceAll("_", " "),
      value: (row) => pretty(row[key]),
      render: key === "station_code"
        ? (row) => <span className="font-black text-blue">{pretty(row[key])}</span>
        : undefined,
    }));
  }, [aiRows]);

  const openAiRow = (row) => {
    if (row?.station_code) {
      const station = stations.find((item) => pretty(item.station_code) === pretty(row.station_code)) || {
        station_code: row.station_code,
        station_name: row.station_name,
        division: row.division,
        section: row.section,
        categorisation: row.category || row.categorisation,
      };
      return openStation(station);
    }
    if (row?.unit_no) {
      const unit = units.find((item) => pretty(item.unit_no) === pretty(row.unit_no));
      if (unit) return openUnit(unit);
    }
    if (row?.project_id) {
      const work = works.find((item) => pretty(item.project_id) === pretty(row.project_id));
      if (work) return openWork(work);
    }
    return null;
  };

  const viewConfig = (() => {
    if (view === "stations") {
      return {
        title: "Stations",
        subtitle: "Search by station code, name, division, section, category, and platform.",
        filters: [
          ["Category", filters.stationCategory, (value) => setFilters((prev) => ({ ...prev, stationCategory: value })), ["All", ...new Set(stations.map((r) => r.categorisation).filter(Boolean).sort())]],
          ["Division", filters.stationDivision, (value) => setFilters((prev) => ({ ...prev, stationDivision: value })), ["All", ...new Set(stations.map((r) => r.division).filter(Boolean).sort())]],
          ["Section", filters.stationSection, (value) => setFilters((prev) => ({ ...prev, stationSection: value })), ["All", ...new Set(stations.map((r) => r.section).filter(Boolean).sort())]],
          ["Platform", filters.stationPlatform, (value) => setFilters((prev) => ({ ...prev, stationPlatform: value })), ["All", ...new Set(stations.map((r) => r.platform_type).filter(Boolean).sort())]],
        ],
      };
    }
    if (view === "units") {
      return {
        title: "Units",
        subtitle: "Linked catering units with station code, category, type, and status.",
        filters: [
          ["Category", filters.unitCategory, (value) => setFilters((prev) => ({ ...prev, unitCategory: value })), ["All", ...new Set(units.map((r) => r.station_category).filter(Boolean).sort())]],
          ["Type", filters.unitType, (value) => setFilters((prev) => ({ ...prev, unitType: value })), ["All", ...new Set(units.map((r) => r.type_of_unit).filter(Boolean).sort())]],
          ["Status", filters.unitStatus, (value) => setFilters((prev) => ({ ...prev, unitStatus: value })), ["All", ...new Set(units.map((r) => r.unit_status).filter(Boolean).sort())]],
        ],
      };
    }
    if (view === "earnings") {
      return { title: "Earnings", subtitle: "Unit-wise receipt records linked back to station and licensee context.", filters: [] };
    }
    if (view === "contracts") {
      return {
        title: "Contracts",
        subtitle: "Catering contracts with licensee, contract period, license fee, and payment history inside units.",
        filters: [],
      };
    }
    if (view === "commercial") {
      return {
        title: "Commercial Contracts",
        subtitle: "OOH, parking, ATM/banking, mobile assets, pay-and-use, and other non-catering commercial contracts.",
        filters: [
          ["Station", filters.commercialStation, (value) => setFilters((prev) => ({ ...prev, commercialStation: value })), ["All", ...new Set(commercialContracts.map((r) => r.station_code).filter(Boolean).sort())]],
          ["Allocation", filters.commercialAllocation, (value) => setFilters((prev) => ({ ...prev, commercialAllocation: value })), ["All", ...new Set(commercialContracts.map((r) => r.allocation_code).filter(Boolean).sort())]],
          ["Policy", filters.commercialPolicy, (value) => setFilters((prev) => ({ ...prev, commercialPolicy: value })), ["All", ...new Set(commercialContracts.map((r) => r.policy).filter(Boolean).sort())]],
          ["Sub Category", filters.commercialSubCategory, (value) => setFilters((prev) => ({ ...prev, commercialSubCategory: value })), ["All", ...new Set(commercialContracts.map((r) => r.sub_category).filter(Boolean).sort())]],
          ["Asset Scope", filters.commercialAssetScope, (value) => setFilters((prev) => ({ ...prev, commercialAssetScope: value })), ["All", ...new Set(commercialContracts.map((r) => r.asset_scope).filter(Boolean).sort())]],
        ],
      };
    }
    if (view === "works") {
      return {
        title: "Sanctioned Works",
        subtitle: "Passenger amenity sanctioned works with station, division, and ABSS scope handling.",
        filters: [
          ["Station", filters.workStation, (value) => {
            setWorkTab("station");
            setFilters((prev) => ({ ...prev, workStation: value }));
          }, ["All", ...new Set(works.map((r) => r.station_code).filter(Boolean).sort())]],
          ["Status", filters.workStatus, (value) => setFilters((prev) => ({ ...prev, workStatus: value })), ["All", ...new Set(works.map((r) => r.status).filter(Boolean).sort())]],
        ],
      };
    }
    if (view === "amenities") {
      return {
        title: "Passenger Amenities",
        subtitle: "Station-linked norms, infra, platform, wheel chair, trolley path, and PA work data.",
        filters: [],
      };
    }
    if (view === "reports") {
      return {
        title: "Reports",
        subtitle: "Operational reports for units, earnings, and license fee alerts.",
        filters: [],
      };
    }
    if (view === "ai") {
      return {
        title: "Ask AI",
        subtitle: "Ask natural-language questions across stations, contracts, earnings, works, and passenger amenities.",
        filters: [],
      };
    }
    if (view === "settings") {
      return {
        title: "Settings",
        subtitle: "Manage validated fetch, sync, import, and database refresh operations for the dashboard.",
        filters: [],
      };
    }
    return { title: "Dashboard", subtitle: "KPI cards and high-level trends across the dataset.", filters: [] };
  })();

  const buildLocalStationDetail = (station) => {
    const code = station.station_code;
    const stationUnits = units.filter((row) => pretty(row.station_code) === pretty(code));
    const stationEarnings = earnings.filter((row) => pretty(row.station_code) === pretty(code));
    const stationCommercialContracts = commercialContracts.filter((row) => pretty(row.station_code) === pretty(code));
    const stationPaWorks = paWorks.filter((row) => pretty(row.station_code) === pretty(code));
    const pfExtensionStatus = paPfExtension.find((row) => pretty(row.station_code) === pretty(code));
    const platformRows = paPlatforms.filter((row) => pretty(row.station_code) === pretty(code));
    const platformLengths = platformRows.map((row) => Number(row.length_m || 0)).filter(Boolean);
    return {
      station,
      contracts: stationUnits.map((unit) => {
        const unitEarnings = isAvailableUnit(unit) ? [] : earnings.filter((row) => pretty(row.unit_no) === pretty(unit.unit_no));
        return { ...unit, earnings: unitEarnings, earnings_total: unitEarnings.reduce((sum, row) => sum + Number(row.amount || 0), 0), pending_receipts: unitEarnings.filter((row) => /pending/i.test(pretty(row.receipt_type))).length };
      }),
      units: stationUnits,
      earnings: stationEarnings,
      works: works.filter((row) => pretty(row.station_code) === pretty(code) || pretty(row.scope_value) === pretty(code)),
      commercial_contracts: stationCommercialContracts,
      amenities: {
        summary: paSummary.find((row) => pretty(row.station_code) === pretty(code)),
        infra: paInfra.find((row) => pretty(row.station_code) === pretty(code)),
        platforms: platformRows,
        wheelchairs: paWheelchairs.find((row) => pretty(row.station_code) === pretty(code)),
        trolley: paTrolley.find((row) => pretty(row.station_code) === pretty(code)),
        pf_extension_status: pfExtensionStatus,
        pa_works: stationPaWorks,
        norms: paNorms.filter((row) => pretty(row.category) === pretty(station.categorisation)),
      },
      amenity_summary: {
        platforms: platformRows.length,
        total_platform_length: platformLengths.reduce((sum, value) => sum + value, 0),
        shortest_platform: platformLengths.length ? Math.min(...platformLengths) : null,
        longest_platform: platformLengths.length ? Math.max(...platformLengths) : null,
        wheel_chairs: paWheelchairs.find((row) => pretty(row.station_code) === pretty(code))?.available_good_condition,
        trolley_path: paTrolley.find((row) => pretty(row.station_code) === pretty(code))?.trolley_path,
        fob_details: paInfra.find((row) => pretty(row.station_code) === pretty(code))?.fob_details,
        pa_works: stationPaWorks.length,
        open_pa_works: stationPaWorks.filter((row) => !/complete/i.test(pretty(row.progress))).length,
        pf_extension_wip: Boolean(pfExtensionStatus?.pf_extension_wip),
        pf_extension_proposed: Boolean(pfExtensionStatus?.pf_extension_proposed),
        raising_extension_proposed: Boolean(pfExtensionStatus?.raising_extension_proposed),
        platform_extension_work_proposed: Boolean(pfExtensionStatus?.platform_extension_work_proposed),
        ramp_feasible: Boolean(pfExtensionStatus?.ramp_feasible),
        lift_proposed: Boolean(pfExtensionStatus?.lift_proposed),
        ramp_proposed: Boolean(pfExtensionStatus?.ramp_proposed),
        not_feasible_lift_ramp: Boolean(pfExtensionStatus?.not_feasible_lift_ramp),
      },
    };
  };

  const openStation = async (station, tab = "overview") => {
    setStationModalTab(tab);
    const fallback = buildLocalStationDetail(station);
    setModal({ open: true, type: "station", record: fallback });
    try {
      const detail = await fetchJson(stationDetailUrl(station.station_code));
      setModal({ open: true, type: "station", record: detail });
    } catch {
      setActivityStatus("Using local station detail view");
    }
  };

  const createStationAmenityFindings = async (record) => {
    const station = record?.station;
    const inspections = record?.action_centre?.inspections || [];
    const inspection = inspections.find((row) => ["draft", "in_progress", "returned"].includes(row.status)) || inspections[0];
    if (!station?.station_code || !inspection?.inspection_id) {
      setActivityStatus("Create or open an inspection for this station before creating amenity findings.");
      return;
    }
    try {
      const result = await fetchJson(amenityFindingsUrl(station.station_code), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inspection_id: inspection.inspection_id }),
      });
      setActivityStatus(`${result.total_created || 0} amenity findings created; ${result.skipped?.length || 0} already open`);
      const refreshed = await fetchJson(stationDetailUrl(station.station_code));
      setModal((current) => current.open && current.type === "station" ? { ...current, record: refreshed } : current);
    } catch (error) {
      setActivityStatus(error?.message || "Unable to create amenity findings");
    }
  };

  const openStationSheet = async (station) => {
    const fallback = buildLocalStationDetail(station);
    setStationSheet({ open: true, record: fallback, loading: true });
    try {
      const detail = await fetchJson(stationDetailUrl(station.station_code));
      setStationSheet((current) => current.open
        ? { open: true, record: detail, loading: false }
        : current);
    } catch {
      setStationSheet((current) => current.open
        ? { ...current, loading: false }
        : current);
      setActivityStatus("Using local station snapshot");
    }
  };

  const openStationDetailFromSheet = (tab = "overview") => {
    if (!stationSheet.record) return;
    setStationModalTab(tab);
    setModal({ open: true, type: "station", record: stationSheet.record });
    setStationSheet({ open: false, record: null, loading: false });
  };

  const openUnit = (unit) => {
    const no = unit.unit_no;
    const unitEarnings = isAvailableUnit(unit) ? [] : earnings.filter((row) => pretty(row.unit_no) === pretty(no));
    const latestReceipt = [...unitEarnings].sort((left, right) => pretty(right.date_of_receipt).localeCompare(pretty(left.date_of_receipt)))[0];
    setModal({
      open: true,
      type: "unit",
      record: {
        unit,
        earnings: unitEarnings,
        earningsTotal: unitEarnings.reduce((sum, row) => sum + Number(row.amount || 0), 0),
        latestReceipt,
      },
    });
  };

  const openEarning = (earning) => {
    setModal({ open: true, type: "earning", record: { earning } });
  };

  const openWork = async (work) => {
    setProgressDraft({ update_date: new Date().toISOString().slice(0, 10), progress_percent: "", expenditure_upto_date: "", status: "", remarks: "" });
    setModal({ open: true, type: "work", record: { work, progress_updates: [], expenditure_updates: [] } });
    try {
      const [progress, expenditure] = await Promise.all([
        fetchJson(workProgressUrl(work.project_id)),
        fetchJson(workExpenditureUrl(work.project_id)),
      ]);
      setModal((current) => current.open && current.type === "work" ? { ...current, record: { ...current.record, progress_updates: progress.items || [], expenditure_updates: expenditure.items || [] } } : current);
    } catch (error) {
      setActivityStatus(error?.message || "Progress history unavailable");
    }
  };

  const saveWorkProgress = async () => {
    const work = modal.record?.work;
    if (!work?.project_id || !progressDraft.update_date) return;
    setSaving(true);
    try {
      await fetchJson(workProgressUrl(work.project_id), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...progressDraft,
          progress_percent: progressDraft.progress_percent === "" ? null : Number(progressDraft.progress_percent),
          expenditure_upto_date: progressDraft.expenditure_upto_date === "" ? null : Number(progressDraft.expenditure_upto_date),
        }),
      });
      if (progressDraft.expenditure_upto_date !== "") {
        await fetchJson(workExpenditureUrl(work.project_id), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            update_date: progressDraft.update_date,
            cumulative_expenditure: Number(progressDraft.expenditure_upto_date),
            source: "progress_entry",
          }),
        });
      }
      const [progress, expenditure] = await Promise.all([
        fetchJson(workProgressUrl(work.project_id)),
        fetchJson(workExpenditureUrl(work.project_id)),
      ]);
      setModal((current) => ({ ...current, record: { ...current.record, progress_updates: progress.items || [], expenditure_updates: expenditure.items || [] } }));
      setProgressDraft((current) => ({ ...current, progress_percent: "", expenditure_upto_date: "", status: "", remarks: "" }));
      await loadData();
      setActivityStatus("Work progress history saved");
    } catch (error) {
      setActivityStatus(error?.message || "Unable to save work progress");
    } finally {
      setSaving(false);
    }
  };

  const uploadWorkProgressPhoto = async (update, file) => {
    const work = modal.record?.work;
    if (!work?.project_id || !update?.progress_id || !file) return;
    setSaving(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("caption", file.name);
      await fetchJson(`${workProgressUrl(work.project_id)}/${update.progress_id}/photos`, { method: "POST", body: form });
      const progress = await fetchJson(workProgressUrl(work.project_id));
      setModal((current) => ({ ...current, record: { ...current.record, progress_updates: progress.items || [] } }));
      setActivityStatus("Progress photo saved");
    } catch (error) {
      setActivityStatus(error?.message || "Unable to save progress photo");
    } finally {
      setSaving(false);
    }
  };

  const openCommercialContract = async (contract) => {
    setModal({ open: true, type: "commercial", record: { contract, station_links: [], payments: [] } });
    try {
      const detail = await fetchJson(commercialContractDetailUrl(contract.contract_key));
      setModal({ open: true, type: "commercial", record: detail });
    } catch (error) {
      setActivityStatus(error?.message || "Using local commercial contract detail");
    }
  };

  const openAmenity = (amenity) => {
    setModal({ open: true, type: "amenity", record: { amenity, tab: amenityTab } });
  };

  const openStationFromAmenity = (row, tab = "amenities") => {
    const station = stations.find((item) => pretty(item.station_code) === pretty(row.station_code)) || {
      station_code: row.station_code,
      station_name: row.station_name,
      division: row.division,
      section: row.section,
      categorisation: row.category || row.categorisation,
    };
    if (station.station_code && pretty(station.station_code) !== "NA") {
      openStation(station, tab);
    } else {
      openAmenity(row);
    }
  };

  const closeModal = () => setModal({ open: false, type: null, record: null });

  const openReportRecord = (row) => {
    if (reportTab === "stations") return openStation(row);
    if (reportTab === "units" || reportTab === "alerts") {
      const unit = units.find((item) => pretty(item.unit_no) === pretty(row.unit_no || row.action_key));
      if (unit) return openUnit(unit);
    }
    if (reportTab === "earnings") return openEarning(row);
    if (reportTab === "commercial") return openCommercialContract(row);
    if (reportTab === "works") return openWork(row);
    if (reportTab === "actions") return openActionRecord(row);
    return null;
  };

  const openActionRecord = (row) => {
    if (row.module === "units") {
      const unit = units.find((item) => pretty(item.unit_no) === pretty(row.unit_no || row.action_key));
      if (unit) return openUnit(unit);
    }
    if (row.module === "earnings") {
      const earning = earnings.find((item) => pretty(item.receipt_key || item.earning_key) === pretty(row.action_key));
      if (earning) return openEarning(earning);
    }
    if (row.module === "works") {
      const work = works.find((item) => pretty(item.project_id) === pretty(row.action_key));
      if (work) return openWork(work);
    }
    if (row.module === "commercial") {
      const contract = commercialContracts.find((item) => pretty(item.contract_name) === pretty(row.action_key));
      if (contract) return openCommercialContract(contract);
    }
    if (row.module === "inspections") {
      const station = stations.find((item) => pretty(item.station_code) === pretty(row.station_code));
      if (station) return openStation(station, "alerts");
    }
    if (row.module === "stations") {
      const station = stations.find((item) => pretty(item.station_code) === pretty(row.station_code || row.action_key));
      if (station) return openStation(station, "alerts");
    }
    if (row.module === "data-centre") {
      setView("dashboard");
      setActivityStatus(row.problem || "Review Data Centre");
    }
    return null;
  };

  const reportValue = (column, row) => {
    const value = column.value ? column.value(row) : row[column.key];
    return value === null || value === undefined ? "" : value;
  };

  const exportReportExcel = () => {
    const header = activeReport.columns.map((column) => `<th>${htmlEscape(column.label)}</th>`).join("");
    const body = activeReport.rows.map((row) => `<tr>${activeReport.columns.map((column) => `<td>${htmlEscape(reportValue(column, row))}</td>`).join("")}</tr>`).join("");
    const html = `<html><head><meta charset="utf-8" /></head><body><table border="1"><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table></body></html>`;
    const blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = activeReport.fileName;
    link.click();
    URL.revokeObjectURL(url);
  };

  const exportReportPdf = () => {
    const header = activeReport.columns.map((column) => `<th>${htmlEscape(column.label)}</th>`).join("");
    const body = activeReport.rows.map((row) => `<tr>${activeReport.columns.map((column) => `<td>${htmlEscape(reportValue(column, row))}</td>`).join("")}</tr>`).join("");
    const doc = window.open("", "_blank");
    if (!doc) return;
    doc.document.write(`
      <html>
        <head>
          <title>${htmlEscape(viewConfig.title)} Report</title>
          <style>
            body{font-family:Arial,sans-serif;padding:24px;color:#111827}
            h1{font-size:20px;margin:0 0 8px}
            p{margin:0 0 16px;color:#475569}
            table{width:100%;border-collapse:collapse;font-size:11px}
            th,td{border:1px solid #cbd5e1;padding:6px;text-align:left;vertical-align:top}
            th{background:#f1f5f9;text-transform:uppercase}
          </style>
        </head>
        <body>
          <h1>${htmlEscape(reportTabs.find((tab) => tab.value === reportTab)?.label || "Report")}</h1>
          <p>${activeReport.rows.length} records exported from Railway Dashboard.</p>
          <table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>
        </body>
      </html>
    `);
    doc.document.close();
    doc.focus();
    doc.print();
  };

  const saveReportPreset = async () => {
    const name = reportPresetName.trim() || `${reportTabs.find((tab) => tab.value === reportTab)?.label || "Report"} preset`;
    const preset = { id: `${Date.now()}`, name, reportTab, reportFilters, schedule: reportPresetSchedule };
    try {
      const saved = await fetchJson(reportPresetsUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, report_tab: reportTab, filters: reportFilters, schedule: reportPresetSchedule || null }),
      });
      setReportPresets((current) => [{ id: saved.preset_id, name: saved.name, reportTab: saved.report_tab, reportFilters: saved.filters || {}, schedule: saved.schedule || "" }, ...current.filter((item) => item.name !== name)].slice(0, 8));
      setActivityStatus("Report preset saved to PostgreSQL");
    } catch {
      setReportPresets((current) => [preset, ...current.filter((item) => item.name !== name)].slice(0, 8));
      setActivityStatus("Report preset saved locally; PostgreSQL is unavailable");
    }
    setReportPresetName("");
    setReportPresetSchedule("");
  };

  const applyReportPreset = (preset) => {
    setReportTab(preset.reportTab || "overview");
    setReportFilters({ ...reportFilters, ...(preset.reportFilters || {}) });
  };

  const runSavedReport = async (preset) => {
    if (!preset?.id || !/^[0-9a-f-]{20,}$/i.test(String(preset.id))) {
      setActivityStatus("This preset is local-only and cannot be run by the server yet.");
      return;
    }
    try {
      const run = await fetchJson(reportPresetRunUrl(preset.id), { method: "POST" });
      setActivityStatus(`Report generated: ${run.row_count || 0} alert rows`);
    } catch (error) {
      setActivityStatus(error?.message || "Scheduled report failed");
    }
  };

  const applyReportTemplate = (template) => {
    setReportTab(template.reportTab || "overview");
    setReportFilters(templateFilterState(reportFilters, template));
    setSearch((prev) => ({ ...prev, reports: template.search || "" }));
    const preset = templatePreset(template, reportFilters);
    setReportPresets((current) => [preset, ...current.filter((item) => item.id !== preset.id)].slice(0, 8));
  };

  const openDrillDown = (title, rows, columns, type) => {
    setDrillDown({ open: true, title, rows, columns, type });
  };

  const typeToView = { station: "stations", unit: "units", earning: "earnings", work: "works" };
  const recordForType = (type) => {
    if (type === "stations") return {};
    if (type === "units") return {};
    if (type === "earnings") return {};
    if (type === "works") return {};
    return {};
  };

  const openCreate = (type = view) => {
    if (!crudFields[type]) return;
    setFormError("");
    setFormModal({ open: true, type, mode: "create", data: recordForType(type) });
  };

  const openEdit = (type, data) => {
    setFormError("");
    setFormModal({ open: true, type, mode: "edit", data: { ...data } });
  };

  const closeForm = () => {
    setFormError("");
    setFormModal({ open: false, type: "stations", mode: "create", data: {} });
  };

  const submitForm = async (event) => {
    event.preventDefault();
    const type = formModal.type;
    const key = keyField[type];
    const path = resourcePath[type];
    const isEdit = formModal.mode === "edit";
    const keyValue = isEdit ? formModal.data[key] : type === "commercial-contracts" ? formModal.data.contract_name : formModal.data[key];
    if (!keyValue) {
      setFormError(`${type === "commercial-contracts" && !isEdit ? "contract_name" : key} is required`);
      return;
    }
    setFormError("");
    setSaving(true);
    try {
      let response = await fetch(`${API_URL}/api/${path}${isEdit ? `/${encodeURIComponent(formModal.data[key])}` : ""}`, {
        method: isEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formModal.data),
      });
      let payload = await response.json().catch(() => null);
      let savedMessage = isEdit ? "updated" : "created";
      if (!isEdit && response.status === 409 && type !== "commercial-contracts") {
        response = await fetch(`${API_URL}/api/${path}/${encodeURIComponent(keyValue)}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(formModal.data),
        });
        payload = await response.json().catch(() => null);
        savedMessage = "updated existing record";
      }
      if (!response.ok || payload?.success === false) {
        throw new Error(payload?.message || `Save failed: ${response.status}`);
      }
      closeForm();
      closeModal();
      await loadFromDb();
      setActivityStatus(`${keyValue} ${savedMessage}`);
    } catch (error) {
      const message = error?.message || "Save failed";
      setFormError(message);
      setActivityStatus(message);
    } finally {
      setSaving(false);
    }
  };

  const deleteRecord = async (type, data) => {
    const key = keyField[type];
    const path = resourcePath[type];
    const keyValue = data?.[key];
    if (!keyValue || !window.confirm(`Delete ${keyValue}?`)) return;
    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/api/${path}/${encodeURIComponent(keyValue)}`, { method: "DELETE" });
      const payload = await response.json().catch(() => null);
      if (!response.ok || payload?.success === false) {
        throw new Error(payload?.message || `Delete failed: ${response.status}`);
      }
      closeModal();
      await loadFromDb();
      setActivityStatus(`${keyValue} deleted`);
    } catch (error) {
      setActivityStatus(error?.message || "Delete failed");
    } finally {
      setSaving(false);
    }
  };

  const importPayload = () => ({
    csv_text: importModal.csvText,
    url: importModal.url,
  });

  const validateImport = async () => {
    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/api/import/${importModal.resource}/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(importPayload()),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok || payload?.success === false) {
        throw new Error(payload?.message || payload?.detail?.message || `Validation failed: ${response.status}`);
      }
      setImportModal((prev) => ({ ...prev, result: payload.data }));
      setActivityStatus(payload.data.valid ? "Import validation passed" : "Import validation found errors");
    } catch (error) {
      setActivityStatus(error?.message || "Validation failed");
    } finally {
      setSaving(false);
    }
  };

  const applyImport = async () => {
    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/api/import/${importModal.resource}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(importPayload()),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok || payload?.success === false) {
        throw new Error(typeof payload?.detail === "string" ? payload.detail : payload?.message || `Import failed: ${response.status}`);
      }
      setImportModal({ open: false, resource: "stations", csvText: "", url: "", result: null });
      await loadFromDb();
      setActivityStatus(`Imported ${payload.data.upserted} ${payload.data.resource} rows`);
    } catch (error) {
      setActivityStatus(error?.message || "Import failed");
    } finally {
      setSaving(false);
    }
  };

  const readCsvFile = async (file) => {
    if (!file) return;
    const text = await file.text();
    setImportModal((prev) => ({ ...prev, csvText: text, url: "", result: null }));
  };

  return (
    <main className="min-h-screen px-2 py-2 text-ink sm:px-4 sm:py-3 lg:px-5">
      <section className="mx-auto grid min-w-0 max-w-[1560px] grid-cols-[minmax(0,1fr)] gap-4 lg:h-[calc(100vh-1.5rem)] lg:grid-cols-[256px_minmax(0,1fr)]">
        <aside className="soft-surface soft-scroll min-w-0 max-w-full rounded-lg border p-3 sm:p-4 lg:sticky lg:top-3 lg:h-[calc(100vh-1.5rem)] lg:overflow-auto">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.22em] text-accent">Rail dashboard</div>
              <div className="mt-2 text-xl font-black text-ink">Navigation</div>
              <p className="mt-1 hidden text-sm text-muted sm:block">Stations, catering units, earnings, and passenger amenities.</p>
            </div>
            <div className="soft-raised rounded-lg border border-line p-2 text-accent">
              <Database size={18} />
            </div>
          </div>
          <div className="soft-scroll mt-4 flex w-full min-w-0 max-w-full gap-2 overflow-x-auto pb-2 lg:block lg:space-y-2 lg:overflow-visible lg:pb-0">
            <NavButton active={view === "dashboard"} icon={BarChart3} label="Dashboard" hint="KPI cards and charts" onClick={() => setView("dashboard")} />
            <NavButton active={view === "stations"} icon={TrainFront} label="Stations" hint="Station master and search" onClick={() => setView("stations")} />
            <NavButton active={false} icon={Wallet} label="Contracts" hint="Catering, commercial, and publicity" onClick={() => { window.location.href = "/contracts"; }} />
            <div className="hidden pt-2 text-[11px] font-black uppercase tracking-[0.2em] text-muted lg:block">Passenger Amenities</div>
            <NavButton active={view === "amenities"} icon={TrainFront} label="Amenity Infra" hint="Norms, platforms, wheel chairs, trolley paths" onClick={() => setView("amenities")} />
            <NavButton active={view === "works"} icon={Wrench} label="Sanctioned Works" hint="PA sanctioned works and station links" onClick={() => setView("works")} />
            <NavButton active={view === "reports"} icon={FileText} label="Reports" hint="License fee and unit alerts" onClick={() => setView("reports")} />
            <NavButton active={view === "ai"} icon={Bot} label="Ask AI" hint="Talk to any table safely" onClick={() => setView("ai")} />
            <NavButton active={view === "settings"} icon={SettingsIcon} label="Settings" hint="Fetch, sync, import, and database controls" onClick={() => setView("settings")} />
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:mt-5 lg:grid-cols-1">
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
          </div>
          <div className="soft-inset mt-3 rounded-lg border border-line p-3 lg:mt-4">
            <div className="text-[11px] font-black uppercase tracking-[0.18em] text-muted">Activity</div>
            <div className="mt-1 text-sm font-semibold text-ink">{activityStatus}</div>
            <div className="mt-1 text-xs text-muted">{lastRefreshAt || "No refresh yet"}</div>
          </div>
        </aside>

        <section className="soft-scroll min-w-0 space-y-4 lg:h-full lg:overflow-auto lg:pr-2">
          <div className="soft-surface sticky top-0 z-30 rounded-lg border p-4 sm:p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <Breadcrumbs title={viewConfig.title} />
                <h1 className="mt-2 text-3xl font-black tracking-tight text-ink sm:text-4xl">{viewConfig.title}</h1>
                <p className="mt-2 max-w-3xl text-sm text-muted">{viewConfig.subtitle}</p>
              </div>
              <div className="flex w-full flex-col gap-2 sm:w-[360px]">
                <SearchInput value={activeSearch} onChange={setActiveSearch} placeholder={`Search ${viewConfig.title.toLowerCase()}`} />
                <div className="text-right text-[11px] font-bold uppercase tracking-[0.14em] text-muted">
                  {view === "dashboard" ? "Overview" : `${dashboardCount} records`}
                </div>
              </div>
            </div>
            {viewConfig.filters.length ? (
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {viewConfig.filters.map(([label, value, onChange, options]) => (
                  <FilterSelect key={label} label={label} value={value} onChange={onChange} options={options} />
                ))}
              </div>
            ) : null}
          </div>

          {view === "settings" ? (
            <div className="space-y-4">
              <Panel
                title="Data refresh and source sync"
                subtitle="Run the validated source workflows here. Imports update PostgreSQL and then reload the dashboard data."
                action={<div className="text-xs font-bold text-muted">{loading ? "Operation in progress" : activityStatus}</div>}
              >
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  <Button onClick={loadData} disabled={loading} className="min-h-20 justify-start">
                    <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
                    <span><span className="block font-black">Refresh database</span><span className="text-xs font-medium opacity-75">Reload current PostgreSQL records</span></span>
                  </Button>
                  <Button onClick={refreshAllSources} disabled={loading} className="min-h-20 justify-start">
                    <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
                    <span><span className="block font-black">Refresh all sources</span><span className="text-xs font-medium opacity-75">Validated catering, amenities, and works</span></span>
                  </Button>
                  <Button variant="secondary" onClick={syncCateringData} disabled={loading} className="min-h-20 justify-start text-accent">
                    <Wallet size={18} />
                    <span><span className="block font-black">Sync catering sheet</span><span className="text-xs font-medium opacity-75">Units and payment/earnings data</span></span>
                  </Button>
                  <Button variant="secondary" onClick={importPassengerAmenities} disabled={loading} className="min-h-20 justify-start text-accent">
                    <Database size={18} />
                    <span><span className="block font-black">Fetch PA infra</span><span className="text-xs font-medium opacity-75">Station amenities and infrastructure</span></span>
                  </Button>
                  <Button variant="secondary" onClick={importSanctionedWorks} disabled={loading} className="min-h-20 justify-start text-accent">
                    <Wrench size={18} />
                    <span><span className="block font-black">Fetch sanctioned works</span><span className="text-xs font-medium opacity-75">Validated passenger amenity works</span></span>
                  </Button>
                </div>
              </Panel>
              <Panel title="Manual imports" subtitle="Use these for workbook or CSV-based source updates when required.">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <Button variant="secondary" onClick={importCommercialContractsWorkbook} disabled={loading} className="min-h-16 justify-start text-accent"><UploadCloud size={17} /><span><span className="block font-black">Import contracts XLSX</span><span className="text-xs font-medium opacity-75">Commercial contract registry</span></span></Button>
                  <Button variant="secondary" onClick={importPfExtensionWorkbook} disabled={loading} className="min-h-16 justify-start text-accent"><UploadCloud size={17} /><span><span className="block font-black">Import PF extension</span><span className="text-xs font-medium opacity-75">Platform extension workbook</span></span></Button>
                  <Button variant="secondary" onClick={() => setImportModal({ open: true, resource: "stations", csvText: "", url: "", result: null })} disabled={loading} className="min-h-16 justify-start text-accent"><UploadCloud size={17} /><span><span className="block font-black">Import CSV</span><span className="text-xs font-medium opacity-75">Select a supported data resource</span></span></Button>
                </div>
              </Panel>
              <Panel title="Latest activity" subtitle="The last operation status is shown here and in the sidebar.">
                <div className="soft-inset rounded-lg border border-line p-4">
                  <div className="text-sm font-black text-ink">{activityStatus}</div>
                  <div className="mt-1 text-xs text-muted">{lastRefreshAt || "No refresh yet"}</div>
                </div>
              </Panel>
            </div>
          ) : null}

          {view === "dashboard" ? (
            <>
              <Panel
                title="Data Centre"
                subtitle="Freshness and quality of the records currently powering this dashboard."
                action={
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <span className={cx(
                      "rounded-full border px-3 py-1 text-xs font-black",
                      dataCentre?.status === "ready"
                        ? "border-emerald-300 bg-emerald-500/10 text-emerald-700"
                        : "border-amber-300 bg-amber-500/10 text-amber-700",
                    )}
                    >
                      {dataCentre?.status === "ready" ? "Ready" : "Needs attention"}
                    </span>
                    <Button size="sm" variant="secondary" onClick={() => setView("settings")}><SettingsIcon size={14} /> Open Settings</Button>
                  </div>
                }
              >
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                  {Object.entries(dataCentre?.modules || {}).map(([key, module]) => (
                    <div key={key} className="soft-raised rounded-lg border border-line p-3">
                      {(() => {
                        const source = dataCentre?.source_snapshots?.[key] || {};
                        return (
                          <>
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-black uppercase tracking-[0.14em] text-muted">{key}</span>
                        <Database size={15} className="text-accent" />
                      </div>
                      <div className="mt-2 text-xl font-black text-ink">{module.count ?? 0}</div>
                      <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted">PostgreSQL records</div>
                      <div className="mt-1 text-[11px] text-muted">
                        {module.last_updated_at ? `Updated ${compactDate(module.last_updated_at)}` : "No update recorded"}
                      </div>
                      <div className="mt-1 text-[11px] font-semibold text-muted">
                        Source {source.source_count ?? "NA"} · {source.source || "PostgreSQL"}
                      </div>
                      <div className="mt-1 text-[11px] font-semibold text-muted">
                        Mobile {dataCentre?.mobile_cache?.counts?.[key] ?? "NA"}
                      </div>
                      {source.reconciliation ? (
                        <div className="mt-2 flex flex-wrap gap-1 text-[10px] font-bold">
                          {Object.entries(source.reconciliation).map(([label, count]) => (
                            <span key={label} className={cx(
                              "rounded-full border px-2 py-0.5",
                              label === "unmatched" && Number(count) > 0
                                ? "border-red-300 bg-red-500/10 text-red-700"
                                : label === "changed" && Number(count) > 0
                                  ? "border-blue-300 bg-blue-500/10 text-blue-700"
                                  : "border-line bg-surfaceStrong text-muted",
                            )}
                            >
                              {pretty(label)} {count}
                            </span>
                          ))}
                        </div>
                      ) : null}
                          </>
                        );
                      })()}
                    </div>
                  ))}
                </div>
                <div className="mt-3 flex flex-col gap-2 rounded-lg border border-line bg-surfaceStrong p-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                  <span className="text-muted">
                    {dataCentre?.quality?.total ? `${dataCentre.quality.total} data-quality exceptions require review.` : "No data-quality exceptions reported."}
                  </span>
                  <span className="font-semibold text-ink">
                    Last activity: {dataCentre?.last_sync_at ? compactDate(dataCentre.last_sync_at) : "Not available"}
                  </span>
                </div>
                <div className="mt-3 grid gap-2 rounded-lg border border-line bg-surfaceStrong p-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                  <div>
                    <div className="text-[10px] font-black uppercase tracking-[0.14em] text-muted">Mobile cache</div>
                    <div className="mt-1 font-black text-ink">
                      {dataCentre?.mobile_cache?.device_count ?? 0} devices · {dataCentre?.mobile_cache?.active_device_count ?? 0} active
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] font-black uppercase tracking-[0.14em] text-muted">Cached records</div>
                    <div className="mt-1 font-semibold text-ink">
                      {dataCentre?.mobile_cache?.counts?.stations ?? 0} stations · {dataCentre?.mobile_cache?.counts?.works ?? 0} works
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] font-black uppercase tracking-[0.14em] text-muted">Device queue</div>
                    <div className="mt-1 font-semibold text-ink">
                      {dataCentre?.mobile_cache?.pending_operations ?? 0} pending · {dataCentre?.mobile_cache?.failed_operations ?? 0} failed
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] font-black uppercase tracking-[0.14em] text-muted">Cache version</div>
                    <div className="mt-1 font-semibold text-ink">
                      {dataCentre?.mobile_cache?.data_version || "No device reported yet"}
                      {dataCentre?.mobile_cache?.last_seen_at ? ` · ${compactDate(dataCentre.mobile_cache.last_seen_at)}` : ""}
                    </div>
                  </div>
                </div>
                {dataCentre?.quality?.exceptions?.length ? (
                  <div className="mt-3 rounded-lg border border-amber-300/70 bg-amber-500/5 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <div className="text-[10px] font-black uppercase tracking-[0.14em] text-amber-700">Link exceptions</div>
                        <div className="mt-1 text-sm font-semibold text-ink">Review these records before trusting a cross-module report.</div>
                      </div>
                      <Badge tone="danger">{dataCentre.quality.total} total</Badge>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                      {dataCentre.quality.exceptions.slice(0, 9).map((exception, index) => (
                        <div key={`${exception.module}-${exception.record_key}-${index}`} className="rounded-md border border-line bg-surface p-2 text-xs">
                          <div className="flex items-center justify-between gap-2 font-black text-ink">
                            <span>{pretty(exception.module)}</span>
                            <span className="text-muted">{pretty(exception.record_key)}</span>
                          </div>
                          <div className="mt-1 text-muted">{exception.problem}</div>
                          {exception.station_code ? <div className="mt-1 font-semibold text-accent">Station {pretty(exception.station_code)}</div> : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </Panel>
              <Panel
                title="Action Centre"
                subtitle="The next records that need attention across contracts, receipts, works, and station links."
                action={
                  <Button variant="secondary" size="sm" onClick={() => { setView("reports"); setReportTab("actions"); }}>
                    View all <ChevronRight size={14} />
                  </Button>
                }
              >
                {reportActionRows.length ? (
                  <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                    {reportActionRows.slice(0, 8).map((row, index) => (
                      <button
                        key={`${row.action_type}-${row.action_key}-${index}`}
                        type="button"
                        onClick={() => openActionRecord(row)}
                        className="soft-raised rounded-lg border border-line p-3 text-left transition hover:-translate-y-0.5 hover:border-accent/50 focus-ring"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="rounded-full border border-amber-300 bg-amber-500/10 px-2 py-1 text-[10px] font-black uppercase tracking-[0.1em] text-amber-700">
                            {pretty(row.action_type)}
                          </span>
                          <CircleAlert size={16} className="shrink-0 text-amber-600" />
                        </div>
                        <div className="mt-3 truncate text-sm font-black text-ink">{pretty(row.action_key)}</div>
                        <div className="mt-1 truncate text-xs text-muted">{pretty(row.problem)}</div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <EmptyState title="No immediate actions" description="Contracts, receipts, works, and data links currently have no flagged items." />
                )}
              </Panel>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {dashboardCards.map((card) => (
                  <Card
                    key={card.key}
                    icon={card.icon}
                    label={card.label}
                    value={card.money ? money(stats?.[card.key] ?? 0) : card.key === "completedWorks" ? completedWorks : card.key === "pendingWorks" ? pendingWorks : card.key === "openFindings" ? reports?.inspections?.findings_open ?? 0 : card.key === "overdueFindings" ? reports?.inspections?.findings_overdue ?? 0 : stats?.[card.key] ?? 0}
                    subtext={card.subtext}
                  />
                ))}
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="Works by Station" subtitle="Top stations by work volume">
                  <SparkBars data={worksByStation} />
                </Panel>
                <Panel title="Works by Category" subtitle="Distribution of scope categories">
                  <Donut series={worksByCategory.map((item, index) => ({ ...item, color: ["#0f766e", "#2563eb", "#8b5cf6", "#f59e0b", "#ef4444"][index % 5] }))} totalLabel="Work category split" />
                </Panel>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="Revenue Trend" subtitle="Earnings movement across receipt dates">
                  <TrendLine data={revenueTrend} />
                </Panel>
                <Panel title="Status Distribution" subtitle="Current work status mix">
                  <Donut series={statusDistribution} totalLabel="Work status split" />
                </Panel>
              </div>
            </>
          ) : null}

          {view === "amenities" ? (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <Card icon={TrainFront} label="Infra Stations" value={paReports?.infra_records ?? paInfra.length} subtext={`${paReports?.coverage?.infra ?? 0}% station infra coverage`} />
                <Card icon={BarChart3} label="Platforms" value={paReports?.platform_records ?? paPlatforms.length} subtext="Platform length and access records" />
                <Card icon={Users} label="Wheel Chairs" value={paReports?.wheelchair_stations ?? paWheelchairs.length} subtext={`${paReports?.coverage?.wheelchairs ?? 0}% stations with entries`} />
                <Card icon={Wrench} label="PF Extn/Raising" value={paReports?.pf_extension_statuses ?? paPfExtension.length} subtext={`${paReports?.ramp_feasible ?? 0} ramp feasible, ${paReports?.lift_proposed ?? 0} lift proposed`} />
              </div>
              <Panel
                title="Passenger Amenity Workspace"
                subtitle="Data from PA Infra Master linked to station codes. Sanctioned works are kept under this head for station-wise amenity review."
                action={
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="secondary" onClick={() => setView("settings")}><SettingsIcon size={15} /> Manage in Settings</Button>
                  </div>
                }
              >
                <Tabs tabs={amenityTabs} value={amenityTab} onChange={setAmenityTab} />
                <div className="mt-4">
                  <DataTable
                    columns={activeAmenity.columns}
                    rows={activeAmenity.rows}
                    getKey={(row, index) => `${pretty(row.station_code || row.norm_key || row.pa_work_key || row.platform_key || row.work_key || row.project_id)}-${index}`}
                    onRowClick={(row) => {
                      if (amenityTab === "sanctionedWorks") return openWork(row);
                      if (amenityTab === "norms") return openAmenity(row);
                      if (amenityTab === "pfExtension") return openStationFromAmenity(row, "platforms");
                      return openStationFromAmenity(row, amenityTab === "platforms" ? "platforms" : "amenities");
                    }}
                    emptyTitle="No passenger amenity records match the current search."
                    fileName={activeAmenity.fileName}
                  />
                </div>
              </Panel>
            </div>
          ) : null}

          {view === "contracts" ? (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <Card icon={Users} label="Catering Units" value={filteredContracts.units.length} subtext="Contracts linked to stations" />
                <Card icon={Wallet} label="Payments" value={filteredContracts.earnings.length} subtext="Unit-wise payment records" />
                <Card icon={CircleAlert} label="Pending Payments" value={filteredContracts.earnings.filter((row) => /pending/i.test(pretty(row.receipt_type))).length} subtext="Receipts marked pending" />
                <Card icon={TrendingUp} label="Revenue" value={money(filteredContracts.earnings.reduce((sum, row) => sum + Number(row.amount || 0), 0))} subtext="Visible contract payments" />
              </div>
              <Panel
                title="Contracts Workspace"
                subtitle="Catering units are the contract records. Payments and earnings are reviewed inside the unit/contract context."
                action={
                  <Button size="sm" variant="secondary" onClick={() => setView("settings")}><SettingsIcon size={15} /> Manage in Settings</Button>
                }
              >
                {cateringSyncResult ? (
                  <div className="soft-inset mb-4 grid gap-2 rounded-lg border border-line p-3 text-xs text-muted sm:grid-cols-2 lg:grid-cols-4">
                    <div><span className="font-black text-ink">{cateringSyncResult.source?.units || 0}</span> units</div>
                    <div><span className="font-black text-ink">{cateringSyncResult.source?.earnings || 0}</span> unique receipts</div>
                    <div><span className="font-black text-ink">{cateringSyncResult.source?.duplicate_earning_rows || 0}</span> duplicates removed</div>
                    <div><span className="font-black text-ink">{cateringSyncResult.reconciliation?.linked_earning_rows || 0}</span> unit-linked receipts</div>
                  </div>
                ) : null}
                <Tabs tabs={contractTabs} value={contractTab} onChange={setContractTab} />
                <div className="mt-4">
                  <DataTable
                    columns={activeContract.columns}
                    rows={activeContract.rows}
                    getKey={(row, index) => `${pretty(row.unit_no || row.receipt_key || row.earning_key)}-${index}`}
                    onRowClick={contractTab === "earnings" ? openEarning : openUnit}
                    emptyTitle="No contract records match the current search."
                    fileName={activeContract.fileName}
                  />
                </div>
              </Panel>
            </div>
          ) : null}

          {view === "commercial" ? (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <Card icon={Database} label="Commercial Contracts" value={commercialContractReports?.total_contracts ?? commercialContracts.length} subtext="Non-catering commercial contracts" />
                <Card icon={TrainFront} label="Station Linked" value={commercialContractReports?.linked_station_rows ?? 0} subtext="Rows linked to station master" />
                <Card icon={Wallet} label="Annual Fee" value={money(commercialContractReports?.annual_license_fee ?? 0)} subtext="Annual license fee potential" />
                <Card icon={CircleAlert} label="Expiring Soon" value={commercialContractReports?.expiry_alerts?.length ?? 0} subtext="Contracts ending within 90 days" />
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="Policy Mix" subtitle="Commercial contracts by policy.">
                  <Donut
                    series={(commercialContractReports?.by_policy || []).slice(0, 6).map((item, index) => ({ label: item.label, value: item.value, color: ["#0f766e", "#2563eb", "#8b5cf6", "#f59e0b", "#ef4444", "#14b8a6"][index % 6] }))}
                    totalLabel="Policy split"
                  />
                </Panel>
                <Panel title="Recorded Payment Trend" subtitle="Monthly commercial payment values extracted from the workbook.">
                  <TrendLine data={(commercialContractReports?.by_month || []).map((row) => ({ label: row.label?.slice(0, 7), value: row.value }))} />
                </Panel>
              </div>
              <Panel
                title="Commercial Contracts Workspace"
                subtitle="OOH, parking, ATM/banking, mobile assets, pay-and-use, and other commercial contracts with station linkage where relevant."
                action={
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" size="sm" onClick={() => openCreate("commercial-contracts")}>
                      <Plus size={15} />
                      Add
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setView("settings")}><SettingsIcon size={15} /> Manage in Settings</Button>
                  </div>
                }
              >
                <DataTable
                  columns={commercialContractColumns}
                  rows={filteredCommercialContracts}
                  getKey={(row, index) => `${pretty(row.contract_key || row.contract_name)}-${pretty(row.station_code)}-${index}`}
                  onRowClick={openCommercialContract}
                  emptyTitle="No commercial contracts match the current search or filters."
                  fileName="commercial-contracts.csv"
                />
              </Panel>
            </div>
          ) : null}

          {view === "reports" ? (
            <div className="space-y-4">
              <StationMetricsReport />
              <Tabs tabs={reportTabs} value={reportTab} onChange={setReportTab} />
              <ReportTemplatesPanel templates={reportTemplates} onApply={applyReportTemplate} />
              <Panel
                title="Reports Builder"
                subtitle="Build a filtered report, save the preset, export it, or drill into records."
                action={
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" size="sm" onClick={exportReportExcel}>
                      <FileText size={14} />
                      Excel
                    </Button>
                    <Button variant="secondary" size="sm" onClick={exportReportPdf}>
                      <FileText size={14} />
                      PDF
                    </Button>
                  </div>
                }
              >
                <div className="grid gap-3 lg:grid-cols-4">
                  <label className="space-y-1">
                    <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">Month</span>
                    <input type="month" value={reportFilters.month} onChange={(event) => setReportFilters((prev) => ({ ...prev, month: event.target.value }))} className="soft-inset h-11 w-full rounded-lg border border-line px-3 text-sm outline-none focus:border-accent" />
                  </label>
                  <label className="space-y-1">
                    <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">From</span>
                    <input type="date" value={reportFilters.dateFrom} onChange={(event) => setReportFilters((prev) => ({ ...prev, dateFrom: event.target.value }))} className="soft-inset h-11 w-full rounded-lg border border-line px-3 text-sm outline-none focus:border-accent" />
                  </label>
                  <label className="space-y-1">
                    <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">To</span>
                    <input type="date" value={reportFilters.dateTo} onChange={(event) => setReportFilters((prev) => ({ ...prev, dateTo: event.target.value }))} className="soft-inset h-11 w-full rounded-lg border border-line px-3 text-sm outline-none focus:border-accent" />
                  </label>
                  <label className="soft-inset flex items-end gap-2 rounded-lg border border-line px-3 py-2 text-sm font-bold text-ink">
                    <input type="checkbox" checked={reportFilters.needsActionOnly} onChange={(event) => setReportFilters((prev) => ({ ...prev, needsActionOnly: event.target.checked }))} />
                    Needs action only
                  </label>
                </div>
                <div className="mt-3 grid gap-3 lg:grid-cols-3">
                  {[
                    ["Station", "station", ["All", ...new Set(stations.map((row) => pretty(row.station_code)).filter((value) => value !== "NA").sort())]],
                    ["Division", "division", ["All", ...new Set(stations.map((row) => pretty(row.division)).filter((value) => value !== "NA").sort())]],
                    ["Section", "section", ["All", ...new Set(stations.map((row) => pretty(row.section)).filter((value) => value !== "NA").sort())]],
                  ].map(([label, key, options]) => (
                    <label key={key} className="space-y-1">
                      <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">{label}</span>
                      <select value={reportFilters[key]} onChange={(event) => setReportFilters((prev) => ({ ...prev, [key]: event.target.value }))} className="soft-inset h-11 w-full rounded-lg border border-line px-3 text-sm outline-none focus:border-accent">
                        {options.map((option) => <option key={option} value={option}>{option}</option>)}
                      </select>
                    </label>
                  ))}
                </div>
                <div className="soft-inset mt-3 flex flex-col gap-3 rounded-lg border border-line p-3 xl:flex-row xl:items-center xl:justify-between">
                  <div className="flex flex-wrap gap-2">
                    {reportPresets.length ? reportPresets.map((preset) => (
                      <span key={preset.id} className="inline-flex items-center overflow-hidden rounded-full border border-line bg-surface text-xs font-black text-ink">
                        <button type="button" onClick={() => applyReportPreset(preset)} className="px-3 py-1.5 transition hover:bg-accent/10">
                          {preset.name}{preset.schedule ? ` · ${preset.schedule}` : ""}
                        </button>
                        {preset.schedule ? (
                          <button type="button" title="Run report now" onClick={() => runSavedReport(preset)} className="border-l border-line px-2 py-1.5 text-accent transition hover:bg-accent/10">
                            <RefreshCw size={13} />
                          </button>
                        ) : null}
                      </span>
                    )) : <span className="text-sm text-muted">No saved report presets yet.</span>}
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <input value={reportPresetName} onChange={(event) => setReportPresetName(event.target.value)} placeholder="Preset name" className="soft-inset h-10 rounded-lg border border-line px-3 text-sm outline-none focus:border-accent" />
                    <select value={reportPresetSchedule} onChange={(event) => setReportPresetSchedule(event.target.value)} className="soft-inset h-10 rounded-lg border border-line px-3 text-sm outline-none focus:border-accent">
                      <option value="">No schedule</option>
                      <option value="weekly">Weekly schedule</option>
                      <option value="monthly">Monthly schedule</option>
                    </select>
                    <Button size="sm" onClick={saveReportPreset}>Save preset</Button>
                    <Button variant="ghost" size="sm" onClick={() => setReportFilters({ month: "", dateFrom: "", dateTo: "", station: "All", division: "All", section: "All", needsActionOnly: false })}>Reset</Button>
                  </div>
                </div>
              </Panel>

              {reportTab === "overview" ? (
                <>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {reportCards.map((card) => (
                      <Card key={card.label} icon={card.icon} label={card.label} value={card.value} subtext={card.subtext} />
                    ))}
                  </div>
                  <div className="grid gap-4 lg:grid-cols-2">
                    <Panel title="Priority Alerts" subtitle="License fee risk buckets only">
                      <KeyValueGrid
                        rows={[
                          ["Overdue", reports?.license_fee_alerts?.overdue ?? 0],
                          ["Needs Review", reports?.license_fee_alerts?.needs_review ?? 0],
                          ["This Month", reports?.license_fee_alerts?.due_this_month ?? 0],
                          ["Next 30 Days", reports?.license_fee_alerts?.due_next_30_days ?? 0],
                          ["Next 90 Days", reports?.license_fee_alerts?.due_next_90_days ?? 0],
                          ["Overdue Estimate", money(reports?.license_fee_alerts?.estimated_overdue_amount ?? 0)],
                        ]}
                      />
                    </Panel>
                    <Panel title="Collection Snapshot" subtitle="Earnings summary without detailed rows">
                      <KeyValueGrid
                        rows={[
                          ["Total Receipts", reports?.earnings?.total_receipts ?? 0],
                          ["Total Amount", money(reports?.earnings?.total_amount ?? 0)],
                          ["License Fee Collected", money(reports?.earnings?.license_fee_collected ?? 0)],
                          ["Current Month LF", money(reports?.earnings?.current_month_license_collected ?? 0)],
                          ["Last 3 Months LF", money(reports?.earnings?.last_3_month_license_collected ?? 0)],
                          ["Pending Receipt Amount", money(reports?.earnings?.pending_receipt_amount ?? 0)],
                        ]}
                      />
                    </Panel>
                  </div>
                  <Panel title="Needs Action Preview" subtitle="Click any row to open the linked record. Use the Needs Action tab for the full list.">
                    <DataTable
                      columns={actionColumns}
                      rows={reportActionRows.slice(0, 50)}
                    getKey={(row, index) => `${row.action_type}-${row.action_key}-${index}`}
                      onRowClick={(row) => {
                        setReportTab("actions");
                        openReportRecord(row);
                      }}
                      emptyTitle="No action rows match the current filters."
                      fileName="needs-action-preview.csv"
                    />
                  </Panel>
                </>
              ) : null}

              {reportTab === "contract-expiry" ? (
                <Panel
                  title="Contract Validity Watch"
                  subtitle="Contracts approaching their validity end date, ordered by urgency."
                  action={
                    <div className="flex flex-wrap gap-2">
                      {[90, 50, 30, 10, 5, 0, 51].map((days) => (
                        <button
                          key={days}
                          type="button"
                          onClick={() => setContractExpiryWindow(days)}
                          className={cx(
                            "focus-ring rounded-full border px-3 py-2 text-xs font-black transition",
                            contractExpiryWindow === days
                              ? days === 51
                                ? "border-emerald-600 bg-emerald-600 text-white shadow-raised"
                              : days <= 10
                                ? "border-red-600 bg-red-600 text-white shadow-raised"
                                : "border-amber-500 bg-amber-500 text-white shadow-raised"
                              : days === 51
                                ? "border-emerald-300 bg-emerald-500/10 text-emerald-700 hover:border-emerald-500"
                                : days <= 10
                                ? "border-red-300 bg-red-500/10 text-red-600 hover:border-red-500"
                                : "border-amber-300 bg-amber-500/10 text-amber-700 hover:border-amber-500",
                          )}
                        >
                          {days === 51 ? "50+ days" : days === 0 ? "Today" : `${days} days`} ({contractExpiryCount(days)})
                        </button>
                      ))}
                    </div>
                  }
                >
                  <ListShell>
                    <div className="grid gap-2">
                      {visibleContractExpiryRows.map((row) => (
                        <button
                          key={row.key}
                          type="button"
                          onClick={() => {
                            if (row.source_type === "unit") {
                              const unit = units.find((item) => pretty(item.unit_no) === pretty(row.unit_no));
                              if (unit) openUnit(unit);
                              return;
                            }
                            const contract = commercialContracts.find((item) => pretty(item.contract_key || item.contract_name) === pretty(row.contract_key || row.contract_name));
                            if (contract) openCommercialContract(contract);
                          }}
                          className="soft-raised group flex min-h-16 items-center gap-3 rounded-lg border border-line px-3 py-2 text-left transition hover:-translate-y-0.5 hover:border-accent"
                        >
                          <div className="flex h-11 w-14 shrink-0 items-center justify-center rounded-md bg-accent/10 px-1 text-center text-[10px] font-black text-accent">
                            {pretty(row.contract_code)}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-black text-ink">{pretty(row.contract_name)}</div>
                            <div className="mt-0.5 truncate text-xs text-muted">
                              {pretty(row.station_code)}{pretty(row.station_name) !== "NA" ? ` - ${pretty(row.station_name)}` : ""} · Valid till {pretty(row.valid_to)}
                            </div>
                          </div>
                          <Badge tone={row.days_remaining < 0 || row.days_remaining <= 10 ? "danger" : row.days_remaining <= 30 ? "warning" : "success"}>
                            {row.days_remaining < 0 ? `Expired ${Math.abs(row.days_remaining)}d` : row.days_remaining === 0 ? "Today" : `${row.days_remaining}d`}
                          </Badge>
                          <div className="flex items-center text-muted">
                            <ChevronRight size={18} className="transition group-hover:translate-x-0.5" />
                          </div>
                        </button>
                      ))}
                      {!visibleContractExpiryRows.length ? (
                        <div className="soft-inset rounded-lg border border-line p-5 text-sm text-muted">
                          {contractExpiryWindow === 51
                            ? "No contracts have more than 50 days remaining under the current report filters."
                            : `No contracts expire within ${contractExpiryWindow} days under the current report filters.`}
                        </div>
                      ) : null}
                    </div>
                  </ListShell>
                </Panel>
              ) : null}

              {reportTab === "stations" ? (
                <Panel title="Station Reports" subtitle="Coverage by category, division, and linked activity">
                  <KeyValueGrid
                    rows={[
                      ["Stations", reports?.stations?.total ?? 0],
                      ["With Units", reports?.stations?.with_units ?? 0],
                      ["Without Units", reports?.stations?.without_units ?? 0],
                      ["With Earnings", reports?.stations?.with_earnings ?? 0],
                      ["With Works", reports?.stations?.with_works ?? 0],
                    ]}
                  />
                  <div className="mt-3">
                    <ReportList
                      rows={(reports?.stations?.by_category || []).slice(0, 8)}
                      onSelect={(row) => openDrillDown(`Stations: ${row.label}`, filteredReportStations.filter((station) => pretty(station.categorisation) === pretty(row.label)), stationColumns, "stations")}
                    />
                  </div>
                </Panel>
              ) : null}

              {reportTab === "units" ? (
                <Panel title="Unit Reports" subtitle="Status, category, license fee, and contract readiness">
                  <KeyValueGrid
                    rows={[
                      ["Total Units", reports?.units?.total ?? 0],
                      ["Active Units", reports?.units?.active ?? 0],
                      ["Inactive Units", reports?.units?.inactive ?? 0],
                      ["Missing License Fee", reports?.units?.missing_license_fee ?? 0],
                    ]}
                  />
                  <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                    <ReportList
                      rows={(reports?.units?.by_status || []).slice(0, 6)}
                      onSelect={(row) => openDrillDown(`Units: ${row.label}`, filteredReportUnits.filter((unit) => pretty(unit.unit_status) === pretty(row.label)), unitColumns, "units")}
                    />
                    <ReportList
                      rows={(reports?.units?.by_type || []).slice(0, 6)}
                      onSelect={(row) => openDrillDown(`Units by type: ${row.label}`, filteredReportUnits.filter((unit) => pretty(unit.type_of_unit) === pretty(row.label)), unitColumns, "units")}
                    />
                  </div>
                </Panel>
              ) : null}

              {reportTab === "earnings" ? (
                <Panel title="Earnings Reports" subtitle="Collection, pending receipts, and license fee trend">
                  <KeyValueGrid
                    rows={[
                      ["Total Receipts", reports?.earnings?.total_receipts ?? 0],
                      ["Total Amount", money(reports?.earnings?.total_amount ?? 0)],
                      ["License Fee Receipts", reports?.earnings?.license_fee_receipts ?? 0],
                      ["Current Month LF", money(reports?.earnings?.current_month_license_collected ?? 0)],
                      ["Last 3 Months LF", money(reports?.earnings?.last_3_month_license_collected ?? 0)],
                      ["Pending Receipt Amount", money(reports?.earnings?.pending_receipt_amount ?? 0)],
                    ]}
                  />
                  <div className="mt-3">
                    <ReportList
                      rows={(reports?.earnings?.by_head || []).slice(0, 6)}
                      moneyValues
                      onSelect={(row) => openDrillDown(`Earnings: ${row.label}`, filteredReportEarnings.filter((earning) => pretty(earning.payment_head) === pretty(row.label)), earningColumns, "earnings")}
                    />
                  </div>
                </Panel>
              ) : null}

              {reportTab === "works" ? (
                <Panel title="Works Reports" subtitle="Filter the sanctioned register by section or work category. Click a row for the complete record.">
                  <KeyValueGrid
                    rows={[
                      ["Total Works", reports?.works?.total ?? 0],
                      ["Completed", reports?.works?.completed ?? 0],
                      ["Pending/Open", reports?.works?.pending ?? 0],
                      ["TDC Delayed", reports?.works?.delayed ?? 0],
                      ["Contradictions", reports?.works?.contradictions ?? 0],
                    ]}
                  />
                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div className="soft-inset rounded-lg border border-line p-3">
                      <div className="mb-2 text-[11px] font-black uppercase tracking-[0.16em] text-muted">Sections</div>
                      <div className="flex flex-wrap gap-2">
                        {["All", ...Array.from(new Set(works.map(workReportSection))).sort()].map((value) => (
                          <button key={value} type="button" onClick={() => setReportWorkSection(value)} className={cx("rounded-full border px-3 py-2 text-xs font-black transition", reportWorkSection === value ? "border-accent bg-accent text-white" : "soft-control text-ink hover:border-accent")}>
                            {value}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="soft-inset rounded-lg border border-line p-3">
                      <div className="mb-2 text-[11px] font-black uppercase tracking-[0.16em] text-muted">Work categories</div>
                      <div className="flex flex-wrap gap-2">
                        {["All", ...Array.from(new Set(works.map(workReportType))).sort()].map((value) => (
                          <button key={value} type="button" onClick={() => setReportWorkType(value)} className={cx("rounded-full border px-3 py-2 text-xs font-black transition", reportWorkType === value ? "border-accent bg-accent text-white" : "soft-control text-ink hover:border-accent")}>
                            {value}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="mt-4">
                    <DataTable
                      columns={reportWorkColumns}
                      rows={filteredReportWorks}
                      getKey={(row, index) => `${pretty(row.project_id)}-${index}`}
                      onRowClick={openWork}
                      emptyTitle="No works match the selected section and category."
                      fileName="works-report-visible.xls"
                    />
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <ReportList
                      rows={(reports?.works?.by_status || []).slice(0, 7)}
                      onSelect={(row) => openDrillDown(`Works: ${row.label}`, filteredReportWorks.filter((work) => pretty(work.status) === pretty(row.label)), reportWorkColumns, "works")}
                    />
                    <ReportList
                      rows={(reports?.works?.by_scope || []).slice(0, 7)}
                      onSelect={(row) => openDrillDown(`Works by scope: ${row.label}`, filteredReportWorks.filter((work) => pretty(work.scope_type || work.block_section_station) === pretty(row.label)), reportWorkColumns, "works")}
                    />
                    <ReportList
                      rows={(reports?.works?.by_sr_den || []).slice(0, 7)}
                      onSelect={(row) => openDrillDown(`Works by Sr.DEN: ${row.label}`, filteredReportWorks.filter((work) => pretty(work.sr_den) === pretty(row.label)), reportWorkColumns, "works")}
                    />
                    <ReportList
                      rows={(reports?.works?.by_cmi || []).slice(0, 7)}
                      onSelect={(row) => openDrillDown(`Works by CMI: ${row.label}`, filteredReportWorks.filter((work) => pretty(work.cmi) === pretty(row.label)), reportWorkColumns, "works")}
                    />
                    <ReportList
                      rows={(reports?.works?.by_allocation || []).slice(0, 7)}
                      onSelect={(row) => openDrillDown(`Works by allocation: ${row.label}`, filteredReportWorks.filter((work) => pretty(work.allocation) === pretty(row.label)), reportWorkColumns, "works")}
                    />
                    <ReportList
                      rows={(reports?.works?.by_year || []).slice(0, 7)}
                      onSelect={(row) => openDrillDown(`Works by sanction year: ${row.label}`, filteredReportWorks.filter((work) => pretty(work.year_of_sanction) === pretty(row.label)), reportWorkColumns, "works")}
                    />
                  </div>
                  {(reports?.works?.delay_alerts?.length || reports?.works?.contradiction_rows?.length) ? (
                    <div className="mt-4 grid gap-3 lg:grid-cols-2">
                      <Panel title="TDC Delays" subtitle="Open works whose target completion date has passed.">
                        <ReportList
                          rows={(reports?.works?.delay_alerts || []).slice(0, 8).map((row) => ({ label: `${row.project_id} · ${row.days_overdue}d overdue`, value: row.progress_percent == null ? "NA" : `${row.progress_percent}%` }))}
                          onSelect={(row) => openDrillDown(`Delayed work: ${row.label}`, (reports?.works?.delay_alerts || []).filter((item) => item.project_id === row.label), reportWorkColumns, "works")}
                        />
                      </Panel>
                      <Panel title="Status Contradictions" subtitle="Records requiring review before management reporting.">
                        <ReportList
                          rows={(reports?.works?.contradiction_rows || []).slice(0, 8).map((row) => ({ label: `${row.project_id} · ${row.problem}`, value: row.progress_percent == null ? "NA" : `${row.progress_percent}%` }))}
                          onSelect={(row) => openDrillDown(`Work contradiction: ${row.label}`, (reports?.works?.contradiction_rows || []).filter((item) => item.project_id === row.label), reportWorkColumns, "works")}
                        />
                      </Panel>
                    </div>
                  ) : null}
                </Panel>
              ) : null}

              {reportTab === "inspections" ? (
                <Panel title="Inspection Management" subtitle="Open deficiencies, overdue actions, severity, and responsible departments across all stations.">
                  <KeyValueGrid
                    rows={[
                      ["Total Inspections", reports?.inspections?.total ?? 0],
                      ["Open Findings", reports?.inspections?.findings_open ?? 0],
                      ["Overdue Findings", reports?.inspections?.findings_overdue ?? 0],
                    ]}
                  />
                  <div className="mt-4 grid gap-3 lg:grid-cols-3">
                    <ReportList rows={(reports?.inspections?.by_severity || []).slice(0, 8)} />
                    <ReportList rows={(reports?.inspections?.by_department || []).slice(0, 8)} />
                    <ReportList rows={(reports?.inspections?.by_status_findings || []).slice(0, 8)} />
                  </div>
                  <div className="mt-4">
                    <div className="mb-2 text-[11px] font-black uppercase tracking-[0.16em] text-muted">Overdue actions</div>
                    <ReportList
                      rows={(reports?.inspections?.overdue_findings || []).slice(0, 12).map((row) => ({
                        ...row,
                        label: `${row.station_code || "NA"} · ${row.title || "Finding"}`,
                        value: `${row.days_overdue}d overdue`,
                      }))}
                      onSelect={(row) => {
                        const station = stations.find((item) => pretty(item.station_code) === pretty(row.station_code));
                        if (station) openStation(station, "alerts");
                      }}
                    />
                  </div>
                </Panel>
              ) : null}

              {reportTab === "actions" ? (
                <Panel title="Needs Action Reports" subtitle="Pending fee alerts, missing data, pending receipts, and open works">
                  <KeyValueGrid
                    rows={[
                      ["Needs Action Rows", reportActionRows.length],
                      ["License Fee Alerts", filteredReportAlerts.length],
                      ["Data Quality Rows", qualityRows.length],
                      ["Open Works", filteredReportWorks.filter((row) => !/complete|done/i.test(pretty(row.status))).length],
                    ]}
                  />
                </Panel>
              ) : null}

              {reportTab === "quality" ? (
                <Panel title="Data Quality Reports" subtitle="Records that need correction before reports become fully reliable">
                  <KeyValueGrid
                    rows={[
                      ["Units Missing Station", reports?.data_quality?.units_missing_station ?? 0],
                      ["Earnings Missing Unit", reports?.data_quality?.earnings_missing_unit ?? 0],
                      ["Earnings Missing Station", reports?.data_quality?.earnings_missing_station ?? 0],
                      ["Works Unmatched Station", reports?.data_quality?.works_unmatched_station ?? 0],
                      ["Units Missing Fee", reports?.data_quality?.units_missing_license_fee ?? 0],
                    ]}
                  />
                </Panel>
              ) : null}

              {reportTab !== "overview" && reportTab !== "contract-expiry" ? (
                <Panel title={`${reportTabs.find((tab) => tab.value === reportTab)?.label || "Report"} Records`} subtitle={`${activeReport.rows.length} records after report filters. Click a row to open its detail modal where applicable.`}>
                  <DataTable
                    columns={activeReport.columns}
                    rows={activeReport.rows}
                    getKey={(row, index) => `${pretty(row.station_code || row.unit_no || row.receipt_key || row.earning_key || row.project_id || row.action_key || row.record)}-${index}`}
                    onRowClick={reportTab === "quality" ? undefined : openReportRecord}
                    emptyTitle="No report rows match the current filters."
                    fileName={activeReport.fileName.replace(".xls", ".csv")}
                  />
                </Panel>
              ) : null}
            </div>
          ) : null}

          {view === "ai" ? (
            <div className="space-y-4">
              <Panel
                title="Ask AI"
                subtitle="Read-only assistant over stations, contracts, earnings, works, passenger amenities, and reports."
                action={
                  <Button size="sm" onClick={() => submitAiQuery()} disabled={aiLoading || !aiQuestion.trim()}>
                    <Send size={14} />
                    {aiLoading ? "Asking..." : "Ask"}
                  </Button>
                }
              >
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    submitAiQuery();
                  }}
                  className="space-y-3"
                >
                  <textarea
                    value={aiQuestion}
                    onChange={(event) => setAiQuestion(event.target.value)}
                    rows={4}
                    placeholder="Example: Tell me everything about KSM, or show stations where ramp is feasible but not proposed."
                    className="soft-inset w-full rounded-lg border border-line px-4 py-3 text-sm outline-none placeholder:text-muted focus:border-accent"
                  />
                  <div className="flex flex-wrap gap-2">
                    {aiSuggestions.map((suggestion) => (
                      <button
                        key={suggestion}
                        type="button"
                        onClick={() => submitAiQuery(suggestion)}
                        className="soft-control rounded-full px-3 py-1.5 text-xs font-black text-ink transition hover:border-accent active:shadow-pressed"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                  {aiError ? (
                    <div className="rounded-lg border border-red-300/70 bg-red-500/10 px-3 py-2 text-sm font-semibold text-red-500">
                      {aiError}
                    </div>
                  ) : null}
                </form>
              </Panel>

              {aiResult ? (
                <>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    {(aiResult.cards || []).map((card, index) => (
                      <Card
                        key={`${card.label}-${index}`}
                        icon={card.tone === "danger" ? CircleAlert : Bot}
                        label={card.label}
                        value={card.value}
                        subtext={card.tone === "danger" ? "Needs attention" : "AI result metric"}
                      />
                    ))}
                  </div>
                  <Panel title="AI Answer" subtitle="The answer is generated from controlled read-only tools and linked dashboard records.">
                    <p className="text-sm leading-6 text-ink">{aiResult.answer}</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {aiResult.graph ? <Badge tone="accent">{aiResult.graph}</Badge> : null}
                      {aiResult.mode ? <Badge tone={aiResult.mode === "langgraph_openai" ? "accent" : "danger"}>{aiResult.mode}</Badge> : null}
                      {aiResult.model ? <Badge>{aiResult.model}</Badge> : null}
                      {(aiResult.sources || []).map((source) => (
                        <Badge key={source} tone="accent">{source}</Badge>
                      ))}
                      {Object.entries(aiResult.applied_filters || {}).map(([key, value]) => (
                        <Badge key={`${key}-${value}`}>{key.replaceAll("_", " ")}: {pretty(value)}</Badge>
                      ))}
                    </div>
                    {aiResult.planner_error || aiResult.answer_error ? (
                      <div className="mt-4 rounded-lg border border-amber-300/70 bg-amber-400/10 px-3 py-2 text-xs font-semibold text-amber-700 dark:text-amber-200">
                        {aiResult.planner_error || aiResult.answer_error}
                      </div>
                    ) : null}
                    {aiResult.sql ? (
                      <pre className="soft-inset soft-scroll mt-4 overflow-auto rounded-lg border border-line p-3 text-xs text-muted">{aiResult.sql}</pre>
                    ) : null}
                  </Panel>
                  <Panel title="AI Result Rows" subtitle="Click rows with station, unit, or project identifiers to open the linked dashboard record.">
                    <DataTable
                      columns={aiColumns}
                      rows={aiRows}
                      getKey={(row, index) => `${pretty(row.station_code || row.unit_no || row.project_id || row.receipt_key || row.id)}-${index}`}
                      onRowClick={openAiRow}
                      emptyTitle="The AI answer did not return table rows."
                      fileName="ai-result-rows.csv"
                    />
                  </Panel>
                  {aiResult.suggested_actions?.length ? (
                    <Panel title="Suggested Actions" subtitle="Next steps based on the returned records.">
                      <div className="flex flex-wrap gap-2">
                        {aiResult.suggested_actions.map((action, index) => (
                          <Badge key={`${action}-${index}`}>{action}</Badge>
                        ))}
                      </div>
                    </Panel>
                  ) : null}
                </>
              ) : (
                <Panel title="How To Ask" subtitle="Use operational language. The assistant can answer with rows, KPIs, sources, and station drilldown.">
                  <KeyValueGrid
                    rows={[
                      ["Station", "Tell me everything about KSM"],
                      ["Contracts", "Show active units without recent earnings"],
                      ["Works", "Which stations have pending works?"],
                      ["Amenities", "Which stations need ramp or lift attention?"],
                      ["Reports", "Show overdue license fee alerts"],
                      ["Safety", "Only read-only SQL/tools are allowed"],
                    ]}
                  />
                </Panel>
              )}
            </div>
          ) : null}

          {view !== "dashboard" && view !== "reports" && view !== "amenities" && view !== "contracts" && view !== "commercial" && view !== "ai" && view !== "settings" ? (
          <Panel
            title={viewConfig.title}
            subtitle={view === "stations" ? "Station master with filtering and search." : view === "units" ? "Catering units linked to stations." : view === "earnings" ? "Earnings linked to units and station codes." : view === "works" ? "Sanctioned works with scope and status." : view === "reports" ? "License fee pending and contract expiry alert list." : "Dashboard summary"}
            action={
              crudFields[view] ? (
                <Button size="sm" onClick={() => openCreate(view)}>
                  <Plus size={15} />
                  Add
                </Button>
              ) : null
            }
          >
            <div className="mb-3 text-xs font-semibold text-muted">{view === "dashboard" ? "Summary view" : view === "reports" ? `${dashboardCount} alerts shown` : `${dashboardCount} records shown`}</div>

            {view === "reports" ? (
              <div className="space-y-3">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                  <Card icon={CircleAlert} label="Overdue" value={reports?.license_fee_alerts?.overdue ?? 0} subtext="Paid period is behind today" />
                  <Card icon={CircleAlert} label="Needs Review" value={reports?.license_fee_alerts?.needs_review ?? 0} subtext="No clear paid-through date found" />
                  <Card icon={Timer} label="This Month" value={reports?.license_fee_alerts?.due_this_month ?? 0} subtext="Fee or contract attention this month" />
                  <Card icon={Timer} label="Next 30 Days" value={reports?.license_fee_alerts?.due_next_30_days ?? 0} subtext="Contract ending within 30 days" />
                  <Card icon={FileText} label="Next 90 Days" value={reports?.license_fee_alerts?.due_next_90_days ?? 0} subtext="Three-month forward alert" />
                </div>
                <div className="soft-inset flex flex-wrap items-center gap-2 rounded-lg border border-line p-3 text-xs">
                  <span className="font-black uppercase tracking-[0.12em] text-muted">Contract expiry</span>
                  {[
                    ["Expired", "contract_expired"],
                    ["0 days", "contract_due_today"],
                    ["5 days", "contract_due_5_days"],
                    ["10 days", "contract_due_10_days"],
                    ["30 days", "contract_due_30_days"],
                    ["50 days", "contract_due_50_days"],
                    ["90 days", "contract_due_90_days"],
                  ].map(([label, key]) => (
                    <span key={key} className="rounded-full border border-line bg-surface px-3 py-1.5 font-bold text-ink">
                      {label}: {reports?.license_fee_alerts?.[key] ?? 0}
                    </span>
                  ))}
                </div>
                <ListShell>
                <div className="grid gap-3">
                  {filteredReportAlerts.slice(0, currentLimit).map((row) => (
                    <button
                      key={`${row.alert_bucket}-${row.unit_no}`}
                      type="button"
                      onClick={() => {
                        const unit = units.find((item) => pretty(item.unit_no) === pretty(row.unit_no));
                        if (unit) openUnit(unit);
                      }}
                      className="soft-raised group grid gap-3 rounded-lg border border-line p-4 text-left transition hover:-translate-y-0.5 hover:border-accent md:grid-cols-[1.1fr_1fr_1fr_auto]"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="text-xs font-black uppercase tracking-wide text-blue">{pretty(row.unit_no)} / {pretty(row.station_code)}</div>
                          <Badge tone={row.alert_bucket === "overdue" ? "danger" : "accent"}>{pretty(row.alert_bucket).replaceAll("_", " ")}</Badge>
                        </div>
                        <div className="mt-1 truncate text-sm font-bold text-ink">{pretty(row.licensee_name)}</div>
                        <div className="mt-1 text-xs text-muted">{pretty(row.station_name)} | {pretty(row.type_of_unit)}</div>
                      </div>
                      <div className="text-xs text-muted">
                        <div>Bucket: <span className="font-bold text-ink">{pretty(row.alert_bucket).replaceAll("_", " ")}</span></div>
                        <div>Last paid through: <span className="font-bold text-ink">{pretty(row.last_paid_through)}</span></div>
                        <div>Contract to: <span className="font-bold text-ink">{pretty(row.contract_to)}</span></div>
                      </div>
                      <div className="text-xs text-muted">
                        <div>Monthly fee: <span className="font-bold text-ink">{money(row.license_fee_amount)}</span></div>
                        <div>Pending months: <span className="font-bold text-ink">{pretty(row.months_pending)}</span></div>
                        <div>Estimate: <span className="font-bold text-ink">{money(row.estimated_pending_amount)}</span></div>
                      </div>
                      <div className="flex items-center justify-end gap-2 text-[11px] font-black uppercase tracking-[0.16em] text-muted">
                        Open Unit
                        <ChevronRight size={18} className="transition group-hover:translate-x-0.5" />
                      </div>
                    </button>
                  ))}
                  {!filteredReportAlerts.length ? <div className="soft-inset rounded-lg border border-line p-4 text-sm text-muted">No license fee alerts match the current search.</div> : null}
                </div>
                </ListShell>
                <ListFooter
                  shown={currentLimit}
                  total={filteredReportAlerts.length}
                  onMore={() => setVisibleLimit((prev) => ({ ...prev, reports: prev.reports + 24 }))}
                  onLess={() => setVisibleLimit((prev) => ({ ...prev, reports: 24 }))}
                />
              </div>
            ) : view === "stations" ? (
              <DataTable
                columns={stationColumns}
                rows={filteredStations}
                getKey={(row) => row.station_code}
                onRowClick={openStationSheet}
                emptyTitle="No stations match the current search or filters."
                fileName="stations-visible.csv"
              />
            ) : view === "units" ? (
              <DataTable
                columns={unitColumns}
                rows={filteredUnits}
                getKey={(row) => row.unit_no}
                onRowClick={openUnit}
                emptyTitle="No units match the current search or filters."
                fileName="units-visible.csv"
              />
            ) : view === "earnings" ? (
              <div className="space-y-3">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  <Card icon={Wallet} label="Paid" value={paidEarnings} subtext="Receipts marked paid / received" />
                  <Card icon={CircleAlert} label="Pending" value={pendingEarnings} subtext="Receipts marked pending" />
                  <Card icon={TrendingUp} label="Total" value={earnings.length} subtext="All earning records" />
                </div>
                <DataTable
                  columns={earningColumns}
                  rows={filteredEarnings}
                  getKey={(row) => row.earning_key || `${row.unit_no}-${row.date_of_receipt}`}
                  onRowClick={openEarning}
                  emptyTitle="No earnings match the current search."
                  fileName="earnings-visible.csv"
                />
              </div>
            ) : view === "works" ? (
              <div className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-4">
                  <Card icon={Wrench} label="Works" value={workMonitoring?.total ?? works.length} subtext="Unique sanctioned works" />
                  <Card icon={CircleAlert} label="Exceptions" value={workMonitoring?.exceptions ?? 0} subtext="Contradictions or TDC attention" />
                  <Card icon={Timer} label="TDC overdue" value={workMonitoring?.tdc_overdue ?? 0} subtext="Open works past target date" />
                  <Card icon={TrendingUp} label="Expenditure updates" value={(workMonitoring?.items || []).reduce((sum, row) => sum + Number(row.expenditure_update_count || 0), 0)} subtext="Historical ledger entries" />
                </div>
                <Tabs
                  tabs={[
                    { value: "station", label: `All Stations (${filteredWorks.station.length})`, icon: TrainFront },
                    { value: "abss", label: `ABSS (${filteredWorks.abss.length})`, icon: TrainFront },
                    { value: "division", label: `Division (${filteredWorks.division.length})`, icon: Database },
                  ]}
                  value={workTab}
                  onChange={setWorkTab}
                />
                <DataTable
                  columns={workColumns}
                  rows={activeWorkRows}
                  getKey={(row, index) => `${pretty(row.project_id)}-${pretty(row.station_code)}-${pretty(row.scope_type)}-${pretty(row.scope_value)}-${index}`}
                  onRowClick={openWork}
                  emptyTitle={workTab === "station" ? "No station-linked works match the selected station/search/status." : workTab === "abss" ? "No ABSS works match the current search/status filters." : "No division works match the current search/status filters."}
                  fileName={`works-${workTab}-visible.csv`}
                />
              </div>
            ) : null}
          </Panel>
          ) : null}
        </section>
      </section>

      <BottomSheet
        open={stationSheet.open}
        title={`${pretty(stationSheet.record?.station?.station_code)} - ${pretty(stationSheet.record?.station?.station_name)}`}
        subtitle="Operational snapshot with linked station records."
        onClose={() => setStationSheet({ open: false, record: null, loading: false })}
      >
        <StationQuickView
          record={stationSheet.record}
          loading={stationSheet.loading}
          stationAlerts={filteredReportAlerts}
          onOpenDetail={openStationDetailFromSheet}
          money={money}
        />
      </BottomSheet>

      <Modal
        open={modal.open}
        title={
          modal.type === "station"
            ? `${pretty(modal.record?.station?.station_code)} - ${pretty(modal.record?.station?.station_name)}`
            : modal.type === "unit"
              ? `${pretty(modal.record?.unit?.unit_no)} - ${pretty(modal.record?.unit?.licensee_name)}`
              : modal.type === "earning"
                ? `${pretty(modal.record?.earning?.unit_no)} - Earnings`
                : modal.type === "work"
                  ? `${pretty(modal.record?.work?.project_id)} - ${pretty(modal.record?.work?.short_name_of_work)}`
                  : modal.type === "commercial"
                    ? `${pretty(modal.record?.contract?.contract_name)} - Commercial`
                  : modal.type === "amenity"
                    ? `${pretty(modal.record?.amenity?.station_code || modal.record?.amenity?.category)} - Passenger Amenity`
                  : "Detail"
        }
        subtitle={
          modal.type === "station"
            ? "Station details with linked units, earnings, and works by station code."
            : modal.type === "unit"
              ? "Unit details with linked earnings by unit number."
              : modal.type === "earning"
                ? "Full earnings record."
                : modal.type === "work"
                  ? "Full sanctioned work record."
                  : modal.type === "commercial"
                    ? "Commercial contract details with station linkage and payment schedule."
                  : modal.type === "amenity"
                    ? "Passenger amenity data linked by station code."
                  : null
        }
        onClose={closeModal}
      >
        {modal.type === "station" ? (
          <Station360
            record={modal.record}
            activeTab={stationModalTab}
            onTabChange={setStationModalTab}
            saving={saving}
            onEdit={() => openEdit("stations", modal.record.station)}
            onDelete={() => deleteRecord("stations", modal.record.station)}
            stationAlerts={filteredReportAlerts}
            qualityRows={qualityRows}
            columns={{ platformColumns, paWorkColumns, unitColumns, workColumns, normColumns, commercialContractColumns }}
            openAmenity={openAmenity}
            openCommercialContract={openCommercialContract}
            openUnit={openUnit}
            openWork={openWork}
            onCreateAmenityFindings={createStationAmenityFindings}
            money={money}
          />
        ) : modal.type === "unit" ? (
          <div className="space-y-4">
            <DetailActions
              saving={saving}
              onEdit={() => openEdit("units", modal.record.unit)}
              onDelete={() => deleteRecord("units", modal.record.unit)}
            />
            <KeyValueGrid
              rows={[
                ["Unit No.", modal.record.unit.unit_no],
                ["Licensee", isAvailableUnit(modal.record.unit) ? "Not allotted" : modal.record.unit.licensee_name],
                ["Station Code", modal.record.unit.station_code],
                ["Station Name", modal.record.unit.station_name],
                ["Category", modal.record.unit.station_category],
                ["Type", modal.record.unit.type_of_unit],
                ["Status", modal.record.unit.unit_status],
                ["Remarks", modal.record.unit.remarks],
                ["License Fee", modal.record.unit.license_fee],
                ["Contract From", modal.record.unit.contract_from],
                ["Contract To", modal.record.unit.contract_to],
                ["Paid Upto", modal.record.unit.paid_upto],
                ...(!isAvailableUnit(modal.record.unit) ? [
                  ["Total Recorded Earnings", money(modal.record.earningsTotal)],
                  ["Latest Receipt", modal.record.latestReceipt?.date_of_receipt],
                  ["Latest Paid Period", modal.record.latestReceipt?.period_to],
                ] : []),
              ]}
            />
            {!isAvailableUnit(modal.record.unit) ? <Panel title="Linked Earnings" subtitle="Earnings rows linked by unit number">
              <div className="space-y-2">
                {modal.record.earnings.length ? modal.record.earnings.map((row) => (
                  <button key={row.earning_key || `${row.unit_no}-${row.date_of_receipt}`} type="button" onClick={() => openEarning(row)} className="soft-raised flex w-full items-start justify-between gap-3 rounded-lg border border-line px-3 py-3 text-left hover:border-accent">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-ink">{pretty(row.date_of_receipt)}</div>
                      <div className="mt-0.5 text-xs text-muted">{pretty(row.payment_head)} / {pretty(row.payment_sub_head)}</div>
                    </div>
                    <div className="shrink-0 text-xs text-muted">{money(row.amount)}</div>
                  </button>
                )) : <div className="text-sm text-muted">No linked earnings found.</div>}
              </div>
            </Panel> : null}
          </div>
        ) : modal.type === "earning" ? (
          <div className="space-y-4">
            <DetailActions
              saving={saving}
              onEdit={() => openEdit("earnings", modal.record.earning)}
              onDelete={() => deleteRecord("earnings", modal.record.earning)}
            />
            <KeyValueGrid
              rows={[
                ["Receipt Key", modal.record.earning.receipt_key],
                ["Unit No.", modal.record.earning.unit_no],
                ["Source Unit Label", modal.record.earning.raw_unit_no],
                ["Station Code", modal.record.earning.station_code],
                ["Source Station", modal.record.earning.raw_station_code],
                ["Earning Scope", modal.record.earning.earning_scope],
                ["Licensee", modal.record.earning.licensee_name],
                ["Receipt Type", modal.record.earning.receipt_type],
                ["Payment Head", modal.record.earning.payment_head],
                ["Payment Sub-head", modal.record.earning.payment_sub_head],
                ["Date of Receipt", modal.record.earning.date_of_receipt],
                ["Period From", modal.record.earning.period_from],
                ["Period To", modal.record.earning.period_to],
                ["Amount", money(modal.record.earning.amount)],
                ["GST", modal.record.earning.gst],
                ["MR No.", modal.record.earning.mr_no],
                ["MR Date", modal.record.earning.mr_date],
                ["UA Case", modal.record.earning.ua_case],
                ["Source Rows", modal.record.earning.source_rows],
                ["Duplicate Count", modal.record.earning.duplicate_count],
              ]}
            />
          </div>
        ) : modal.type === "work" ? (
          <div className="space-y-4">
            <DetailActions
              saving={saving}
              onEdit={() => openEdit("works", modal.record.work)}
              onDelete={() => deleteRecord("works", modal.record.work)}
            />
            <KeyValueGrid
              rows={[
                ["Project ID", modal.record.work.source_project_id || modal.record.work.project_id],
                ["Internal Key", modal.record.work.project_id],
                ["Sheet SN", modal.record.work.source_sn],
                ["Short Name", modal.record.work.short_name_of_work],
                ["Status", modal.record.work.status],
                ["Date of Sanction", modal.record.work.date_of_sanction],
                ["Block Section Station", modal.record.work.block_section_station],
                ["Scope Type", modal.record.work.scope_type],
                ["Scope Value", modal.record.work.scope_value],
                ["Station Code", modal.record.work.station_code],
                ["Section", modal.record.work.section],
                ["Allocation", modal.record.work.allocation],
                ["Cost", money(modal.record.work.cost)],
                ["Expenditure Upto Date", money(modal.record.work.expenditure_upto_date)],
                ["Physical Progress", modal.record.work.physical_progress],
                ["Financial Progress", modal.record.work.financial_progress],
                ["Anticipated Expenditure", modal.record.work.anticipated_expenditure],
                ["Remarks", modal.record.work.remarks],
              ]}
            />
            <Panel title="Progress history" subtitle="Periodic progress, expenditure, TDC and field remarks are retained instead of overwriting the work record.">
              <div className="grid gap-2 md:grid-cols-5">
                <input className="soft-inset h-10 rounded-lg border border-line px-3 text-sm outline-none focus:border-accent" type="date" value={progressDraft.update_date} onChange={(event) => setProgressDraft((current) => ({ ...current, update_date: event.target.value }))} />
                <input className="soft-inset h-10 rounded-lg border border-line px-3 text-sm outline-none focus:border-accent" type="number" min="0" max="100" placeholder="Progress %" value={progressDraft.progress_percent} onChange={(event) => setProgressDraft((current) => ({ ...current, progress_percent: event.target.value }))} />
                <input className="soft-inset h-10 rounded-lg border border-line px-3 text-sm outline-none focus:border-accent" type="number" min="0" placeholder="Expenditure" value={progressDraft.expenditure_upto_date} onChange={(event) => setProgressDraft((current) => ({ ...current, expenditure_upto_date: event.target.value }))} />
                <input className="soft-inset h-10 rounded-lg border border-line px-3 text-sm outline-none focus:border-accent" placeholder="Status" value={progressDraft.status} onChange={(event) => setProgressDraft((current) => ({ ...current, status: event.target.value }))} />
                <Button size="sm" onClick={saveWorkProgress} disabled={saving || !progressDraft.update_date}><Plus size={14} /> Save update</Button>
              </div>
              <textarea className="soft-inset mt-2 min-h-20 w-full rounded-lg border border-line px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Progress remarks" value={progressDraft.remarks} onChange={(event) => setProgressDraft((current) => ({ ...current, remarks: event.target.value }))} />
              {modal.record.progress_updates?.length ? (
                <div className="mt-3 space-y-2">
                  {modal.record.progress_updates.map((update) => (
                    <div key={update.progress_id || `${update.project_id}-${update.update_date}`} className="soft-raised rounded-lg border border-line p-3 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-black text-ink">{pretty(update.update_date)}</span>
                        <span className="font-semibold text-accent">{update.progress_percent == null ? "Progress NA" : `${update.progress_percent}%`}</span>
                      </div>
                      <div className="mt-1 text-xs text-muted">{pretty(update.status)} · Expenditure {money(update.expenditure_upto_date)}</div>
                      {update.remarks ? <div className="mt-2 text-sm text-muted">{update.remarks}</div> : null}
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {(update.photos || []).map((photo) => (
                          <a key={photo.photo_id} href={`${API_URL}${photo.download_url}`} target="_blank" rel="noreferrer" className="text-xs font-semibold text-accent hover:underline">Photo</a>
                        ))}
                        <label className="cursor-pointer rounded-full border border-line px-2 py-1 text-xs font-semibold text-muted hover:border-accent hover:text-accent">
                          Add photo
                          <input className="hidden" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => uploadWorkProgressPhoto(update, event.target.files?.[0])} />
                        </label>
                      </div>
                    </div>
                  ))}
                </div>
              ) : <div className="mt-3 text-sm text-muted">No periodic progress updates recorded yet.</div>}
            </Panel>
            <Panel title="Expenditure history" subtitle="Cumulative values are retained by date and can be reconciled against the work master record.">
              {modal.record.expenditure_updates?.length ? (
                <DataTable
                  columns={[
                    { key: "update_date", label: "Date" },
                    { key: "period_expenditure", label: "Period", value: (row) => money(row.period_expenditure) },
                    { key: "cumulative_expenditure", label: "Cumulative", value: (row) => money(row.cumulative_expenditure) },
                    { key: "source", label: "Source" },
                    { key: "remarks", label: "Remarks" },
                  ]}
                  rows={modal.record.expenditure_updates || []}
                  getKey={(row, index) => `${pretty(row.expenditure_id || row.update_date)}-${index}`}
                  emptyTitle="No expenditure history recorded."
                  fileName="work-expenditure-history.csv"
                />
              ) : <div className="text-sm text-muted">No separate expenditure ledger entries recorded yet.</div>}
            </Panel>
          </div>
        ) : modal.type === "commercial" ? (
          <div className="space-y-4">
            <DetailActions
              saving={saving}
              onEdit={() => openEdit("commercial-contracts", modal.record.contract)}
              onDelete={() => deleteRecord("commercial-contracts", modal.record.contract)}
            />
            <KeyValueGrid
              rows={[
                ["Contract Name", modal.record.contract.contract_name],
                ["Licensee", modal.record.contract.licensee_name],
                ["Policy", modal.record.contract.policy],
                ["Sub Category", modal.record.contract.sub_category],
                ["Asset Scope", modal.record.contract.asset_scope],
                ["Raw Station", modal.record.contract.raw_station_value],
                ["Station Match", modal.record.contract.station_match_status],
                ["Allocation Code", modal.record.contract.allocation_code],
                ["Allotted On", modal.record.contract.contract_allotted_on],
                ["Contract From", modal.record.contract.contract_period_from],
                ["Contract Upto", modal.record.contract.contract_upto],
                ["No. of Years", modal.record.contract.no_of_years],
                ["Space Sq Ft", modal.record.contract.space_sq_ft],
                ["Annual License Fee", money(modal.record.contract.annual_license_fee)],
                ["Quarterly License Fee", money(modal.record.contract.quarterly_license_fee)],
                ["Security Deposit", money(modal.record.contract.security_deposit)],
                ["Renewal Status", modal.record.contract.renewal_status],
                ["Termination Status", modal.record.contract.termination_status],
                ["Tender Status", modal.record.contract.tender_status],
                ["Recorded Payment Total", money(modal.record.payment_total)],
              ]}
            />
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => window.open(commercialContractStatementUrl(modal.record.contract.contract_key), "_blank", "noopener,noreferrer")}
              >
                <Download size={14} /> Download payment statement
              </Button>
            </div>
            <Panel title="Linked Stations" subtitle="Station links generated from Stn or inferred from contract name.">
              <DataTable
                columns={[
                  { key: "station_code", label: "Station", value: (row) => pretty(row.station_code), render: (row) => <span className="font-black text-blue">{pretty(row.station_code)}</span> },
                  { key: "station_name", label: "Name" },
                  { key: "division", label: "Division" },
                  { key: "section", label: "Section" },
                  { key: "match_type", label: "Match Type" },
                  { key: "match_status", label: "Status" },
                  { key: "raw_station_value", label: "Raw Value" },
                ]}
                rows={modal.record.station_links || []}
                getKey={(row, index) => `${pretty(row.id)}-${index}`}
                onRowClick={(row) => {
                  const station = stations.find((item) => pretty(item.station_code) === pretty(row.station_code));
                  if (station) openStation(station, "commercial");
                }}
                emptyTitle="No station links. This may be a mobile/train asset contract."
                fileName="commercial-contract-station-links.csv"
              />
            </Panel>
            <Panel title="Payment Schedule" subtitle="Month-wise payment values extracted from workbook columns.">
              <DataTable
                columns={commercialPaymentColumns}
                rows={modal.record.payments || []}
                getKey={(row, index) => `${pretty(row.payment_key || row.payment_month)}-${index}`}
                emptyTitle="No monthly payment rows found for this contract."
                fileName="commercial-contract-payments.csv"
              />
            </Panel>
          </div>
        ) : modal.type === "amenity" ? (
          <div className="space-y-4">
            <KeyValueGrid
              rows={Object.entries(modal.record.amenity || {})
                .filter(([key]) => !["source_hash", "created_at", "updated_at", "first_seen_at", "last_seen_at", "is_active"].includes(key))
                .map(([key, value]) => [key.replaceAll("_", " "), value])}
            />
            {modal.record.amenity?.station_code ? (
              <Panel title="Station Link" subtitle="Open the station master record linked to this amenity item.">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    const station = stations.find((item) => pretty(item.station_code) === pretty(modal.record.amenity.station_code));
                    if (station) openStation(station);
                  }}
                >
                  <TrainFront size={14} />
                  Open Station
                </Button>
              </Panel>
            ) : null}
          </div>
        ) : null}
      </Modal>
      <Modal
        open={drillDown.open}
        title={drillDown.title}
        subtitle={`${drillDown.rows.length} records from the selected report segment.`}
        onClose={() => setDrillDown({ open: false, title: "", rows: [], columns: [], type: null })}
      >
        <DataTable
          columns={drillDown.columns}
          rows={drillDown.rows}
          getKey={(row, index) => `${pretty(row.station_code || row.unit_no || row.receipt_key || row.earning_key || row.project_id || row.record)}-${index}`}
          onRowClick={(row) => {
            if (drillDown.type === "stations") openStation(row);
            if (drillDown.type === "units") openUnit(row);
            if (drillDown.type === "earnings") openEarning(row);
            if (drillDown.type === "works") openWork(row);
          }}
          emptyTitle="No records found for this drill-down."
          fileName="report-drill-down.csv"
        />
      </Modal>
      <Modal
        open={formModal.open}
        title={`${formModal.mode === "edit" ? "Edit" : "Add"} ${formModal.type}`}
        subtitle="Changes are saved directly to the application database."
        onClose={closeForm}
      >
        <RecordForm
          fields={crudFields[formModal.type] || []}
          value={formModal.data}
          onChange={(data) => setFormModal((prev) => ({ ...prev, data }))}
          onSubmit={submitForm}
          onCancel={closeForm}
          saving={saving}
          mode={formModal.mode}
          error={formError}
        />
      </Modal>
      <Modal
        open={importModal.open}
        title="Import Data"
        subtitle="Upload CSV text/file or provide a public Google Sheet CSV export URL. Validate before applying."
        onClose={() => setImportModal({ open: false, resource: "stations", csvText: "", url: "", result: null })}
      >
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1">
              <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">Module</span>
              <select
                value={importModal.resource}
                onChange={(event) => setImportModal((prev) => ({ ...prev, resource: event.target.value, result: null }))}
                className="soft-inset h-11 rounded-lg border border-line px-3 text-sm outline-none focus:border-accent"
              >
                <option value="stations">Stations</option>
                <option value="units">Units</option>
                <option value="works">Works</option>
                <option value="earnings">Earnings</option>
              </select>
            </label>
            <label className="grid gap-1">
              <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">CSV File</span>
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => readCsvFile(event.target.files?.[0])}
                className="soft-inset h-11 rounded-lg border border-line px-3 py-2 text-sm outline-none focus:border-accent"
              />
            </label>
          </div>
          <label className="grid gap-1">
            <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">Google Sheet CSV URL</span>
            <input
              value={importModal.url}
              onChange={(event) => setImportModal((prev) => ({ ...prev, url: event.target.value, csvText: "", result: null }))}
              placeholder="https://docs.google.com/spreadsheets/d/.../gviz/tq?tqx=out:csv&gid=..."
              className="soft-inset h-11 rounded-lg border border-line px-3 text-sm outline-none focus:border-accent"
            />
          </label>
          <label className="grid gap-1">
            <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">CSV Text</span>
            <textarea
              value={importModal.csvText}
              onChange={(event) => setImportModal((prev) => ({ ...prev, csvText: event.target.value, url: "", result: null }))}
              rows={8}
              className="soft-inset rounded-lg border border-line px-3 py-2 text-sm outline-none focus:border-accent"
            />
          </label>
          {importModal.result ? (
            <div className="soft-inset rounded-lg border border-line p-3 text-sm">
              <div className="font-bold text-ink">{importModal.result.rows} rows checked - {importModal.result.valid ? "valid" : "errors found"}</div>
              {importModal.result.preview ? (
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
                  {[
                    ["Added", importModal.result.preview.added?.count || 0, "text-emerald-700"],
                    ["Changed", importModal.result.preview.changed?.count || 0, "text-blue-700"],
                    ["Removed", importModal.result.preview.removed?.count || 0, "text-amber-700"],
                    ["Duplicates", importModal.result.preview.duplicates?.count || 0, "text-red-700"],
                    ["Unmatched", importModal.result.preview.unmatched?.count || 0, "text-red-700"],
                  ].map(([label, count, tone]) => (
                    <div key={label} className="rounded-md border border-line bg-surface px-2 py-2">
                      <div className="text-[10px] font-black uppercase tracking-[0.12em] text-muted">{label}</div>
                      <div className={`mt-1 text-base font-black ${tone}`}>{count}</div>
                    </div>
                  ))}
                {importModal.result.preview.removal_policy ? (
                  <div className="mt-2 text-[11px] text-muted">{importModal.result.preview.removal_policy}</div>
                ) : null}
                </div>
              ) : null}
              {importModal.result.errors?.length ? (
                <div className="mt-2 max-h-32 overflow-auto text-xs text-red-700">
                  {importModal.result.errors.map((error, index) => (
                    <div key={`${error.row}-${error.field}-${index}`}>Row {error.row}: {error.field} - {error.message}</div>
                  ))}
                </div>
              ) : null}
              {importModal.result.preview?.unmatched?.rows?.length ? (
                <div className="mt-2 max-h-24 overflow-auto text-xs text-amber-800">
                  {importModal.result.preview.unmatched.rows.slice(0, 8).map((row, index) => (
                    <div key={`${row.row}-${row.key}-${index}`}>Row {row.row}: {row.key || "record"} - {row.reason}</div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button variant="secondary" onClick={() => setImportModal({ open: false, resource: "stations", csvText: "", url: "", result: null })}>
              Cancel
            </Button>
            <Button variant="secondary" onClick={validateImport} disabled={saving} className="text-accent">
              Validate
            </Button>
            <Button onClick={applyImport} disabled={saving || importModal.result?.valid === false}>
              Apply Import
            </Button>
          </div>
        </div>
      </Modal>
    </main>
  );
}
