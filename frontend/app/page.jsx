"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Bot,
  CircleAlert,
  ChevronRight,
  Database,
  FileText,
  Home,
  Moon,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Send,
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
import { DataTable } from "../components/ui";
import { Station360 } from "../components/station-360";
import { ReportTemplatesPanel } from "../components/reports/report-templates-panel";
import { API_URL, aiQueryUrl, fetchJson, importPassengerAmenitiesUrl, importPfExtensionUrl, stationDetailUrl } from "../lib/api";
import { reportTemplates, templateFilterState, templatePreset } from "../lib/report-templates";
import { useRailDashboardData } from "../hooks/use-rail-dashboard-data";

const money = (value) => `INR ${Number(value || 0).toLocaleString("en-IN")}`;
const pretty = (value) => (value === null || value === undefined || value === "" ? "NA" : String(value));
const toNumber = (value) => Number(value || 0);
const cx = (...classes) => classes.filter(Boolean).join(" ");
const compactDate = (value) => {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString().slice(0, 10);
};
const monthKey = (value) => compactDate(value).slice(0, 7);
const htmlEscape = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));

const buttonClasses = {
  primary: "bg-accent text-white shadow-glow hover:bg-accent/90",
  secondary: "border border-line bg-surface/80 text-ink hover:border-accent hover:bg-surfaceStrong",
  ghost: "text-muted hover:bg-surface/75 hover:text-ink",
  danger: "border border-red-300/70 bg-surface/80 text-red-600 hover:bg-red-500/10",
};

