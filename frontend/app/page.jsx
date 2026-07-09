"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  CircleAlert,
  ChevronRight,
  RefreshCw,
  Search,
  TrainFront,
  TrendingUp,
  Users,
  Wallet,
  X,
  Wrench,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

const money = (value) => `INR ${Number(value || 0).toLocaleString("en-IN")}`;
const pretty = (value) => (value === null || value === undefined || value === "" ? "NA" : String(value));
const toNumber = (value) => Number(value || 0);

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const json = await response.json();
  if (!response.ok || json.success === false) {
    throw new Error(json.message || `Request failed: ${response.status}`);
  }
  return json.data;
}

function Card({ icon: Icon, label, value, subtext }) {
  return (
    <div className="glass rounded-2xl border border-line p-4 shadow-soft">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-black uppercase tracking-[0.18em] text-muted">{label}</div>
          <div className="mt-2 text-2xl font-black text-ink">{value}</div>
        </div>
        <div className="rounded-xl bg-accentSoft p-3 text-[#0b5f59]">
          <Icon size={18} />
        </div>
      </div>
      <div className="mt-3 text-xs font-semibold text-muted">{subtext}</div>
    </div>
  );
}

function Panel({ title, subtitle, action, children }) {
  return (
    <section className="glass rounded-2xl border border-line p-4 shadow-soft">
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
        <circle cx="50" cy="50" r="42" fill="none" stroke="#e5eef3" strokeWidth="12" />
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
      className={`flex w-full items-start gap-3 rounded-xl border px-3 py-3 text-left transition ${
        active ? "border-accent bg-accentSoft text-accent-strong" : "border-line bg-white text-ink hover:border-accent"
      }`}
    >
      <Icon size={17} className="mt-0.5 shrink-0" />
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
        className="h-11 w-full rounded-xl border border-line bg-white pl-10 pr-3 text-sm outline-none placeholder:text-muted focus:border-accent"
        placeholder={placeholder}
      />
    </label>
  );
}

