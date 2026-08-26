// @ts-nocheck
"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleAlert, Clock3, Eye, FileCheck2, Layers3, Megaphone, Pencil, Plus, Search, Settings, Wallet, X, XCircle } from "lucide-react";
import { API_URL, contractRegistryDetailUrl, contractSummaryUrl, contractsUrl, fetchJson } from "../../lib/api";

const numberValue = (value) => Number(String(value ?? 0).replace(/[₹,\s]/g, "")) || 0;
const money = (value) => `₹${numberValue(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
const date = (value) => value ? new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";
const titleCase = (value) => String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const cacheKey = "sbcnav-contracts-workspace-v1";
const activeCateringUnit = (row = {}) => {
  const status = String(row.unit_status || "").toLowerCase();
  const available = status === "available" || (!String(row.licensee_name || "").trim() && !String(row.contract_from || "").trim() && !String(row.contract_to || "").trim());
  return !available && !/no offers|scheduled|tender|under process|cancelled|not awarded|no train service/.test(status);
};
const categories = [
  ["all", "All contracts", Layers3, "Every contract family"],
  ["publicity", "Publicity", Megaphone, "Station, train, audio and other publicity"],
  ["catering", "Catering", Wallet, "Catering units and licensees"],
];
const statuses = [["all", "All"], ["running", "Running"], ["completed", "Completed"], ["cancelled", "Cancelled"]];

function normalizeRows(category, payload) {
  const items = payload?.data?.items || payload?.items || [];
  if (category === "publicity") return items.map((row) => ({ ...row, contract_family: "publicity" }));
  return items.map((row) => category === "commercial" ? {
    contract_id: `commercial-${row.contract_key}`, contract_name: row.contract_name, status: row.renewal_status || row.tender_status || "running", contract_family: "commercial", policy_code: row.policy, category: row.sub_category, contractor: { legal_name: row.licensee_name }, assets: [{ asset_type: row.asset_scope || "station", station_code: row.station_code || row.raw_station_value, asset_name: row.asset_scope }], period: { start: row.contract_period_from, end: row.contract_upto }, financials: { annual_license_fee: row.annual_license_fee, total_contract_value: row.total_license_fee_2026_2027 }, raw: row,
  } : {
    contract_id: `catering-${row.unit_no}`, contract_name: row.type_of_unit || row.unit_no, status: activeCateringUnit(row) ? "running" : "unawarded", contract_family: "catering", category: row.station_category, type_of_unit: row.type_of_unit, contractor: { legal_name: row.licensee_name }, assets: [{ asset_type: "station unit", station_code: row.station_code, asset_name: row.unit_no }], period: { start: row.contract_from, end: row.contract_to }, financials: { total_contract_value: row.license_fee }, raw: row,
  });
}

export default function ContractsPage() {
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("all");
  const [publicityPolicy, setPublicityPolicy] = useState("all");
  const [cateringStatus, setCateringStatus] = useState("running");
  const [cateringType, setCateringType] = useState("all");
  const [search, setSearch] = useState("");
  const [datasets, setDatasets] = useState({ publicity: [], catering: [] });
  const [summary, setSummary] = useState({ counts: {} });
  const [selected, setSelected] = useState(null);
  const [paymentLoading, setPaymentLoading] = useState(false);
  const [editor, setEditor] = useState(null);
  const [compactView, setCompactView] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true); setError("");
    let payload;
    let lastError;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        payload = await Promise.all([
          fetchJson(contractsUrl({ status: "all", search: "", pageSize: 5000 })),
          fetchJson(contractSummaryUrl()),
          fetchJson(`${API_URL}/api/units?page=1&page_size=5000`),
        ]);
        break;
      } catch (err) {
        lastError = err;
        if (attempt < 2) await new Promise((resolve) => setTimeout(resolve, 1200 * (attempt + 1)));
      }
    }
    if (!payload) { setError(lastError?.message || "Could not load contracts"); }
    else {
      const [publicity, totals, catering] = payload;
      const nextDatasets = { publicity: normalizeRows("publicity", publicity), catering: normalizeRows("catering", catering) };
      setDatasets(nextDatasets);
      setSummary(totals || { counts: {} });
      try { window.localStorage.setItem(cacheKey, JSON.stringify({ datasets: nextDatasets, summary: totals || { counts: {} } })); } catch { /* Ignore cache quota errors. */ }
    }
    setLoading(false);
  };

  useEffect(() => {
    try {
      const cached = JSON.parse(window.localStorage.getItem(cacheKey) || "null");
      if (cached?.datasets) { setDatasets(cached.datasets); setSummary(cached.summary || { counts: {} }); setLoading(false); }
    } catch { /* Ignore stale or unavailable browser cache. */ }
    load();
  }, []);

  const counts = { all: datasets.publicity.length + datasets.catering.length, publicity: datasets.publicity.length, catering: datasets.catering.length };
  const rows = category === "all" ? [...datasets.publicity, ...datasets.catering] : datasets[category] || [];
  const runningPublicityRows = datasets.publicity.filter((row) => String(row.status || "").toLowerCase() === "running");
  const publicityPolicies = [...new Set(runningPublicityRows.map((row) => String(row.policy_code || row.raw?.policy_code || row.raw?.policy || "").trim()).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b))
    .map((policy) => ({ policy, count: runningPublicityRows.filter((row) => String(row.policy_code || row.raw?.policy_code || row.raw?.policy || "").trim() === policy).length }));
  const visibleRows = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return rows.filter((row) => {
      const statusOk = category === "publicity"
        ? status === "all" || String(row.status || "").toLowerCase() === status
        : category !== "catering" || String(row.status || "").toLowerCase() === cateringStatus;
      const policyOk = category !== "publicity" || publicityPolicy === "all" || (status === "running" && String(row.policy_code || row.raw?.policy_code || row.raw?.policy || "").trim() === publicityPolicy);
      const typeOk = category !== "catering" || cateringType === "all" || String(row.type_of_unit || "").toLowerCase() === cateringType.toLowerCase();
      return statusOk && policyOk && typeOk && (!needle || JSON.stringify(row).toLowerCase().includes(needle));
    });
  }, [rows, search, category, status, publicityPolicy, cateringStatus, cateringType]);
  const cateringRunningRows = datasets.catering.filter((row) => row.status === "running");
  const cateringTypes = [...new Set(cateringRunningRows.map((row) => String(row.type_of_unit || "").trim()).filter(Boolean))].sort();
  const openDetail = async (row) => {
    setSelected(row); setPaymentLoading(true);
    try {
      if (row.contract_family === "publicity") {
        setSelected(await fetchJson(contractRegistryDetailUrl(row.contract_id)));
      } else {
        const unitNo = row.raw?.unit_no || row.contract_id.replace(/^catering-/, "");
        const earnings = await fetchJson(`${API_URL}/api/earnings?unit_no=${encodeURIComponent(unitNo)}&page=1&page_size=5000`);
        setSelected({ ...row, payments: earnings.items || [] });
      }
    } catch { setSelected(row); }
    finally { setPaymentLoading(false); }
  };
  const openEditor = (row = null) => setEditor(row || { contract_family: category === "catering" ? "catering" : "publicity", contract_name: "", contract_number: "", policy_code: "", contractor: { legal_name: "" }, assets: [{ station_code: "" }] });
  const closeSheets = () => { setSelected(null); setEditor(null); };

  return <main className="min-h-screen bg-[#f7f9fc] text-slate-900"><div className="mx-auto grid min-h-screen max-w-[1680px] lg:grid-cols-[232px_minmax(0,1fr)]">
    <aside className="border-r border-slate-200 bg-white p-4 lg:sticky lg:top-0 lg:h-screen"><div className="mb-6 flex items-center gap-3"><div className="rounded-xl bg-indigo-600 p-2 text-white"><Layers3 className="h-5 w-5" /></div><div><div className="text-xs font-black uppercase tracking-[0.18em] text-indigo-600">SBCNAV</div><div className="font-bold">Rail dashboard</div></div></div><div className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Navigation</div><nav className="space-y-1"><a href="/" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50"><Layers3 className="h-4 w-4" />Dashboard</a><a href="/" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50"><Megaphone className="h-4 w-4" />Stations</a><a href="/contracts" className="flex items-center gap-3 rounded-xl bg-indigo-50 px-3 py-2.5 text-sm font-bold text-indigo-700"><Wallet className="h-4 w-4" />Contracts</a><a href="/" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50"><FileCheck2 className="h-4 w-4" />Sanctioned Works</a><a href="/" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50"><Settings className="h-4 w-4" />Settings</a></nav><div className="mt-8 rounded-xl bg-slate-50 p-3 text-xs text-slate-500">PostgreSQL workspace<br /><span className="font-semibold text-emerald-600">Connected</span></div></aside>
    <section className="soft-scroll min-w-0 space-y-4 px-3 py-3 sm:px-5 sm:py-4 lg:px-8 lg:py-6"><div className="soft-surface sticky top-0 z-10 rounded-xl border border-line p-4"><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="mb-1 text-[10px] font-black uppercase tracking-[0.24em] text-accent">SBCNAV · Contract operations</p><h1 className="text-2xl font-black tracking-tight text-ink">Publicity and catering</h1><p className="mt-1 text-sm text-muted">Contracts, payment history, and actions from PostgreSQL.</p></div><div className="flex gap-2"><button onClick={() => openEditor()} className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg border border-accent bg-accent px-3 text-xs font-extrabold text-white"><Plus className="h-4 w-4" />Add new</button><button onClick={load} className="soft-control focus-ring inline-flex h-9 items-center gap-2 rounded-lg border border-line px-3 text-xs font-extrabold text-ink">Refresh data</button></div></div>
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-2 shadow-sm">{categories.map(([key, label, Icon]) => <button key={key} onClick={() => { setCategory(key); setPublicityPolicy("all"); if (key !== "publicity") setStatus("all"); if (key === "catering") { setCateringStatus("running"); setCateringType("all"); } }} className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold ${category === key ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}><Icon className="h-3.5 w-3.5" />{label}<span className="opacity-75">{counts[key]}</span></button>)}</div>
    <div className="mb-3 flex flex-wrap items-center gap-1.5 rounded-xl border border-slate-200 bg-white p-2 shadow-sm">{category === "publicity" && statuses.map(([key, label]) => <button key={key} onClick={() => { setStatus(key); setPublicityPolicy("all"); }} className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${status === key ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}{category === "catering" && [["running", "Running / Active", cateringRunningRows.length], ["unawarded", "Unawarded / Other", datasets.catering.filter((row) => row.status === "unawarded").length]].map(([key, label, count]) => <button key={key} onClick={() => { setCateringStatus(key); setCateringType("all"); }} className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${cateringStatus === key ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label} {count}</button>)}<label className="relative ml-auto min-w-[220px] flex-1 sm:max-w-sm"><Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search contracts, station, train, policy..." className="w-full rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-8 pr-2.5 text-xs outline-none focus:border-indigo-400" /></label></div>
    {category === "publicity" && status === "running" && <div className="mb-3 flex flex-wrap items-center gap-1.5 rounded-xl border border-slate-200 bg-white p-2 shadow-sm"><span className="mr-1 text-[10px] font-black uppercase tracking-wide text-slate-500">Policy</span><button onClick={() => setPublicityPolicy("all")} className={`rounded-lg px-2.5 py-1.5 text-[11px] font-bold ${publicityPolicy === "all" ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>All {runningPublicityRows.length}</button>{publicityPolicies.map(({ policy, count }) => <button key={policy} onClick={() => setPublicityPolicy(policy)} className={`rounded-lg px-2.5 py-1.5 text-[11px] font-bold ${publicityPolicy === policy ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{policy} {count}</button>)}</div>}
    {category === "catering" && cateringStatus === "running" && <div className="mb-3 flex flex-wrap items-center gap-1.5 rounded-xl border border-slate-200 bg-white p-2 shadow-sm"><span className="mr-1 text-[10px] font-black uppercase tracking-wide text-slate-500">Type</span><button onClick={() => setCateringType("all")} className={`rounded-lg px-2.5 py-1.5 text-[11px] font-bold ${cateringType === "all" ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>All types {cateringRunningRows.length}</button>{cateringTypes.map((type) => <button key={type} onClick={() => setCateringType(type)} className={`rounded-lg px-2.5 py-1.5 text-[11px] font-bold ${cateringType === type ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{type} {cateringRunningRows.filter((row) => String(row.type_of_unit || "").toLowerCase() === type.toLowerCase()).length}</button>)}</div>}
    </div>
    {error && <div className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"><CircleAlert className="mr-2 inline h-4 w-4" />{error}</div>}
    <div className="soft-surface overflow-hidden rounded-xl border border-line"><div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3"><div><div className="font-black text-ink">{category === "all" ? "All contracts" : `${titleCase(category)} contracts`}</div><div className="text-xs text-muted">{loading ? "Loading all families..." : `${visibleRows.length} records`}</div></div><div className="flex gap-2"><button onClick={() => setCompactView((value) => !value)} className="soft-control rounded-lg border border-line px-2.5 py-1.5 text-[11px] font-black text-ink">{compactView ? "Detailed view" : "Compact view"}</button><button onClick={() => openEditor()} className="soft-control inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-[11px] font-black text-ink"><Plus className="h-3.5 w-3.5" />Add</button></div></div><div className="soft-scroll max-h-[64vh] overflow-auto"><table className="w-full min-w-[1100px] text-left text-sm"><thead className="sticky top-0 z-10 bg-surfaceStrong text-[11px] uppercase tracking-[0.14em] text-muted"><tr><th className="border-b border-line px-3 py-2">Contract</th><th className="border-b border-line px-3 py-2">Family</th><th className="border-b border-line px-3 py-2">Contractor</th><th className="border-b border-line px-3 py-2">Asset</th><th className="border-b border-line px-3 py-2">Policy / category</th><th className="border-b border-line px-3 py-2">Period</th><th className="border-b border-line px-3 py-2 text-right">Value</th><th className="border-b border-line px-3 py-2 text-right">Actions</th></tr></thead><tbody>{visibleRows.map((row) => <tr key={`${row.contract_family}-${row.contract_id}`} onClick={() => openDetail(row)} className="cursor-pointer border-b border-line/70 transition hover:bg-accentSoft/60"><td className={compactView ? "px-3 py-2" : "px-4 py-4"}><div className="font-black text-ink">{row.contract_name || "Unnamed contract"}</div><div className="mt-1 text-xs text-muted">{row.contract_number || row.assets?.[0]?.asset_name || "No reference"} · <span className="capitalize">{row.status || "unknown"}</span></div></td><td className={compactView ? "px-3 py-2" : "px-4 py-4"}><span className="rounded-full border border-accent/30 bg-accentSoft px-2 py-1 text-[10px] font-black uppercase tracking-wide text-accentStrong">{row.contract_family}</span></td><td className={compactView ? "px-3 py-2 text-xs" : "px-4 py-4 text-sm"}>{row.contractor?.legal_name || "—"}</td><td className={compactView ? "px-3 py-2 text-xs" : "px-4 py-4 text-sm"}>{row.assets?.[0]?.station_code || row.assets?.[0]?.train_number || row.assets?.[0]?.asset_name || "Other"}</td><td className={compactView ? "px-3 py-2 text-xs" : "px-4 py-4 text-sm"}><div>{row.policy_code || "—"}</div><div className="mt-1 text-xs text-muted">{row.category || row.contract_family}</div></td><td className={compactView ? "px-3 py-2 text-xs" : "px-4 py-4 text-sm"}>{date(row.period?.start)}<br />to {date(row.period?.end)}</td><td className={(compactView ? "px-3 py-2" : "px-4 py-4") + " text-right font-black"}>{money(row.financials?.total_contract_value || row.financials?.annual_license_fee)}</td><td className={compactView ? "px-3 py-2" : "px-4 py-4"}><div className="flex justify-end gap-1"><button aria-label="View" title="View" onClick={(event) => { event.stopPropagation(); openDetail(row); }} className="soft-control rounded-md border border-line p-1.5 text-muted hover:text-accent"><Eye className="h-3.5 w-3.5" /></button><button aria-label="Edit" title="Edit" onClick={(event) => { event.stopPropagation(); openEditor(row); }} className="soft-control rounded-md border border-line p-1.5 text-muted hover:text-accent"><Pencil className="h-3.5 w-3.5" /></button></div></td></tr>)}</tbody></table></div>{!loading && !visibleRows.length && <div className="p-12 text-center text-sm text-muted">No contracts match this view.</div>}</div>
    {selected && <div className="fixed inset-0 z-20 flex justify-end bg-slate-900/30" onClick={() => setSelected(null)}><aside onClick={(e) => e.stopPropagation()} className="soft-scroll h-full w-full max-w-2xl overflow-y-auto bg-[var(--page-background)] p-5 shadow-2xl"><div className="soft-surface mb-4 rounded-xl border p-4"><div className="flex items-start justify-between gap-4"><div><p className="text-[10px] font-black uppercase tracking-[0.2em] text-accent">{titleCase(selected.contract_family)} detail</p><h2 className="mt-1 text-xl font-black text-ink">{selected.contract_name || "Contract detail"}</h2><p className="mt-1 text-xs text-muted">{selected.contract_number || selected.contract_id}</p></div><button onClick={() => setSelected(null)} className="soft-control rounded-lg border border-line p-2 text-muted hover:text-ink"><X className="h-4 w-4" /></button></div></div><div className="grid grid-cols-2 gap-2 sm:grid-cols-3">{[["Status", selected.status], ["Policy", selected.policy_code], ["Contractor", selected.contractor?.legal_name], ["Start", date(selected.period?.start)], ["End", date(selected.period?.end)], ["Total value", money(selected.financials?.total_contract_value)]].map(([label, value]) => <div key={label} className="soft-surface rounded-lg border p-3"><div className="text-[10px] font-black uppercase tracking-wide text-muted">{label}</div><div className="mt-1 text-sm font-black text-ink">{value || "—"}</div></div>)}</div><div className="soft-surface mt-4 rounded-xl border p-4"><div className="flex items-center justify-between gap-3"><div><h3 className="text-sm font-black uppercase tracking-[0.16em] text-ink">Payment details</h3><p className="mt-1 text-xs text-muted">Recorded payments and payment schedule for this contract.</p></div>{paymentLoading && <span className="text-xs font-bold text-muted">Loading…</span>}</div>{!paymentLoading && (selected.payments || []).length ? <div className="mt-3 space-y-2">{selected.payments.map((payment, index) => <div key={payment.payment_id || payment.receipt_key || index} className="soft-inset flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line px-3 py-2 text-xs"><span className="font-black text-ink">{date(payment.payment_date || payment.date_of_receipt || payment.payment_month)}</span><span className="font-black text-ink">{money(payment.amount_paid ?? payment.amount)}</span><span className="text-muted">{payment.payment_status || payment.receipt_type || payment.payment_head || "Recorded"}</span></div>)}</div> : !paymentLoading ? <div className="mt-3 text-sm text-muted">No recorded payment entries for this contract.</div> : null}</div><div className="soft-surface mt-4 rounded-xl border p-4"><h3 className="text-sm font-black uppercase tracking-[0.16em] text-ink">Assets</h3>{(selected.assets || []).map((asset, index) => <div key={index} className="mt-2 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink">{asset.station_code || asset.train_number || asset.asset_name || asset.raw_asset_value}<span className="ml-2 text-xs text-muted">{asset.asset_type}</span></div>)}</div></aside></div>}
    {editor && <div className="fixed inset-0 z-20 flex justify-end bg-slate-900/30" onClick={() => setEditor(null)}><aside onClick={(e) => e.stopPropagation()} className="soft-scroll h-full w-full max-w-xl overflow-y-auto bg-[var(--page-background)] p-5 shadow-2xl"><div className="soft-surface rounded-xl border p-4"><div className="flex items-center justify-between"><div><p className="text-[10px] font-black uppercase tracking-[0.2em] text-accent">{editor.contract_id ? "Edit contract" : "New contract"}</p><h2 className="mt-1 text-xl font-black text-ink">Contract action</h2></div><button onClick={() => setEditor(null)} className="soft-control rounded-lg border border-line p-2"><X className="h-4 w-4" /></button></div><div className="mt-5 space-y-3"><label className="block text-xs font-black uppercase tracking-wide text-muted">Contract name<input value={editor.contract_name || ""} onChange={(e) => setEditor({ ...editor, contract_name: e.target.value })} className="soft-inset mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm font-semibold text-ink outline-none" /></label><label className="block text-xs font-black uppercase tracking-wide text-muted">Contract number<input value={editor.contract_number || ""} onChange={(e) => setEditor({ ...editor, contract_number: e.target.value })} className="soft-inset mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm font-semibold text-ink outline-none" /></label><label className="block text-xs font-black uppercase tracking-wide text-muted">Policy<input value={editor.policy_code || ""} onChange={(e) => setEditor({ ...editor, policy_code: e.target.value })} className="soft-inset mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm font-semibold text-ink outline-none" /></label><label className="block text-xs font-black uppercase tracking-wide text-muted">Contractor<input value={editor.contractor?.legal_name || ""} onChange={(e) => setEditor({ ...editor, contractor: { ...(editor.contractor || {}), legal_name: e.target.value } })} className="soft-inset mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm font-semibold text-ink outline-none" /></label></div><div className="mt-6 flex justify-end gap-2"><button onClick={() => setEditor(null)} className="soft-control rounded-lg border border-line px-3 py-2 text-xs font-black">Close</button><button onClick={() => setEditor(null)} className="rounded-lg bg-accent px-3 py-2 text-xs font-black text-white">Save draft</button></div><p className="mt-3 text-[11px] text-muted">Contract registry writes are managed through the PostgreSQL import workflow in Settings. This form preserves an editable draft without changing source data.</p></div></aside></div>}
  </section></div></main>;
}