function Button({ children, variant = "primary", size = "md", className = "", ...props }) {
  return (
    <button
      type="button"
      className={cx(
        "focus-ring inline-flex items-center justify-center gap-2 rounded-xl font-extrabold transition disabled:cursor-not-allowed disabled:opacity-60",
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
    neutral: "border-line bg-surface/80 text-muted",
    accent: "border-accent/30 bg-accentSoft text-accentStrong",
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
    <div className="mt-4 flex flex-col items-center justify-between gap-3 rounded-2xl border border-line bg-surface/55 px-4 py-3 text-sm text-muted sm:flex-row">
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
    <div className="soft-scroll flex gap-2 overflow-x-auto rounded-2xl border border-line bg-surface/45 p-1.5">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const active = value === tab.value;
        return (
          <button
            key={tab.value}
            type="button"
            onClick={() => onChange(tab.value)}
            className={cx(
              "focus-ring inline-flex h-10 shrink-0 items-center gap-2 rounded-xl px-3 text-xs font-black uppercase tracking-[0.12em] transition",
              active ? "bg-accent text-white shadow-glow" : "text-muted hover:bg-surface hover:text-ink",
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
    <div className="glass rounded-2xl border p-5 transition hover:-translate-y-0.5 hover:shadow-glow">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-black uppercase tracking-[0.18em] text-muted">{label}</div>
          <div className="mt-2 text-2xl font-black text-ink">{value}</div>
        </div>
        <div className="rounded-xl bg-accentSoft p-3 text-accentStrong shadow-glow">
          <Icon size={18} />
        </div>
      </div>
      <div className="mt-3 text-xs font-semibold text-muted">{subtext}</div>
    </div>
  );
}

function Panel({ title, subtitle, action, children }) {
  return (
    <section className="glass rounded-2xl border p-5">
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

function ReportList({ rows = [], moneyValues = false, onSelect }) {
  return (
    <div className="space-y-2">
      {rows.length ? rows.map((row) => (
        <button
          key={row.label}
          type="button"
          onClick={() => onSelect?.(row)}
          className={cx(
            "flex w-full items-center justify-between gap-3 rounded-xl border border-line bg-surface/70 px-3 py-2.5 text-left text-sm transition",
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
      className={`focus-ring flex w-full items-start gap-3 rounded-xl border px-3 py-3 text-left transition ${active ? "border-accent bg-accentSoft text-accentStrong shadow-glow" : "border-line bg-surface/60 text-ink hover:border-accent hover:bg-surfaceStrong"
        }`}
    >
      <span className="rounded-lg border border-line bg-surface/70 p-1.5">
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
        className="h-11 w-full rounded-xl border border-line bg-surface/85 pl-10 pr-3 text-sm outline-none placeholder:text-muted focus:border-accent"
        placeholder={placeholder}
      />
    </label>
  );
}

function FilterSelect({ label, value, onChange, options }) {
  return (
    <label className="grid gap-1">
      <span className="text-[11px] font-black uppercase tracking-[0.18em] text-muted">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="h-11 rounded-xl border border-line bg-surface/85 px-3 text-sm outline-none focus:border-accent">
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
      className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-line bg-surface/85 px-3 text-sm font-extrabold text-ink transition hover:border-accent"
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
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-3">
      <div className="max-h-[92vh] w-full max-w-5xl overflow-hidden rounded-2xl border border-line bg-surfaceStrong shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-line bg-surface px-4 py-4">
          <div>
            <div className="text-[11px] font-black uppercase tracking-[0.2em] text-accent">Detail view</div>
            <h3 className="mt-1 text-xl font-black text-ink">{title}</h3>
            {subtitle ? <p className="mt-1 text-sm text-muted">{subtitle}</p> : null}
          </div>
          <button type="button" onClick={onClose} className="focus-ring rounded-full border border-line bg-surface p-2 text-ink transition hover:border-accent hover:bg-surfaceStrong">
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
        <div key={label} className="rounded-xl border border-line bg-surface p-3">
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
              className="h-11 rounded-xl border border-line bg-surface px-3 text-sm outline-none disabled:bg-surfaceStrong disabled:text-muted focus:border-accent"
            />
          </label>
        ))}
      </div>
      {error ? (
        <div className="rounded-xl border border-red-300/70 bg-red-500/10 px-3 py-2 text-sm font-semibold text-red-500">
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
      { name: "short_name_of_work", label: "Short Name of Work", required: true },
      { name: "status", label: "Status" },
      { name: "date_of_sanction", label: "Date of Sanction" },
      { name: "block_section_station", label: "Block Section Station" },
      { name: "section", label: "Section" },
      { name: "allocation", label: "Allocation" },
      { name: "anticipated_expenditure", label: "Anticipated Expenditure", type: "number" },
      { name: "remarks", label: "Remarks" },
      { name: "engg_remarks", label: "Engineering Remarks" },
    ],
  };

  const resourcePath = { stations: "stations", units: "units", earnings: "earnings", works: "works" };
  const keyField = { stations: "station_code", units: "unit_no", earnings: "receipt_key", works: "project_id" };

  const {
    stats,
    stations,
    units,
    earnings,
    works,
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
  const [search, setSearch] = useState({ dashboard: "", stations: "", contracts: "", units: "", earnings: "", works: "", amenities: "", reports: "", ai: "" });
  const [visibleLimit, setVisibleLimit] = useState({ stations: 24, units: 24, earnings: 24, works: 24, reports: 24 });
  const [amenityTab, setAmenityTab] = useState("summary");
  const [contractTab, setContractTab] = useState("units");
  const [stationModalTab, setStationModalTab] = useState("overview");
  const [reportTab, setReportTab] = useState("overview");
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
  const [drillDown, setDrillDown] = useState({ open: false, title: "", rows: [], columns: [], type: null });
  const [filters, setFilters] = useState({
    stationCategory: "All",
    stationDivision: "All",
    stationSection: "All",
    stationPlatform: "All",
    unitCategory: "All",
    unitType: "All",
    unitStatus: "All",
    workScope: "All",
    workStatus: "All",
  });
  const [modal, setModal] = useState({ open: false, type: null, record: null });
  const [formModal, setFormModal] = useState({ open: false, type: "stations", mode: "create", data: {} });
  const [formError, setFormError] = useState("");
  const [importModal, setImportModal] = useState({ open: false, resource: "stations", csvText: "", url: "", result: null });
  const [saving, setSaving] = useState(false);
  const [aiQuestion, setAiQuestion] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [aiError, setAiError] = useState("");

  const aiSuggestions = [
    "Tell me everything about KSM",
    "Show pending license fee alerts",
    "Which works are still pending?",
    "Which stations need ramp or lift attention?",
    "Show units with missing license fee",
    "Give station coverage summary",
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
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("rail-dashboard-theme", theme);
  }, [theme]);

  useEffect(() => {
    window.localStorage.setItem("rail-report-presets", JSON.stringify(reportPresets));
  }, [reportPresets]);

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
    const q = search.stations.trim().toLowerCase();
    return stations.filter((row) => {
      const searchOk = [row.station_code, row.station_name, row.division, row.section, row.categorisation].some((value) => pretty(value).toLowerCase().includes(q));
      const catOk = filters.stationCategory === "All" || pretty(row.categorisation) === filters.stationCategory;
      const divOk = filters.stationDivision === "All" || pretty(row.division) === filters.stationDivision;
      const secOk = filters.stationSection === "All" || pretty(row.section) === filters.stationSection;
      const platOk = filters.stationPlatform === "All" || pretty(row.platform_type) === filters.stationPlatform;
      return searchOk && catOk && divOk && secOk && platOk;
    });
  }, [stations, search.stations, filters]);

  const filteredUnits = useMemo(() => {
    const q = search.units.trim().toLowerCase();
    return units.filter((row) => {
      const searchOk = [row.unit_no, row.station_code, row.station_name, row.licensee_name, row.unit_status, row.station_category].some((value) => pretty(value).toLowerCase().includes(q));
      const catOk = filters.unitCategory === "All" || pretty(row.station_category) === filters.unitCategory;
      const typeOk = filters.unitType === "All" || pretty(row.type_of_unit) === filters.unitType;
      const statusOk = filters.unitStatus === "All" || pretty(row.unit_status) === filters.unitStatus;
      return searchOk && catOk && typeOk && statusOk;
    });
  }, [units, search.units, filters]);

  const filteredEarnings = useMemo(() => {
    const q = search.earnings.trim().toLowerCase();
    return earnings.filter((row) => [row.unit_no, row.station_code, row.licensee_name, row.payment_head, row.payment_sub_head, row.receipt_type].some((value) => pretty(value).toLowerCase().includes(q)));
  }, [earnings, search.earnings]);

  const filteredContracts = useMemo(() => {
    const q = (search.contracts || "").trim().toLowerCase();
    return {
      units: units.filter((row) => [row.unit_no, row.station_code, row.station_name, row.licensee_name, row.unit_status, row.station_category, row.type_of_unit].some((value) => pretty(value).toLowerCase().includes(q))),
      earnings: earnings.filter((row) => [row.unit_no, row.station_code, row.licensee_name, row.payment_head, row.payment_sub_head, row.receipt_type, row.mr_no].some((value) => pretty(value).toLowerCase().includes(q))),
    };
  }, [units, earnings, search.contracts]);

  const filteredWorks = useMemo(() => {
    const q = search.works.trim().toLowerCase();
    return works.filter((row) => {
      const searchOk = [row.project_id, row.short_name_of_work, row.block_section_station, row.section, row.status].some((value) => pretty(value).toLowerCase().includes(q));
      const scopeOk = filters.workScope === "All" || pretty(row.scope_type || row.block_section_station) === filters.workScope;
      const statusOk = filters.workStatus === "All" || pretty(row.status) === filters.workStatus;
      return searchOk && scopeOk && statusOk;
    });
  }, [works, search.works, filters]);

  const filteredAmenities = useMemo(() => {
    const q = search.amenities.trim().toLowerCase();
    const contains = (row, fields) => fields.some((field) => pretty(row[field]).toLowerCase().includes(q));
    const filterRows = (rows, fields) => rows.filter((row) => !q || contains(row, fields));
    return {
      summary: filterRows(paSummary, ["station_code", "station_name", "division", "section", "category", "trolley_path", "fob_details"]),
      infra: filterRows(paInfra, ["station_code", "station_name", "division", "section", "category", "fob_details", "shelter_details"]),
      platforms: filterRows(paPlatforms, ["station_code", "station_name", "division", "section", "platform"]),
      wheelchairs: filterRows(paWheelchairs, ["station_code", "station_name", "division", "section", "category"]),
      trolley: filterRows(paTrolley, ["station_code", "station_name", "division", "section", "categorisation", "trolley_path"]),
      paWorks: filterRows(paWorks, ["station_code", "station_name", "work_type", "work_name", "progress", "tender_status", "executive_agency"]),
      pfExtension: filterRows(paPfExtension, ["station_code", "station_name", "division", "section", "category", "status_text", "remarks"]),
      norms: filterRows(paNorms, ["category", "amenity", "norm", "norm_quantity"]),
      sanctionedWorks: filteredWorks,
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
    const stationOk = reportFilters.station === "All" || code === reportFilters.station;
    const divisionOk = reportFilters.division === "All" || division === reportFilters.division;
    const sectionOk = reportFilters.section === "All" || section === reportFilters.section;
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
    const q = search.reports.trim().toLowerCase();
    return stations.filter((row) => {
      const textOk = [row.station_code, row.station_name, row.division, row.section, row.categorisation].some((value) => pretty(value).toLowerCase().includes(q));
      return textOk && matchesReportScope(row);
    });
  }, [stations, search.reports, reportFilters, stationByCode]);

  const filteredReportUnits = useMemo(() => {
    const q = search.reports.trim().toLowerCase();
    return units.filter((row) => {
      const textOk = [row.unit_no, row.station_code, row.station_name, row.licensee_name, row.type_of_unit, row.unit_status].some((value) => pretty(value).toLowerCase().includes(q));
      const actionOk = !reportFilters.needsActionOnly || !row.license_fee || !row.station_code || !/active/i.test(pretty(row.unit_status));
      return textOk && actionOk && matchesReportScope(row) && matchesReportDate(row, ["contract_to", "contract_from"]);
    });
  }, [units, search.reports, reportFilters, stationByCode]);

  const filteredReportEarnings = useMemo(() => {
    const q = search.reports.trim().toLowerCase();
    return earnings.filter((row) => {
      const textOk = [row.unit_no, row.station_code, row.licensee_name, row.payment_head, row.payment_sub_head, row.receipt_type].some((value) => pretty(value).toLowerCase().includes(q));
      const actionOk = !reportFilters.needsActionOnly || /pending/i.test(pretty(row.receipt_type));
      return textOk && actionOk && matchesReportScope(row) && matchesReportDate(row, ["date_of_receipt", "mr_date", "period_to"]);
    });
  }, [earnings, search.reports, reportFilters, stationByCode]);

  const filteredReportWorks = useMemo(() => {
    const q = search.reports.trim().toLowerCase();
    return works.filter((row) => {
      const textOk = [row.project_id, row.short_name_of_work, row.station_code, row.section, row.status, row.scope_type].some((value) => pretty(value).toLowerCase().includes(q));
      const actionOk = !reportFilters.needsActionOnly || !/complete|done/i.test(pretty(row.status));
      return textOk && actionOk && matchesReportScope(row) && matchesReportDate(row, ["date_of_sanction"]);
    });
  }, [works, search.reports, reportFilters, stationByCode]);

  const reportAlerts = reports?.license_fee_alerts?.rows || [];
  const filteredReportAlerts = useMemo(() => {
    const q = search.reports.trim().toLowerCase();
    return reportAlerts.filter((row) => [
      row.unit_no,
      row.station_code,
      row.station_name,
      row.licensee_name,
      row.type_of_unit,
      row.unit_status,
      row.alert_bucket,
    ].some((value) => pretty(value).toLowerCase().includes(q)) && matchesReportScope(row) && matchesReportDate(row, ["contract_to", "last_paid_through"]));
  }, [reportAlerts, search.reports, reportFilters, stationByCode]);

  const reportActionRows = useMemo(() => {
    const rows = [
      ...filteredReportAlerts.map((row) => ({ ...row, action_type: "License Fee Alert", module: "units", action_key: row.unit_no, problem: pretty(row.alert_bucket).replaceAll("_", " ") })),
      ...filteredReportUnits.filter((row) => !row.station_code || !row.license_fee).map((row) => ({ ...row, action_type: "Unit Data Issue", module: "units", action_key: row.unit_no, problem: !row.station_code ? "Missing station code" : "Missing license fee" })),
      ...filteredReportEarnings.filter((row) => /pending/i.test(pretty(row.receipt_type))).map((row) => ({ ...row, action_type: "Pending Receipt", module: "earnings", action_key: row.receipt_key || row.earning_key, problem: "Receipt pending" })),
      ...filteredReportWorks.filter((row) => !/complete|done/i.test(pretty(row.status))).map((row) => ({ ...row, action_type: "Open Work", module: "works", action_key: row.project_id, problem: pretty(row.status) })),
    ];
    return rows;
  }, [filteredReportAlerts, filteredReportUnits, filteredReportEarnings, filteredReportWorks]);

  const reportCards = [
    { icon: TrainFront, label: "Stations Covered", value: reports?.stations?.total ?? 0, subtext: `${reports?.stations?.with_units ?? 0} with units, ${reports?.stations?.with_works ?? 0} with works` },
    { icon: Users, label: "Active Units", value: reports?.units?.active ?? 0, subtext: "Units treated as active for fee reporting" },
    { icon: Wallet, label: "License Fee Collected", value: money(reports?.earnings?.license_fee_collected ?? 0), subtext: "All license fee receipts captured" },
    { icon: Wrench, label: "Open Works", value: reports?.works?.pending ?? 0, subtext: "Works not marked complete/done" },
    { icon: CircleAlert, label: "Critical Alerts", value: reports?.overview?.critical_alerts ?? 0, subtext: "Overdue or needs-review license fee cases" },
    { icon: TrendingUp, label: "Overdue Estimate", value: money(reports?.license_fee_alerts?.estimated_overdue_amount ?? 0), subtext: "Estimated from license fee and pending months" },
  ];

  const reportTabs = [
    { value: "overview", label: "Overview", icon: BarChart3 },
    { value: "stations", label: "Stations", icon: TrainFront },
    { value: "units", label: "Units", icon: Users },
    { value: "earnings", label: "Earnings", icon: Wallet },
    { value: "works", label: "Works", icon: Wrench },
    { value: "actions", label: "Needs Action", icon: CircleAlert },
    { value: "quality", label: "Quality", icon: CircleAlert },
    { value: "alerts", label: "Alerts", icon: Timer },
  ];

  const dashboardCards = [
    { key: "stations", icon: TrainFront, label: "Stations", subtext: "Registered stations in the database" },
    { key: "units", icon: Users, label: "Contracts", subtext: "Catering stalls and vending contracts" },
    { key: "works", icon: Wrench, label: "Works", subtext: "Sanctioned work records" },
    { key: "earningsTotal", icon: Wallet, label: "Contract Revenue", subtext: "Payments captured inside catering units", money: true },
    { key: "completedWorks", icon: BarChart3, label: "Completed Works", subtext: "Works with complete/done status" },
    { key: "pendingWorks", icon: CircleAlert, label: "Pending Works", subtext: "Open or unfinished work items" },
  ];

  const amenityCount = filteredAmenities[amenityTab]?.length || 0;
  const contractCount = filteredContracts[contractTab]?.length || 0;
  const aiRows = Array.isArray(aiResult?.rows) ? aiResult.rows : [];
  const dashboardCount = view === "stations" ? filteredStations.length : view === "contracts" ? contractCount : view === "units" ? filteredUnits.length : view === "earnings" ? filteredEarnings.length : view === "works" ? filteredWorks.length : view === "amenities" ? amenityCount : view === "reports" ? filteredReportAlerts.length : view === "ai" ? aiRows.length : stats?.stations ?? 0;
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
    { key: "licensee_name", label: "Licensee", value: (row) => pretty(row.licensee_name), render: (row) => <span className="font-semibold text-ink">{pretty(row.licensee_name)}</span> },
    { key: "station_code", label: "Station" },
    { key: "type_of_unit", label: "Type" },
    { key: "station_category", label: "Category" },
    { key: "license_fee", label: "Fee" },
    { key: "unit_status", label: "Status", value: (row) => pretty(row.unit_status), render: (row) => <Badge tone={/active/i.test(pretty(row.unit_status)) ? "accent" : "neutral"}>{pretty(row.unit_status)}</Badge> },
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
    { key: "project_id", label: "Project", value: (row) => pretty(row.project_id), render: (row) => <span className="font-black text-blue">{pretty(row.project_id)}</span> },
    { key: "short_name_of_work", label: "Work", value: (row) => pretty(row.short_name_of_work), render: (row) => <span className="line-clamp-2 font-medium text-ink">{pretty(row.short_name_of_work)}</span> },
    { key: "status", label: "Status", value: (row) => pretty(row.status), render: (row) => <Badge tone={/complete|done/i.test(pretty(row.status)) ? "accent" : "neutral"}>{pretty(row.status)}</Badge> },
    { key: "scope_type", label: "Scope" },
    { key: "station_code", label: "Station" },
    { key: "section", label: "Section" },
    { key: "anticipated_expenditure", label: "Cost" },
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
  ];

  const activeReport = (() => {
    if (reportTab === "stations") return { rows: filteredReportStations, columns: stationColumns, fileName: "station-report.xls" };
    if (reportTab === "units") return { rows: filteredReportUnits, columns: unitColumns, fileName: "unit-report.xls" };
    if (reportTab === "earnings") return { rows: filteredReportEarnings, columns: earningColumns, fileName: "earnings-report.xls" };
    if (reportTab === "works") return { rows: filteredReportWorks, columns: workColumns, fileName: "works-report.xls" };
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
    if (view === "works") {
      return {
        title: "Sanctioned Works",
        subtitle: "Passenger amenity sanctioned works with station, division, and ABSS scope handling.",
        filters: [
          ["Scope", filters.workScope, (value) => setFilters((prev) => ({ ...prev, workScope: value })), ["All", "Station", "Division", "ABSS", "Other"]],
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
    return { title: "Dashboard", subtitle: "KPI cards and high-level trends across the dataset.", filters: [] };
  })();

  const buildLocalStationDetail = (station) => {
    const code = station.station_code;
    const stationUnits = units.filter((row) => pretty(row.station_code) === pretty(code));
    const stationEarnings = earnings.filter((row) => pretty(row.station_code) === pretty(code));
    const stationPaWorks = paWorks.filter((row) => pretty(row.station_code) === pretty(code));
    const pfExtensionStatus = paPfExtension.find((row) => pretty(row.station_code) === pretty(code));
    const platformRows = paPlatforms.filter((row) => pretty(row.station_code) === pretty(code));
    const platformLengths = platformRows.map((row) => Number(row.length_m || 0)).filter(Boolean);
    return {
      station,
      contracts: stationUnits.map((unit) => {
        const unitEarnings = earnings.filter((row) => pretty(row.unit_no) === pretty(unit.unit_no));
        return { ...unit, earnings: unitEarnings, earnings_total: unitEarnings.reduce((sum, row) => sum + Number(row.amount || 0), 0), pending_receipts: unitEarnings.filter((row) => /pending/i.test(pretty(row.receipt_type))).length };
      }),
      units: stationUnits,
      earnings: stationEarnings,
      works: works.filter((row) => pretty(row.station_code) === pretty(code) || pretty(row.scope_value) === pretty(code)),
      amenities: {
        summary: paSummary.find((row) => pretty(row.station_code) === pretty(code)),
        infra: paInfra.find((row) => pretty(row.station_code) === pretty(code)),
        platforms: platformRows,
        wheelchairs: paWheelchairs.find((row) => pretty(row.station_code) === pretty(code)),
        trolley: paTrolley.find((row) => pretty(row.station_code) === pretty(code)),
        pf_extension_status: pfExtensionStatus,
        pa_works: stationPaWorks,
        paWorks: stationPaWorks,
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

  const openUnit = (unit) => {
    const no = unit.unit_no;
    setModal({
      open: true,
      type: "unit",
      record: {
        unit,
        earnings: earnings.filter((row) => pretty(row.unit_no) === pretty(no)),
      },
    });
  };

  const openEarning = (earning) => {
    setModal({ open: true, type: "earning", record: { earning } });
  };

  const openWork = (work) => {
    setModal({ open: true, type: "work", record: { work } });
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
    if (reportTab === "works") return openWork(row);
    if (reportTab === "actions") {
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

  const saveReportPreset = () => {
    const name = reportPresetName.trim() || `${reportTabs.find((tab) => tab.value === reportTab)?.label || "Report"} preset`;
    const preset = { id: `${Date.now()}`, name, reportTab, reportFilters };
    setReportPresets((current) => [preset, ...current.filter((item) => item.name !== name)].slice(0, 8));
    setReportPresetName("");
  };

  const applyReportPreset = (preset) => {
    setReportTab(preset.reportTab || "overview");
    setReportFilters({ ...reportFilters, ...(preset.reportFilters || {}) });
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
    const keyValue = formModal.data[key];
    const isEdit = formModal.mode === "edit";
    if (!keyValue) {
      setFormError(`${key} is required`);
      return;
    }
    setFormError("");
    setSaving(true);
    try {
      let response = await fetch(`${API_URL}/api/${path}${isEdit ? `/${encodeURIComponent(keyValue)}` : ""}`, {
        method: isEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formModal.data),
      });
      let payload = await response.json().catch(() => null);
      let savedMessage = isEdit ? "updated" : "created";
      if (!isEdit && response.status === 409) {
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
    <main className="min-h-screen px-3 py-3 text-ink sm:px-4 lg:px-6">
      <section className="mx-auto grid max-w-7xl gap-5 lg:h-[calc(100vh-1.5rem)] lg:grid-cols-[292px_minmax(0,1fr)]">
        <aside className="glass soft-scroll rounded-3xl border p-4 lg:sticky lg:top-3 lg:h-[calc(100vh-1.5rem)] lg:overflow-auto">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.22em] text-accent">Rail dashboard</div>
              <div className="mt-2 text-xl font-black text-ink">Navigation</div>
              <p className="mt-1 text-sm text-muted">Stations, catering units, earnings, and passenger amenities.</p>
            </div>
            <div className="rounded-2xl border border-line bg-surface/80 p-2 text-accent">
              <Database size={18} />
            </div>
          </div>
          <div className="mt-4 space-y-2">
            <NavButton active={view === "dashboard"} icon={BarChart3} label="Dashboard" hint="KPI cards and charts" onClick={() => setView("dashboard")} />
            <NavButton active={view === "stations"} icon={TrainFront} label="Stations" hint="Station master and search" onClick={() => setView("stations")} />
            <NavButton active={view === "contracts"} icon={Wallet} label="Contracts" hint="Catering units and payments" onClick={() => setView("contracts")} />
            <div className="pt-2 text-[11px] font-black uppercase tracking-[0.2em] text-muted">Passenger Amenities</div>
            <NavButton active={view === "amenities"} icon={TrainFront} label="Amenity Infra" hint="Norms, platforms, wheel chairs, trolley paths" onClick={() => setView("amenities")} />
            <NavButton active={view === "works"} icon={Wrench} label="Sanctioned Works" hint="PA sanctioned works and station links" onClick={() => setView("works")} />
            <NavButton active={view === "reports"} icon={FileText} label="Reports" hint="License fee and unit alerts" onClick={() => setView("reports")} />
            <NavButton active={view === "ai"} icon={Bot} label="Ask AI" hint="Talk to any table safely" onClick={() => setView("ai")} />
          </div>
          <div className="mt-5">
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
          </div>
          <Button onClick={loadData} disabled={loading} className="mt-4 w-full">
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            {loading ? "Refreshing..." : "Refresh data"}
          </Button>
          <Button
            variant="secondary"
            onClick={() => setImportModal({ open: true, resource: view === "dashboard" || view === "amenities" ? "stations" : view === "contracts" ? "units" : view, csvText: "", url: "", result: null })}
            className="mt-2 w-full text-accent"
          >
            <UploadCloud size={16} />
            Import CSV
          </Button>
          <Button
            variant="secondary"
            onClick={importPassengerAmenities}
            disabled={loading}
            className="mt-2 w-full text-accent"
          >
            <RefreshCw size={16} className={loading && view === "amenities" ? "animate-spin" : ""} />
            Fetch PA Infra
          </Button>
          <div className="mt-4 rounded-2xl border border-line bg-surface/70 p-3">
            <div className="text-[11px] font-black uppercase tracking-[0.18em] text-muted">Activity</div>
            <div className="mt-1 text-sm font-semibold text-ink">{activityStatus}</div>
            <div className="mt-1 text-xs text-muted">{lastRefreshAt || "No refresh yet"}</div>
          </div>
        </aside>

        <section className="soft-scroll space-y-5 lg:h-full lg:overflow-auto lg:pr-1">
          <div className="glass sticky top-0 z-30 rounded-3xl border p-5">
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

          {view === "dashboard" ? (
            <>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {dashboardCards.map((card) => (
                  <Card
                    key={card.key}
                    icon={card.icon}
                    label={card.label}
                    value={card.money ? money(stats?.[card.key] ?? 0) : card.key === "completedWorks" ? completedWorks : card.key === "pendingWorks" ? pendingWorks : stats?.[card.key] ?? 0}
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
                    <Button size="sm" onClick={importPassengerAmenities} disabled={loading}>
                      <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
                      Fetch PA Infra
                    </Button>
                    <Button variant="secondary" size="sm" onClick={importPfExtensionWorkbook} disabled={loading}>
                      <UploadCloud size={15} />
                      Import PF Extn
                    </Button>
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
              <Panel title="Contracts Workspace" subtitle="Catering units are the contract records. Payments and earnings are reviewed inside the unit/contract context.">
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

          {view === "reports" ? (
            <div className="space-y-4">
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
                    <input type="month" value={reportFilters.month} onChange={(event) => setReportFilters((prev) => ({ ...prev, month: event.target.value }))} className="h-11 w-full rounded-xl border border-line bg-surface px-3 text-sm outline-none focus:border-accent" />
                  </label>
                  <label className="space-y-1">
                    <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">From</span>
                    <input type="date" value={reportFilters.dateFrom} onChange={(event) => setReportFilters((prev) => ({ ...prev, dateFrom: event.target.value }))} className="h-11 w-full rounded-xl border border-line bg-surface px-3 text-sm outline-none focus:border-accent" />
                  </label>
                  <label className="space-y-1">
                    <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">To</span>
                    <input type="date" value={reportFilters.dateTo} onChange={(event) => setReportFilters((prev) => ({ ...prev, dateTo: event.target.value }))} className="h-11 w-full rounded-xl border border-line bg-surface px-3 text-sm outline-none focus:border-accent" />
                  </label>
                  <label className="flex items-end gap-2 rounded-xl border border-line bg-surface/65 px-3 py-2 text-sm font-bold text-ink">
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
                      <select value={reportFilters[key]} onChange={(event) => setReportFilters((prev) => ({ ...prev, [key]: event.target.value }))} className="h-11 w-full rounded-xl border border-line bg-surface px-3 text-sm outline-none focus:border-accent">
                        {options.map((option) => <option key={option} value={option}>{option}</option>)}
                      </select>
                    </label>
                  ))}
                </div>
                <div className="mt-3 flex flex-col gap-3 rounded-2xl border border-line bg-surface/55 p-3 xl:flex-row xl:items-center xl:justify-between">
                  <div className="flex flex-wrap gap-2">
                    {reportPresets.length ? reportPresets.map((preset) => (
                      <button key={preset.id} type="button" onClick={() => applyReportPreset(preset)} className="rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-black text-ink transition hover:border-accent">
                        {preset.name}
                      </button>
                    )) : <span className="text-sm text-muted">No saved report presets yet.</span>}
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <input value={reportPresetName} onChange={(event) => setReportPresetName(event.target.value)} placeholder="Preset name" className="h-10 rounded-xl border border-line bg-surface px-3 text-sm outline-none focus:border-accent" />
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
                <Panel title="Works Reports" subtitle="Status, scope, section, and station-wise work load">
                  <KeyValueGrid
                    rows={[
                      ["Total Works", reports?.works?.total ?? 0],
                      ["Completed", reports?.works?.completed ?? 0],
                      ["Pending/Open", reports?.works?.pending ?? 0],
                    ]}
                  />
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <ReportList
                      rows={(reports?.works?.by_status || []).slice(0, 7)}
                      onSelect={(row) => openDrillDown(`Works: ${row.label}`, filteredReportWorks.filter((work) => pretty(work.status) === pretty(row.label)), workColumns, "works")}
                    />
                    <ReportList
                      rows={(reports?.works?.by_scope || []).slice(0, 7)}
                      onSelect={(row) => openDrillDown(`Works by scope: ${row.label}`, filteredReportWorks.filter((work) => pretty(work.scope_type || work.block_section_station) === pretty(row.label)), workColumns, "works")}
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

              {reportTab !== "overview" ? (
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
                    className="w-full rounded-2xl border border-line bg-surface px-4 py-3 text-sm outline-none placeholder:text-muted focus:border-accent"
                  />
                  <div className="flex flex-wrap gap-2">
                    {aiSuggestions.map((suggestion) => (
                      <button
                        key={suggestion}
                        type="button"
                        onClick={() => submitAiQuery(suggestion)}
                        className="rounded-full border border-line bg-surface/75 px-3 py-1.5 text-xs font-black text-ink transition hover:border-accent hover:bg-surfaceStrong"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                  {aiError ? (
                    <div className="rounded-xl border border-red-300/70 bg-red-500/10 px-3 py-2 text-sm font-semibold text-red-500">
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
                    </div>
                    {aiResult.planner_error || aiResult.answer_error ? (
                      <div className="mt-4 rounded-xl border border-amber-300/70 bg-amber-400/10 px-3 py-2 text-xs font-semibold text-amber-700 dark:text-amber-200">
                        {aiResult.planner_error || aiResult.answer_error}
                      </div>
                    ) : null}
                    {aiResult.sql ? (
                      <pre className="soft-scroll mt-4 overflow-auto rounded-xl border border-line bg-surface p-3 text-xs text-muted">{aiResult.sql}</pre>
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

          {view !== "dashboard" && view !== "reports" && view !== "amenities" && view !== "contracts" && view !== "ai" ? (
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
                      className="group grid gap-3 rounded-xl border border-line bg-surface/85 p-4 text-left transition hover:-translate-y-0.5 hover:border-accent hover:bg-surfaceStrong md:grid-cols-[1.1fr_1fr_1fr_auto]"
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
                  {!filteredReportAlerts.length ? <div className="rounded-xl border border-line bg-surface/85 p-4 text-sm text-muted">No license fee alerts match the current search.</div> : null}
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
                onRowClick={openStation}
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
              <DataTable
                columns={workColumns}
                rows={filteredWorks}
                getKey={(row) => row.work_key || row.project_id}
                onRowClick={openWork}
                emptyTitle="No works match the current search or filters."
                fileName="works-visible.csv"
              />
            ) : null}
          </Panel>
          ) : null}
        </section>
      </section>

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
            columns={{ platformColumns, paWorkColumns, unitColumns, workColumns, normColumns }}
            openAmenity={openAmenity}
            openUnit={openUnit}
            openWork={openWork}
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
                ["Licensee", modal.record.unit.licensee_name],
                ["Station Code", modal.record.unit.station_code],
                ["Station Name", modal.record.unit.station_name],
                ["Category", modal.record.unit.station_category],
                ["Type", modal.record.unit.type_of_unit],
                ["Status", modal.record.unit.unit_status],
                ["License Fee", modal.record.unit.license_fee],
                ["Contract From", modal.record.unit.contract_from],
                ["Contract To", modal.record.unit.contract_to],
              ]}
            />
            <Panel title="Linked Earnings" subtitle="Earnings rows linked by unit number">
              <div className="space-y-2">
                {modal.record.earnings.length ? modal.record.earnings.map((row) => (
                  <button key={row.earning_key || `${row.unit_no}-${row.date_of_receipt}`} type="button" onClick={() => openEarning(row)} className="flex w-full items-start justify-between gap-3 rounded-xl border border-line bg-surface px-3 py-3 text-left hover:border-accent">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-ink">{pretty(row.date_of_receipt)}</div>
                      <div className="mt-0.5 text-xs text-muted">{pretty(row.payment_head)} / {pretty(row.payment_sub_head)}</div>
                    </div>
                    <div className="shrink-0 text-xs text-muted">{money(row.amount)}</div>
                  </button>
                )) : <div className="text-sm text-muted">No linked earnings found.</div>}
              </div>
            </Panel>
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
                ["Station Code", modal.record.earning.station_code],
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
                ["Project ID", modal.record.work.project_id],
                ["Short Name", modal.record.work.short_name_of_work],
                ["Status", modal.record.work.status],
                ["Date of Sanction", modal.record.work.date_of_sanction],
                ["Block Section Station", modal.record.work.block_section_station],
                ["Scope Type", modal.record.work.scope_type],
                ["Scope Value", modal.record.work.scope_value],
                ["Station Code", modal.record.work.station_code],
                ["Section", modal.record.work.section],
                ["Allocation", modal.record.work.allocation],
                ["Anticipated Expenditure", modal.record.work.anticipated_expenditure],
                ["Remarks", modal.record.work.remarks],
              ]}
            />
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
                className="h-11 rounded-xl border border-line bg-surface px-3 text-sm outline-none focus:border-accent"
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
                className="h-11 rounded-xl border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
              />
            </label>
          </div>
          <label className="grid gap-1">
            <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">Google Sheet CSV URL</span>
            <input
              value={importModal.url}
              onChange={(event) => setImportModal((prev) => ({ ...prev, url: event.target.value, csvText: "", result: null }))}
              placeholder="https://docs.google.com/spreadsheets/d/.../gviz/tq?tqx=out:csv&gid=..."
              className="h-11 rounded-xl border border-line bg-surface px-3 text-sm outline-none focus:border-accent"
            />
          </label>
          <label className="grid gap-1">
            <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">CSV Text</span>
            <textarea
              value={importModal.csvText}
              onChange={(event) => setImportModal((prev) => ({ ...prev, csvText: event.target.value, url: "", result: null }))}
              rows={8}
              className="rounded-xl border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
            />
          </label>
          {importModal.result ? (
            <div className="rounded-xl border border-line bg-surface p-3 text-sm">
              <div className="font-bold text-ink">{importModal.result.rows} rows checked - {importModal.result.valid ? "valid" : "errors found"}</div>
              {importModal.result.errors?.length ? (
                <div className="mt-2 max-h-32 overflow-auto text-xs text-red-700">
                  {importModal.result.errors.map((error, index) => (
                    <div key={`${error.row}-${error.field}-${index}`}>Row {error.row}: {error.field} - {error.message}</div>
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
