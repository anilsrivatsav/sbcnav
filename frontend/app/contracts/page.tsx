// @ts-nocheck
"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleAlert, Clock3, FileCheck2, Layers3, Megaphone, Search, Settings, Wallet, X, XCircle } from "lucide-react";
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
    if (row.contract_family !== "publicity") { setSelected(row); return; }
    try { setSelected(await fetchJson(contractRegistryDetailUrl(row.contract_id))); } catch { setSelected(row); }
  };

  return <main className="min-h-screen bg-[#f7f9fc] text-slate-900"><div className="mx-auto grid min-h-screen max-w-[1680px] lg:grid-cols-[232px_minmax(0,1fr)]">
    <aside className="border-r border-slate-200 bg-white p-4 lg:sticky lg:top-0 lg:h-screen"><div className="mb-6 flex items-center gap-3"><div className="rounded-xl bg-indigo-600 p-2 text-white"><Layers3 className="h-5 w-5" /></div><div><div className="text-xs font-black uppercase tracking-[0.18em] text-indigo-600">SBCNAV</div><div className="font-bold">Rail dashboard</div></div></div><div className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Navigation</div><nav className="space-y-1"><a href="/" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50"><Layers3 className="h-4 w-4" />Dashboard</a><a href="/" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50"><Megaphone className="h-4 w-4" />Stations</a><a href="/contracts" className="flex items-center gap-3 rounded-xl bg-indigo-50 px-3 py-2.5 text-sm font-bold text-indigo-700"><Wallet className="h-4 w-4" />Contracts</a><a href="/" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50"><FileCheck2 className="h-4 w-4" />Sanctioned Works</a><a href="/" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50"><Settings className="h-4 w-4" />Settings</a></nav><div className="mt-8 rounded-xl bg-slate-50 p-3 text-xs text-slate-500">PostgreSQL workspace<br /><span className="font-semibold text-emerald-600">Connected</span></div></aside>
    <section className="min-w-0 px-4 py-5 sm:px-6 lg:px-8"><div className="mb-5 flex flex-wrap items-end justify-between gap-4"><div><p className="mb-1 text-[10px] font-black uppercase tracking-[0.24em] text-indigo-600">SBCNAV · Contract operations</p><h1 className="text-2xl font-semibold tracking-tight">Publicity and catering</h1><p className="mt-1 text-sm text-slate-500">Contracts loaded from the PostgreSQL workspace.</p></div><button onClick={load} className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white shadow-sm">Refresh data</button></div>
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-2 shadow-sm">{categories.map(([key, label, Icon]) => <button key={key} onClick={() => { setCategory(key); setPublicityPolicy("all"); if (key !== "publicity") setStatus("all"); if (key === "catering") { setCateringStatus("running"); setCateringType("all"); } }} className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold ${category === key ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}><Icon className="h-3.5 w-3.5" />{label}<span className="opacity-75">{counts[key]}</span></button>)}</div>
    <div className="mb-3 flex flex-wrap items-center gap-1.5 rounded-xl border border-slate-200 bg-white p-2 shadow-sm">{category === "publicity" && statuses.map(([key, label]) => <button key={key} onClick={() => { setStatus(key); setPublicityPolicy("all"); }} className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${status === key ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}{category === "catering" && [["running", "Running / Active", cateringRunningRows.length], ["unawarded", "Unawarded / Other", datasets.catering.filter((row) => row.status === "unawarded").length]].map(([key, label, count]) => <button key={key} onClick={() => { setCateringStatus(key); setCateringType("all"); }} className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${cateringStatus === key ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label} {count}</button>)}<label className="relative ml-auto min-w-[220px] flex-1 sm:max-w-sm"><Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search contracts, station, train, policy..." className="w-full rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-8 pr-2.5 text-xs outline-none focus:border-indigo-400" /></label></div>
    {category === "publicity" && status === "running" && <div className="mb-3 flex flex-wrap items-center gap-1.5 rounded-xl border border-slate-200 bg-white p-2 shadow-sm"><span className="mr-1 text-[10px] font-black uppercase tracking-wide text-slate-500">Policy</span><button onClick={() => setPublicityPolicy("all")} className={`rounded-lg px-2.5 py-1.5 text-[11px] font-bold ${publicityPolicy === "all" ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>All {runningPublicityRows.length}</button>{publicityPolicies.map(({ policy, count }) => <button key={policy} onClick={() => setPublicityPolicy(policy)} className={`rounded-lg px-2.5 py-1.5 text-[11px] font-bold ${publicityPolicy === policy ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{policy} {count}</button>)}</div>}
    {category === "catering" && cateringStatus === "running" && <div className="mb-3 flex flex-wrap items-center gap-1.5 rounded-xl border border-slate-200 bg-white p-2 shadow-sm"><span className="mr-1 text-[10px] font-black uppercase tracking-wide text-slate-500">Type</span><button onClick={() => setCateringType("all")} className={`rounded-lg px-2.5 py-1.5 text-[11px] font-bold ${cateringType === "all" ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>All types {cateringRunningRows.length}</button>{cateringTypes.map((type) => <button key={type} onClick={() => setCateringType(type)} className={`rounded-lg px-2.5 py-1.5 text-[11px] font-bold ${cateringType === type ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{type} {cateringRunningRows.filter((row) => String(row.type_of_unit || "").toLowerCase() === type.toLowerCase()).length}</button>)}</div>}
    {error && <div className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"><CircleAlert className="mr-2 inline h-4 w-4" />{error}</div>}
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><div className="font-semibold">{category === "all" ? "All contracts" : `${titleCase(category)} contracts`}</div><div className="text-sm text-slate-500">{loading ? "Loading all families..." : `${visibleRows.length} records`}</div></div><div className="overflow-x-auto"><table className="w-full min-w-[1000px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Contract</th><th className="px-5 py-3">Family</th><th className="px-5 py-3">Contractor</th><th className="px-5 py-3">Asset</th><th className="px-5 py-3">Policy / category</th><th className="px-5 py-3">Period</th><th className="px-5 py-3 text-right">Value</th></tr></thead><tbody className="divide-y divide-slate-100">{visibleRows.map((row) => <tr key={`${row.contract_family}-${row.contract_id}`} onClick={() => openDetail(row)} className="cursor-pointer hover:bg-indigo-50/40"><td className="px-5 py-4"><div className="font-semibold text-slate-900">{row.contract_name || "Unnamed contract"}</div><div className="mt-1 text-xs text-slate-500">{row.contract_number || row.assets?.[0]?.asset_name || "No reference"} · <span className="capitalize">{row.status || "unknown"}</span></div></td><td className="px-5 py-4"><span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-bold capitalize text-indigo-700">{row.contract_family}</span></td><td className="px-5 py-4 text-slate-600">{row.contractor?.legal_name || "—"}</td><td className="px-5 py-4 text-slate-600">{row.assets?.[0]?.station_code || row.assets?.[0]?.train_number || row.assets?.[0]?.asset_name || "Other"}</td><td className="px-5 py-4"><div>{row.policy_code || "—"}</div><div className="mt-1 text-xs text-slate-500">{row.category || row.contract_family}</div></td><td className="px-5 py-4 text-slate-600">{date(row.period?.start)}<br />to {date(row.period?.end)}</td><td className="px-5 py-4 text-right font-semibold">{money(row.financials?.total_contract_value || row.financials?.annual_license_fee)}</td></tr>)}</tbody></table></div>{!loading && !visibleRows.length && <div className="p-12 text-center text-sm text-slate-500">No contracts match this view.</div>}</div>
    {selected && <div className="fixed inset-0 z-20 flex justify-end bg-slate-900/20" onClick={() => setSelected(null)}><aside onClick={(e) => e.stopPropagation()} className="h-full w-full max-w-xl overflow-y-auto bg-white p-7 shadow-2xl"><div className="mb-7 flex items-start justify-between"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-600">{titleCase(selected.contract_family)} detail</p><h2 className="mt-2 text-2xl font-semibold">{selected.contract_name}</h2></div><button onClick={() => setSelected(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X /></button></div><div className="grid grid-cols-2 gap-3">{[["Status", selected.status], ["Family", selected.contract_family], ["Policy", selected.policy_code], ["Contractor", selected.contractor?.legal_name], ["Start", date(selected.period?.start)], ["End", date(selected.period?.end)], ["Annual fee", money(selected.financials?.annual_license_fee)], ["Total value", money(selected.financials?.total_contract_value)]].map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 font-semibold">{value || "—"}</div></div>)}</div><h3 className="mb-3 mt-8 font-semibold">Assets</h3>{(selected.assets || []).map((asset, index) => <div key={index} className="mb-2 rounded-xl border border-slate-200 p-3 text-sm">{asset.station_code || asset.train_number || asset.asset_name || asset.raw_asset_value}<span className="ml-2 text-xs text-slate-500">{asset.asset_type}</span></div>)}</aside></div>}
  </section></div></main>;
}