function FilterSelect({ label, value, onChange, options }) {
  return (
    <label className="grid gap-1">
      <span className="text-[11px] font-black uppercase tracking-[0.18em] text-muted">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="h-11 rounded-xl border border-line bg-white px-3 text-sm outline-none focus:border-accent">
        {options.map((item) => (
          <option key={item} value={item}>{item}</option>
        ))}
      </select>
    </label>
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
      <div className="max-h-[92vh] w-full max-w-5xl overflow-hidden rounded-2xl border border-line bg-[#f8fbfd] shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-line bg-white px-4 py-4">
          <div>
            <div className="text-[11px] font-black uppercase tracking-[0.2em] text-accent">Detail view</div>
            <h3 className="mt-1 text-xl font-black text-ink">{title}</h3>
            {subtitle ? <p className="mt-1 text-sm text-muted">{subtitle}</p> : null}
          </div>
          <button type="button" onClick={onClose} className="rounded-full border border-line bg-white p-2 text-ink hover:border-accent">
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
        <div key={label} className="rounded-xl border border-line bg-white p-3">
          <dt className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">{label}</dt>
          <dd className="mt-1 text-sm font-semibold text-ink">{pretty(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function Page() {
  const [stats, setStats] = useState(null);
  const [stations, setStations] = useState([]);
  const [units, setUnits] = useState([]);
  const [earnings, setEarnings] = useState([]);
  const [works, setWorks] = useState([]);
  const [view, setView] = useState("dashboard");
  const [loading, setLoading] = useState(false);
  const [syncStatus, setSyncStatus] = useState("Ready to fetch data");
  const [lastSyncAt, setLastSyncAt] = useState(null);
  const [search, setSearch] = useState({ dashboard: "", stations: "", units: "", earnings: "", works: "" });
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

  const loadData = async () => {
    setLoading(true);
    setSyncStatus("Syncing from Google Sheets...");
    try {
      await fetch(`${API}/api/sync`, { method: "POST" });
      const [statsData, stationsData, unitsData, earningsData, worksData] = await Promise.all([
        fetchJson(`${API}/api/stats`),
        fetchJson(`${API}/api/stations?page=1&page_size=5000&sort_by=station_name`),
        fetchJson(`${API}/api/units?page=1&page_size=5000&sort_by=unit_no`),
        fetchJson(`${API}/api/earnings?page=1&page_size=5000&sort_by=date_of_receipt&sort_order=desc`),
        fetchJson(`${API}/api/works?page=1&page_size=5000&sort_by=project_id`),
      ]);
      setStats(statsData);
      setStations(stationsData.items || []);
      setUnits(unitsData.items || []);
      setEarnings(earningsData.items || []);
      setWorks(worksData.items || []);
      setLastSyncAt(new Date().toLocaleString());
      setSyncStatus("Synced successfully");
    } catch (error) {
      setSyncStatus(error.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setSyncStatus("Ready to fetch data");
  }, []);

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

  const filteredWorks = useMemo(() => {
    const q = search.works.trim().toLowerCase();
    return works.filter((row) => {
      const searchOk = [row.project_id, row.short_name_of_work, row.block_section_station, row.section, row.status].some((value) => pretty(value).toLowerCase().includes(q));
      const scopeOk = filters.workScope === "All" || pretty(row.scope_type || row.block_section_station) === filters.workScope;
      const statusOk = filters.workStatus === "All" || pretty(row.status) === filters.workStatus;
      return searchOk && scopeOk && statusOk;
    });
  }, [works, search.works, filters]);

  const dashboardCards = [
    { key: "stations", icon: TrainFront, label: "Stations", subtext: "Registered stations in the database" },
    { key: "units", icon: Users, label: "Units", subtext: "Catering stalls and vending units" },
    { key: "works", icon: Wrench, label: "Works", subtext: "Sanctioned work records" },
    { key: "earningsTotal", icon: Wallet, label: "Earnings", subtext: "Catering revenue captured from Sheets", money: true },
    { key: "completedWorks", icon: BarChart3, label: "Completed Works", subtext: "Works with complete/done status" },
    { key: "pendingWorks", icon: CircleAlert, label: "Pending Works", subtext: "Open or unfinished work items" },
  ];

  const dashboardCount = view === "stations" ? filteredStations.length : view === "units" ? filteredUnits.length : view === "earnings" ? filteredEarnings.length : view === "works" ? filteredWorks.length : stats?.stations ?? 0;
  const activeSearch = search[view] ?? "";
  const setActiveSearch = (value) => setSearch((prev) => ({ ...prev, [view]: value }));

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
    if (view === "works") {
      return {
        title: "Works",
        subtitle: "Sanctioned works with station, division, and ABSS scope handling.",
        filters: [
          ["Scope", filters.workScope, (value) => setFilters((prev) => ({ ...prev, workScope: value })), ["All", "Station", "Division", "ABSS", "Other"]],
          ["Status", filters.workStatus, (value) => setFilters((prev) => ({ ...prev, workStatus: value })), ["All", ...new Set(works.map((r) => r.status).filter(Boolean).sort())]],
        ],
      };
    }
    return { title: "Dashboard", subtitle: "KPI cards and high-level trends across the dataset.", filters: [] };
  })();

  const openStation = (station) => {
    const code = station.station_code;
    setModal({
      open: true,
      type: "station",
      record: {
        station,
        units: units.filter((row) => pretty(row.station_code) === pretty(code)),
        earnings: earnings.filter((row) => pretty(row.station_code) === pretty(code)),
        works: works.filter((row) => pretty(row.station_code) === pretty(code) || pretty(row.scope_value) === pretty(code)),
      },
    });
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

  const closeModal = () => setModal({ open: false, type: null, record: null });

  return (
    <main className="min-h-screen px-3 py-3 sm:px-4 lg:px-6">
      <section className="mx-auto grid max-w-7xl gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="glass rounded-2xl border border-line p-4 shadow-soft">
          <div className="text-xs font-black uppercase tracking-[0.22em] text-accent">Rail dashboard</div>
          <div className="mt-2 text-xl font-black text-ink">Navigation</div>
          <p className="mt-1 text-sm text-muted">Dashboard, stations, units, earnings, and works.</p>
          <div className="mt-4 space-y-2">
            <NavButton active={view === "dashboard"} icon={BarChart3} label="Dashboard" hint="KPI cards and charts" onClick={() => setView("dashboard")} />
            <NavButton active={view === "stations"} icon={TrainFront} label="Stations" hint="Station master and search" onClick={() => setView("stations")} />
            <NavButton active={view === "units"} icon={Users} label="Units" hint="Catering units linked to stations" onClick={() => setView("units")} />
            <NavButton active={view === "earnings"} icon={Wallet} label="Earnings" hint="Unit payments and dues" onClick={() => setView("earnings")} />
            <NavButton active={view === "works"} icon={Wrench} label="Works" hint="Sanctioned works and links" onClick={() => setView("works")} />
          </div>
          <button type="button" onClick={loadData} disabled={loading} className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-4 py-3 text-sm font-extrabold text-white shadow-soft disabled:cursor-wait disabled:opacity-70">
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            {loading ? "Fetching..." : "Fetch latest data"}
          </button>
          <div className="mt-4 rounded-xl border border-line bg-white p-3">
            <div className="text-[11px] font-black uppercase tracking-[0.18em] text-muted">Sync</div>
            <div className="mt-1 text-sm font-semibold text-ink">{syncStatus}</div>
            <div className="mt-1 text-xs text-muted">{lastSyncAt || "No sync yet"}</div>
          </div>
        </aside>

        <section className="space-y-4">
          <div className="glass rounded-2xl border border-line p-5 shadow-soft">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="text-xs font-black uppercase tracking-[0.22em] text-accent">Rail dashboard</div>
                <h1 className="mt-2 text-3xl font-black tracking-tight text-ink sm:text-4xl">{viewConfig.title}</h1>
                <p className="mt-2 max-w-3xl text-sm text-muted">{viewConfig.subtitle}</p>
              </div>
              <div className="w-full sm:w-[360px]">
                <SearchInput value={activeSearch} onChange={setActiveSearch} placeholder={`Search ${viewConfig.title.toLowerCase()}`} />
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

          <Panel
            title={viewConfig.title}
            subtitle={view === "stations" ? "Station master with filtering and search." : view === "units" ? "Catering units linked to stations." : view === "earnings" ? "Earnings linked to units and station codes." : view === "works" ? "Sanctioned works with scope and status." : "Dashboard summary"}
          >
            <div className="mb-3 text-xs font-semibold text-muted">{view === "dashboard" ? "Summary view" : `${dashboardCount} records shown`}</div>

            {view === "stations" ? (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {filteredStations.slice(0, 12).map((station) => (
                  <button
                    key={station.station_code}
                    type="button"
                    onClick={() => openStation(station)}
                    className="group w-full cursor-pointer rounded-xl border border-line bg-white p-4 text-left transition hover:-translate-y-0.5 hover:border-accent hover:shadow-md"
                    aria-label={`Open station details for ${pretty(station.station_code)}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-xs font-black uppercase tracking-wide text-blue">{station.station_code}</div>
                        <div className="mt-1 font-bold text-ink">{station.station_name}</div>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.16em] text-muted">
                        Open
                        <ChevronRight size={18} className="transition group-hover:translate-x-0.5" />
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted">
                      <div>Division: {pretty(station.division)}</div>
                      <div>Section: {pretty(station.section)}</div>
                      <div>Footfall: {pretty(station.passenger_footfall)}</div>
                      <div>Category: {pretty(station.categorisation)}</div>
                    </div>
                  </button>
                ))}
              </div>
            ) : view === "units" ? (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {filteredUnits.slice(0, 12).map((unit) => (
                  <button
                    key={unit.unit_no}
                    type="button"
                    onClick={() => openUnit(unit)}
                    className="group w-full cursor-pointer rounded-xl border border-line bg-white p-4 text-left transition hover:-translate-y-0.5 hover:border-accent hover:shadow-md"
                    aria-label={`Open unit details for ${pretty(unit.unit_no)}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-xs font-black uppercase tracking-wide text-blue">{unit.unit_no}</div>
                        <div className="mt-1 font-bold text-ink">{pretty(unit.licensee_name)}</div>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.16em] text-muted">
                        Open
                        <ChevronRight size={18} className="transition group-hover:translate-x-0.5" />
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted">
                      <div>Station: {pretty(unit.station_code)}</div>
                      <div>Category: {pretty(unit.station_category)}</div>
                      <div>Type: {pretty(unit.type_of_unit)}</div>
                      <div>Fee: {pretty(unit.license_fee)}</div>
                    </div>
                  </button>
                ))}
              </div>
            ) : view === "earnings" ? (
              <div className="space-y-3">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  <Card icon={Wallet} label="Paid" value={paidEarnings} subtext="Receipts marked paid / received" />
                  <Card icon={CircleAlert} label="Pending" value={pendingEarnings} subtext="Receipts marked pending" />
                  <Card icon={TrendingUp} label="Total" value={earnings.length} subtext="All earning records" />
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {filteredEarnings.slice(0, 12).map((row) => (
                    <button
                      key={row.earning_key || `${row.unit_no}-${row.date_of_receipt}`}
                      type="button"
                      onClick={() => openEarning(row)}
                      className="group w-full cursor-pointer rounded-xl border border-line bg-white p-4 text-left transition hover:-translate-y-0.5 hover:border-accent hover:shadow-md"
                      aria-label={`Open earnings details for ${pretty(row.unit_no)}`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-xs font-black uppercase tracking-wide text-blue">{pretty(row.unit_no)}</div>
                          <div className="mt-1 font-semibold text-ink">{pretty(row.licensee_name)}</div>
                        </div>
                        <div className="flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.16em] text-muted">
                          Open
                          <ChevronRight size={18} className="transition group-hover:translate-x-0.5" />
                        </div>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted">
                        <div>Station: {pretty(row.station_code)}</div>
                        <div>Receipt: {pretty(row.receipt_type)}</div>
                        <div>Head: {pretty(row.payment_head)}</div>
                        <div>Amount: {money(row.amount)}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : view === "works" ? (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {filteredWorks.slice(0, 12).map((work) => (
                  <button
                    key={work.project_id}
                    type="button"
                    onClick={() => openWork(work)}
                    className="group w-full cursor-pointer rounded-xl border border-line bg-white p-4 text-left transition hover:-translate-y-0.5 hover:border-accent hover:shadow-md"
                    aria-label={`Open work details for ${pretty(work.project_id)}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wide text-blue">{work.project_id}</div>
                        <div className="mt-1 text-sm font-semibold text-ink">{pretty(work.short_name_of_work)}</div>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.16em] text-muted">
                        Open
                        <ChevronRight size={18} className="transition group-hover:translate-x-0.5" />
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted">
                      <div>Scope: {pretty(work.scope_type || work.block_section_station)}</div>
                      <div>Station: {pretty(work.station_code)}</div>
                      <div>Section: {pretty(work.section)}</div>
                      <div>Status: {pretty(work.status)}</div>
                    </div>
                  </button>
                ))}
              </div>
            ) : null}
          </Panel>
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
                  : null
        }
        onClose={closeModal}
      >
        {modal.type === "station" ? (
          <div className="space-y-4">
            <KeyValueGrid
              rows={[
                ["Station Code", modal.record.station.station_code],
                ["Station Name", modal.record.station.station_name],
                ["Division", modal.record.station.division],
                ["Section", modal.record.station.section],
                ["Category", modal.record.station.categorisation],
                ["Platform Type", modal.record.station.platform_type],
                ["Footfall", modal.record.station.passenger_footfall],
                ["Passenger Range", modal.record.station.passenger_range],
              ]}
            />
            <div className="grid gap-4 xl:grid-cols-3">
              <Panel title="Linked Units" subtitle="Units using the same station code">
                <div className="space-y-2">
                  {modal.record.units.length ? modal.record.units.map((unit) => (
                    <button key={unit.unit_no} type="button" onClick={() => openUnit(unit)} className="flex w-full items-start justify-between gap-3 rounded-xl border border-line bg-white px-3 py-3 text-left">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-ink">{pretty(unit.unit_no)}</div>
                        <div className="mt-0.5 text-xs text-muted">{pretty(unit.licensee_name)}</div>
                      </div>
                      <div className="shrink-0 text-xs text-muted">{pretty(unit.unit_status)}</div>
                    </button>
                  )) : <div className="text-sm text-muted">No linked units found.</div>}
                </div>
              </Panel>
              <Panel title="Linked Earnings" subtitle="Earnings rows matching station code">
                <div className="space-y-2">
                  {modal.record.earnings.length ? modal.record.earnings.map((row) => (
                    <button key={row.earning_key || `${row.unit_no}-${row.date_of_receipt}`} type="button" onClick={() => openEarning(row)} className="flex w-full items-start justify-between gap-3 rounded-xl border border-line bg-white px-3 py-3 text-left">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-ink">{pretty(row.unit_no)}</div>
                        <div className="mt-0.5 text-xs text-muted">{pretty(row.licensee_name)}</div>
                      </div>
                      <div className="shrink-0 text-xs text-muted">{money(row.amount)}</div>
                    </button>
                  )) : <div className="text-sm text-muted">No linked earnings found.</div>}
                </div>
              </Panel>
              <Panel title="Linked Works" subtitle="Works mapped to this station code">
                <div className="space-y-2">
                  {modal.record.works.length ? modal.record.works.map((work) => (
                    <button key={work.project_id} type="button" onClick={() => openWork(work)} className="flex w-full items-start justify-between gap-3 rounded-xl border border-line bg-white px-3 py-3 text-left">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-ink">{pretty(work.project_id)}</div>
                        <div className="mt-0.5 text-xs text-muted">{pretty(work.short_name_of_work)}</div>
                      </div>
                      <div className="shrink-0 text-xs text-muted">{pretty(work.status)}</div>
                    </button>
                  )) : <div className="text-sm text-muted">No linked works found.</div>}
                </div>
              </Panel>
            </div>
          </div>
        ) : modal.type === "unit" ? (
          <div className="space-y-4">
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
                  <button key={row.earning_key || `${row.unit_no}-${row.date_of_receipt}`} type="button" onClick={() => openEarning(row)} className="flex w-full items-start justify-between gap-3 rounded-xl border border-line bg-white px-3 py-3 text-left">
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
        ) : modal.type === "work" ? (
          <div className="space-y-4">
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
        ) : null}
      </Modal>
    </main>
  );
}
