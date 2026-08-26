// @ts-nocheck
"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleAlert, Clock3, FileCheck2, Layers3, Megaphone, Search, Wallet, X, XCircle } from "lucide-react";
import { API_URL, contractRegistryDetailUrl, contractSummaryUrl, contractsUrl, fetchJson } from "../../lib/api";

const numberValue = (value) => Number(String(value ?? 0).replace(/[₹,\s]/g, "")) || 0;
const money = (value) => `₹${numberValue(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
const date = (value) => value ? new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";
const titleCase = (value) => String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const categories = [
  ["all", "All contracts", Layers3, "Every contract family"],
  ["publicity", "Publicity", Megaphone, "Station, train, audio and other publicity"],
  ["catering", "Catering", Wallet, "Catering units and licensees"],
];
const statuses = [["all", "All"], ["awarded", "Awarded"], ["running", "Running"], ["completed", "Completed"], ["cancelled", "Cancelled"]];

function normalizeRows(category, payload) {
  const items = payload?.data?.items || payload?.items || [];
  if (category === "publicity") return items.map((row) => ({ ...row, contract_family: "publicity" }));
  return items.map((row) => category === "commercial" ? {
    contract_id: `commercial-${row.contract_key}`, contract_name: row.contract_name, status: row.renewal_status || row.tender_status || "running", contract_family: "commercial", policy_code: row.policy, category: row.sub_category, contractor: { legal_name: row.licensee_name }, assets: [{ asset_type: row.asset_scope || "station", station_code: row.station_code || row.raw_station_value, asset_name: row.asset_scope }], period: { start: row.contract_period_from, end: row.contract_upto }, financials: { annual_license_fee: row.annual_license_fee, total_contract_value: row.total_license_fee_2026_2027 }, raw: row,
  } : {
    contract_id: `catering-${row.unit_no}`, contract_name: row.type_of_unit || row.unit_no, status: row.unit_status === "Available" ? "awarded" : "running", contract_family: "catering", category: row.station_category, contractor: { legal_name: row.licensee_name }, assets: [{ asset_type: "station unit", station_code: row.station_code, asset_name: row.unit_no }], period: { start: row.contract_from, end: row.contract_to }, financials: { total_contract_value: row.license_fee }, raw: row,
  });
}

export default function ContractsPage() {
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [datasets, setDatasets] = useState({ publicity: [], catering: [] });
  const [summary, setSummary] = useState({ counts: {} });
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true); setError("");
    try {
      const [publicity, totals, catering] = await Promise.all([
        fetchJson(contractsUrl({ status, search: "", pageSize: 5000 })),
        fetchJson(contractSummaryUrl()),
        fetchJson(`${API_URL}/api/units?page=1&page_size=5000`),
      ]);
      setDatasets({ publicity: normalizeRows("publicity", publicity), catering: normalizeRows("catering", catering) });
      setSummary(totals || { counts: {} });
    } catch (err) { setError(err?.message || "Could not load contracts"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [status]);

  const counts = { all: datasets.publicity.length + datasets.catering.length, publicity: datasets.publicity.length, catering: datasets.catering.length };
  const rows = category === "all" ? [...datasets.publicity, ...datasets.catering] : datasets[category] || [];
  const visibleRows = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return rows.filter((row) => !needle || JSON.stringify(row).toLowerCase().includes(needle));
  }, [rows, search]);
  const statCards = [["Awarded", "awarded", FileCheck2], ["Running", "running", Clock3], ["Completed", "completed", CheckCircle2], ["Cancelled", "cancelled", XCircle]];
  const openDetail = async (row) => {
    if (row.contract_family !== "publicity") { setSelected(row); return; }
    try { setSelected(await fetchJson(contractRegistryDetailUrl(row.contract_id))); } catch { setSelected(row); }
  };

  return <main className="min-h-screen bg-[#f7f9fc] px-5 py-8 text-slate-900 md:px-10"><div className="mx-auto max-w-7xl">
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4"><div><p className="mb-2 text-xs font-bold uppercase tracking-[0.24em] text-indigo-600">SBCNAV · Contract operations</p><h1 className="text-3xl font-semibold tracking-tight">Publicity and catering</h1><p className="mt-2 max-w-3xl text-sm text-slate-500">Publicity and catering are loaded from the same backend workspace. Choose a family or review both together.</p></div><button onClick={load} className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm">Refresh data</button></div>
    <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{categories.map(([key, label, Icon, description]) => <button key={key} onClick={() => { setCategory(key); if (key !== "publicity") setStatus("all"); }} className={`rounded-2xl border p-4 text-left shadow-sm transition hover:-translate-y-0.5 ${category === key ? "border-indigo-400 bg-indigo-600 text-white ring-2 ring-indigo-100" : "border-slate-200 bg-white text-slate-700"}`}><div className="flex items-center justify-between gap-3"><span className="flex items-center gap-2 text-sm font-bold"><Icon className="h-4 w-4" />{label}</span><span className={`rounded-full px-2.5 py-1 text-xs font-bold ${category === key ? "bg-white/20" : "bg-slate-100 text-slate-700"}`}>{counts[key]}</span></div><p className={`mt-3 text-xs ${category === key ? "text-indigo-100" : "text-slate-500"}`}>{description}</p></button>)}</div>
    {category === "publicity" && <div className="mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{statCards.map(([label, key, Icon]) => <button key={key} onClick={() => setStatus(key)} className={`rounded-2xl border bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 ${status === key ? "border-indigo-400 ring-2 ring-indigo-100" : "border-slate-200"}`}><Icon className="mb-4 h-5 w-5 text-indigo-600" /><div className="text-2xl font-semibold">{summary.counts?.[key] || 0}</div><div className="mt-1 text-sm text-slate-500">{label}</div></button>)}</div>}
    <div className="mb-5 flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">{category === "publicity" && statuses.map(([key, label]) => <button key={key} onClick={() => setStatus(key)} className={`rounded-xl px-4 py-2 text-sm font-semibold ${status === key ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}<label className="relative ml-auto min-w-[240px] flex-1 sm:max-w-sm"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search contracts, station, train, policy..." className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm outline-none focus:border-indigo-400" /></label></div>
    {error && <div className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"><CircleAlert className="mr-2 inline h-4 w-4" />{error}</div>}
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><div className="font-semibold">{category === "all" ? "All contracts" : `${titleCase(category)} contracts`}</div><div className="text-sm text-slate-500">{loading ? "Loading all families..." : `${visibleRows.length} records`}</div></div><div className="overflow-x-auto"><table className="w-full min-w-[1000px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Contract</th><th className="px-5 py-3">Family</th><th className="px-5 py-3">Contractor</th><th className="px-5 py-3">Asset</th><th className="px-5 py-3">Policy / category</th><th className="px-5 py-3">Period</th><th className="px-5 py-3 text-right">Value</th></tr></thead><tbody className="divide-y divide-slate-100">{visibleRows.map((row) => <tr key={`${row.contract_family}-${row.contract_id}`} onClick={() => openDetail(row)} className="cursor-pointer hover:bg-indigo-50/40"><td className="px-5 py-4"><div className="font-semibold text-slate-900">{row.contract_name || "Unnamed contract"}</div><div className="mt-1 text-xs text-slate-500">{row.contract_number || row.assets?.[0]?.asset_name || "No reference"} · <span className="capitalize">{row.status || "unknown"}</span></div></td><td className="px-5 py-4"><span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-bold capitalize text-indigo-700">{row.contract_family}</span></td><td className="px-5 py-4 text-slate-600">{row.contractor?.legal_name || "—"}</td><td className="px-5 py-4 text-slate-600">{row.assets?.[0]?.station_code || row.assets?.[0]?.train_number || row.assets?.[0]?.asset_name || "Other"}</td><td className="px-5 py-4"><div>{row.policy_code || "—"}</div><div className="mt-1 text-xs text-slate-500">{row.category || row.contract_family}</div></td><td className="px-5 py-4 text-slate-600">{date(row.period?.start)}<br />to {date(row.period?.end)}</td><td className="px-5 py-4 text-right font-semibold">{money(row.financials?.total_contract_value || row.financials?.annual_license_fee)}</td></tr>)}</tbody></table></div>{!loading && !visibleRows.length && <div className="p-12 text-center text-sm text-slate-500">No contracts match this view.</div>}</div>
    {selected && <div className="fixed inset-0 z-20 flex justify-end bg-slate-900/20" onClick={() => setSelected(null)}><aside onClick={(e) => e.stopPropagation()} className="h-full w-full max-w-xl overflow-y-auto bg-white p-7 shadow-2xl"><div className="mb-7 flex items-start justify-between"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-600">{titleCase(selected.contract_family)} detail</p><h2 className="mt-2 text-2xl font-semibold">{selected.contract_name}</h2></div><button onClick={() => setSelected(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X /></button></div><div className="grid grid-cols-2 gap-3">{[["Status", selected.status], ["Family", selected.contract_family], ["Policy", selected.policy_code], ["Contractor", selected.contractor?.legal_name], ["Start", date(selected.period?.start)], ["End", date(selected.period?.end)], ["Annual fee", money(selected.financials?.annual_license_fee)], ["Total value", money(selected.financials?.total_contract_value)]].map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 font-semibold">{value || "—"}</div></div>)}</div><h3 className="mb-3 mt-8 font-semibold">Assets</h3>{(selected.assets || []).map((asset, index) => <div key={index} className="mb-2 rounded-xl border border-slate-200 p-3 text-sm">{asset.station_code || asset.train_number || asset.asset_name || asset.raw_asset_value}<span className="ml-2 text-xs text-slate-500">{asset.asset_type}</span></div>)}</aside></div>}
  </div></main>;
}
