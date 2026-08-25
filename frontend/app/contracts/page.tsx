"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleAlert, Clock3, FileCheck2, Search, XCircle } from "lucide-react";
import { contractRegistryDetailUrl, contractSummaryUrl, contractsUrl, fetchJson } from "../../lib/api";

type Contract = {
  contract_id: number;
  contract_number?: string;
  contract_name?: string;
  status?: string;
  contract_family?: string;
  policy_code?: string;
  category?: string;
  contractor?: { legal_name?: string };
  period?: { start?: string; end?: string };
  financials?: { annual_license_fee?: number; total_contract_value?: number };
  assets?: { asset_type?: string; station_code?: string; train_number?: string; asset_name?: string }[];
  payment_schedule?: { schedule_id: number; installment_number?: number; due_date?: string; expected_amount?: number; status?: string }[];
  source?: { sheet?: string; row?: number };
};

const tabs = [
  ["all", "All"], ["awarded", "Awarded"], ["running", "Running"],
  ["completed", "Completed"], ["cancelled", "Cancelled"],
] as const;

const money = (value?: number) => `₹${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
const date = (value?: string) => value ? new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";

export default function ContractsPage() {
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<Contract[]>([]);
  const [summary, setSummary] = useState<any>({ counts: {} });
  const [selected, setSelected] = useState<Contract | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true); setError("");
    try {
      const [data, totals] = await Promise.all([fetchJson(contractsUrl({ status, search })), fetchJson(contractSummaryUrl())]);
      setRows(data.items || []); setSummary(totals || { counts: {} });
    } catch (err: any) { setError(err?.message || "Could not load contracts"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [status]);
  useEffect(() => { const timer = setTimeout(load, 350); return () => clearTimeout(timer); }, [search]);

  const statCards = useMemo(() => [
    ["Awarded", "awarded", FileCheck2], ["Running", "running", Clock3], ["Completed", "completed", CheckCircle2], ["Cancelled", "cancelled", XCircle],
  ], []);

  const openDetail = async (row: Contract) => {
    try { setSelected(await fetchJson(contractRegistryDetailUrl(row.contract_id))); } catch { setSelected(row); }
  };

  return <main className="min-h-screen bg-[#f5f7fb] px-5 py-8 text-slate-900 md:px-10">
    <div className="mx-auto max-w-7xl">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div><p className="mb-2 text-xs font-bold uppercase tracking-[0.24em] text-indigo-600">Rail Inspect · Contract Registry</p><h1 className="text-3xl font-semibold tracking-tight">Contracts workspace</h1><p className="mt-2 text-sm text-slate-500">E-auction, tender, station, train, audio and other commercial contracts.</p></div>
        <button onClick={load} className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm">Refresh data</button>
      </div>
      <div className="mb-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map(([label, key, Icon]: any) => <button key={key} onClick={() => setStatus(key)} className={`rounded-2xl border bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 ${status === key ? "border-indigo-400 ring-2 ring-indigo-100" : "border-slate-200"}`}><Icon className="mb-4 h-5 w-5 text-indigo-600" /><div className="text-2xl font-semibold">{summary.counts?.[key] || 0}</div><div className="mt-1 text-sm text-slate-500">{label}</div></button>)}
      </div>
      <div className="mb-5 flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
        {tabs.map(([key, label]) => <button key={key} onClick={() => setStatus(key)} className={`rounded-xl px-4 py-2 text-sm font-semibold ${status === key ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}{key !== "all" && <span className="ml-2 opacity-70">{summary.counts?.[key] || 0}</span>}</button>)}
        <label className="relative ml-auto min-w-[240px] flex-1 sm:max-w-xs"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search contract, number, policy..." className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm outline-none focus:border-indigo-400" /></label>
      </div>
      {error && <div className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"><CircleAlert className="mr-2 inline h-4 w-4" />{error}</div>}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><div className="font-semibold">{status === "all" ? "All contracts" : `${status[0].toUpperCase()}${status.slice(1)} contracts`}</div><div className="text-sm text-slate-500">{loading ? "Loading..." : `${rows.length} records`}</div></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Contract</th><th className="px-5 py-3">Contractor</th><th className="px-5 py-3">Asset</th><th className="px-5 py-3">Policy / category</th><th className="px-5 py-3">Period</th><th className="px-5 py-3 text-right">Value</th></tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row) => <tr key={row.contract_id} onClick={() => openDetail(row)} className="cursor-pointer hover:bg-indigo-50/40"><td className="px-5 py-4"><div className="font-semibold text-slate-900">{row.contract_name || "Unnamed contract"}</div><div className="mt-1 text-xs text-slate-500">{row.contract_number || "No contract number"} · <span className="capitalize">{row.status}</span></div></td><td className="px-5 py-4 text-slate-600">{row.contractor?.legal_name || "—"}</td><td className="px-5 py-4 text-slate-600">{row.assets?.[0]?.station_code || row.assets?.[0]?.train_number || row.assets?.[0]?.asset_name || "Other"}</td><td className="px-5 py-4"><div>{row.policy_code || "—"}</div><div className="mt-1 text-xs text-slate-500">{row.category || row.contract_family}</div></td><td className="px-5 py-4 text-slate-600">{date(row.period?.start)}<br />to {date(row.period?.end)}</td><td className="px-5 py-4 text-right font-semibold">{money(row.financials?.total_contract_value)}</td></tr>)}</tbody></table></div>
        {!loading && !rows.length && <div className="p-12 text-center text-sm text-slate-500">No contracts match this view.</div>}
      </div>
      {selected && <div className="fixed inset-0 z-20 flex justify-end bg-slate-900/20" onClick={() => setSelected(null)}><aside onClick={(e) => e.stopPropagation()} className="h-full w-full max-w-xl overflow-y-auto bg-white p-7 shadow-2xl"><div className="mb-7 flex items-start justify-between"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-600">Contract detail</p><h2 className="mt-2 text-2xl font-semibold">{selected.contract_name}</h2><p className="mt-1 text-sm text-slate-500">{selected.contract_number}</p></div><button onClick={() => setSelected(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100">×</button></div><div className="grid grid-cols-2 gap-3">{[["Status", selected.status], ["Family", selected.contract_family], ["Policy", selected.policy_code], ["Contractor", selected.contractor?.legal_name], ["Start", date(selected.period?.start)], ["End", date(selected.period?.end)], ["Annual fee", money(selected.financials?.annual_license_fee)], ["Total value", money(selected.financials?.total_contract_value)]].map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 font-semibold">{value || "—"}</div></div>)}</div><h3 className="mb-3 mt-8 font-semibold">Assets</h3>{(selected.assets || []).map((asset: any, index: number) => <div key={index} className="mb-2 rounded-xl border border-slate-200 p-3 text-sm">{asset.station_code || asset.train_number || asset.asset_name || asset.raw_asset_value}<span className="ml-2 text-xs text-slate-500">{asset.asset_type}</span></div>)}<h3 className="mb-3 mt-8 font-semibold">Payment schedule</h3>{(selected.payment_schedule || []).length ? selected.payment_schedule.map((item: any) => <div key={item.schedule_id} className="flex justify-between border-b border-slate-100 py-3 text-sm"><span>Installment {item.installment_number}</span><span>{date(item.due_date)}</span></div>) : <p className="text-sm text-slate-500">No payment schedule imported yet.</p>}<p className="mt-8 text-xs text-slate-400">Source: {selected.source?.sheet || "contract registry"}, row {selected.source?.row || "—"}</p></aside></div>}
    </div>
  </main>;
}
