"use client";

import { useEffect, useState } from "react";
import { API_URL, fetchJson } from "../lib/api";
import { Button, Panel } from "./ui";

type Annual = { financial_year: string; row_count: number; months: number[]; unallocated_rows: number; missing_pub_amounts: number; missing_nfr_amounts: number; pub_earnings: string; nfr_earnings: string };
type Receipt = { source_row: number; receipt_date: string | null; month: number | null; details: string; firm: string; policy: string; location: string; detailed_head: string; receipt_reference: string; pub_earnings: string | null; nfr_earnings: string | null };
type Warning = { row: number; message: string };
type Ledger = {
  source: { filename: string; row_count: number; warnings: Warning[] } | null;
  options: { years: string[]; policies: string[]; heads: string[] };
  selected_year: string;
  annual: Annual[];
  monthly: { month: number; label: string; row_count: number; pub_earnings: string | null; nfr_earnings: string | null }[];
  policies: (Annual & { policy: string })[];
  comparison: { previous_year: string; months: number[]; pub_earnings: { change_percent: string | null }; nfr_earnings: { change_percent: string | null } };
  rows: Receipt[];
  latest_receipt_date: string | null;
};
const rupees = (v: string | null | undefined) => v == null ? "—" : Number(v).toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const monthLabel = (m: number) => new Date(2024, m - 1).toLocaleString("en-IN", { month: "short" });
const selectStyle = "soft-inset rounded-lg border border-line p-2 text-sm text-ink";

export function PublicityEarnings({operatorKey}:{operatorKey?:string} = {}) {
  const [data, setData] = useState<Ledger | null>(null);
  const [year, setYear] = useState("");
  const [policy, setPolicy] = useState("");
  const [head, setHead] = useState("");
  const [query, setQuery] = useState("");
  const [metric, setMetric] = useState<"pub_earnings" | "nfr_earnings">("pub_earnings");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [page, setPage] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ row_count: number; annual: Annual[]; warnings: Warning[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [importKey,setImportKey]=useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setPage(1);
    const params = new URLSearchParams();
    if (year) params.set("year", year);
    if (policy) params.set("policy", policy);
    if (head) params.set("head", head);
    if (query.trim()) params.set("q", query.trim());
    const timer = setTimeout(() => {
      fetchJson(`${API_URL}/api/publicity-earnings?${params}`, { signal: controller.signal })
        .then(setData)
        .catch((e: Error) => { if (!controller.signal.aborted) setError(e.message); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 200);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [year, policy, head, query, revision]);

  async function upload(apply: boolean) {
    if (!file) return;
    setBusy(true); setNotice("");
    const body = new FormData(); body.append("file", file);
    try {
      const result = await fetchJson(`${API_URL}/api/publicity-earnings/import?dry_run=${!apply}`, { method: "POST", headers:{Authorization:`Bearer ${operatorKey??importKey}`},body });
      if (apply) {
        setPreview(null);
        setNotice(`${result.status === "unchanged" ? "Already imported" : "Imported"}: ${result.row_count.toLocaleString("en-IN")} Main Sheet rows.`);
        setYear(""); setPolicy(""); setHead(""); setQuery(""); setRevision(v => v + 1);
      } else setPreview(result);
    } catch (e) { setNotice(e instanceof Error ? e.message : "Import failed"); }
    finally { setBusy(false); }
  }

  function exportReceipts() {
    if (!data) return;
    const fields: (keyof Receipt)[] = ["source_row", "receipt_date", "month", "details", "firm", "policy", "location", "detailed_head", "receipt_reference", "pub_earnings", "nfr_earnings"];
    const cell = (v: unknown) => `"${String(v ?? "").replace(/^[=+@-]/, "'$&").replaceAll('"', '""')}"`;
    const csv = [fields.join(","), ...data.rows.map(r => fields.map(k => cell(r[k])).join(","))].join("\r\n");
    const url = URL.createObjectURL(new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = `publicity-earnings-${data.selected_year}.csv`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const selected = data?.annual.find(r => r.financial_year === data.selected_year);
  const maxMonthly = Math.max(1, ...(data?.monthly.map(r => Math.abs(Number(r[metric]))) || []));
  const change = data?.comparison[metric].change_percent;
  const metricLabel = metric === "pub_earnings" ? "PUB earnings" : "NFR earnings";
  const partial = data?.selected_year === data?.options.years.at(-1) && (selected?.months.length || 0) < 12;
  const th = "whitespace-nowrap px-3 py-2 text-left text-xs font-bold text-muted";
  const td = "border-t border-line px-3 py-2 text-sm";

  return <Panel title="Historical publicity earnings" subtitle="Main Sheet receipt ledger · amounts in rupees">
    <div className="grid gap-5">
      <details className="rounded-xl border border-line p-3">
        <summary className="cursor-pointer text-sm font-bold">Import earnings workbook</summary>
        <p className="my-3 text-sm text-muted">Only Main Sheet is read. Import a complete workbook to activate a new ledger version. Earlier versions are retained; contract payments are separate.</p>
        <div className="flex flex-wrap items-center gap-3">
          {operatorKey===undefined?<label className="grid gap-1 text-xs font-bold">Operator access key<input type="password" autoComplete="off" className={selectStyle} value={importKey} disabled={busy} onChange={e=>setImportKey(e.target.value)} /></label>:null}
          <input aria-label="Earnings workbook" type="file" accept=".xlsx" disabled={busy} onChange={e => { setFile(e.target.files?.[0] || null); setPreview(null); setNotice(""); }} />
          <Button size="sm" variant="secondary" disabled={!file || busy || !(operatorKey??importKey)} onClick={() => upload(false)}>{busy ? "Processing…" : "Validate Main Sheet"}</Button>
        </div>
        {preview && <div className="mt-3 grid gap-3 text-sm">
          <p>{preview.row_count.toLocaleString("en-IN")} rows across {preview.annual.length} financial years. {preview.warnings.length} data-quality notes.</p>
          <div className="overflow-auto"><table className="w-full"><thead><tr><th className={th}>Financial year</th><th className={th}>PUB earnings</th><th className={th}>NFR earnings</th></tr></thead><tbody>{preview.annual.map(r => <tr key={r.financial_year}><td className={td}>{r.financial_year}</td><td className={td}>{rupees(r.pub_earnings)}</td><td className={td}>{rupees(r.nfr_earnings)}</td></tr>)}</tbody></table></div>
          <details><summary>Review data-quality notes</summary><ul className="max-h-48 overflow-auto">{preview.warnings.map((w, i) => <li key={i}>Row {w.row}: {w.message}</li>)}</ul></details>
          <Button size="sm" disabled={busy||!(operatorKey??importKey)} onClick={() => upload(true)}>Import {preview.row_count.toLocaleString("en-IN")} rows</Button>
        </div>}
        {notice && <p role="status" className="mt-3 text-sm">{notice}</p>}
      </details>
      {error && <div role="alert" className="text-sm text-red-600">{error} <button className="underline" onClick={() => setRevision(v => v + 1)}>Retry</button></div>}
      <div className="flex flex-wrap gap-3">
        <label className="grid gap-1 text-xs font-bold">Financial year<select className={selectStyle} value={year || data?.selected_year || ""} onChange={e => setYear(e.target.value)}>{data?.options.years.map(v => <option key={v}>{v}</option>)}</select></label>
        <label className="grid gap-1 text-xs font-bold">Measure<select className={selectStyle} value={metric} onChange={e => setMetric(e.target.value as typeof metric)}><option value="pub_earnings">PUB earnings</option><option value="nfr_earnings">NFR earnings</option></select></label>
        <label className="grid gap-1 text-xs font-bold">Policy<select className={selectStyle} value={policy} onChange={e => setPolicy(e.target.value)}><option value="">All policies</option>{data?.options.policies.map(v => <option key={v}>{v}</option>)}</select></label>
        <label className="grid gap-1 text-xs font-bold">Detailed head<select className={selectStyle} value={head} onChange={e => setHead(e.target.value)}><option value="">All heads</option>{data?.options.heads.map(v => <option key={v}>{v}</option>)}</select></label>
        <label className="grid gap-1 text-xs font-bold">Search receipts<input className={selectStyle} value={query} onChange={e => setQuery(e.target.value)} placeholder="Firm, details, location or reference" /></label>
      </div>
      {loading ? <p role="status">Loading earnings…</p> : !error && data && (data.source ? <>
        <p className="text-xs text-muted">{data.source.filename} · Main Sheet · {data.source.row_count.toLocaleString("en-IN")} rows · Latest dated receipt: {data.latest_receipt_date || "Unavailable"}. PUB and NFR are separate source measures and must not be added together.</p>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="soft-inset rounded-xl p-4"><p className="text-xs text-muted">{data.selected_year} {partial ? "· partial year" : "· recorded receipts"}</p><p className="mt-2 text-xl font-black">{rupees(selected?.[metric])}</p><p className="text-xs">{metricLabel}</p></div>
          <div className="soft-inset rounded-xl p-4"><p className="text-xs text-muted">Change across common recorded months vs {data.comparison.previous_year}</p><p className="mt-2 text-xl font-black">{change == null ? "Unavailable" : `${Number(change) > 0 ? "+" : ""}${change}%`}</p><p className="text-xs">{data.comparison.months.map(monthLabel).join(", ") || "No comparable months"}</p></div>
          <div className="soft-inset rounded-xl p-4"><p className="text-xs text-muted">Matching receipts</p><p className="mt-2 text-xl font-black">{data.rows.length}</p><p className="text-xs">{selected?.unallocated_rows || 0} without month · {selected?.[metric === "pub_earnings" ? "missing_pub_amounts" : "missing_nfr_amounts"] || 0} missing amounts</p></div>
        </div>
        <p className="text-xs text-muted">Totals sum populated source amounts; — means no amount recorded. Missing months are not assumed to be zero. Comparisons exclude rows without a month and are unavailable when a compared amount is missing. The latest recorded month may be incomplete.</p>
        <div className="grid gap-5 xl:grid-cols-2">
          <div><h3 className="mb-3 text-sm font-bold">Financial year totals · {metricLabel}</h3><div className="overflow-auto"><table className="w-full"><thead><tr><th className={th}>Year</th><th className={th}>Recorded months</th><th className={th}>Earnings</th></tr></thead><tbody>{data.annual.map(r => <tr key={r.financial_year}><td className={td}><button className="font-bold underline" onClick={() => setYear(r.financial_year)}>{r.financial_year}</button></td><td className={td}>{r.months.length}/12{r.unallocated_rows ? ` + ${r.unallocated_rows} undated-month rows` : ""}</td><td className={`${td} whitespace-nowrap tabular-nums`}>{rupees(r[metric])}</td></tr>)}</tbody></table></div></div>
          <div><h3 className="mb-3 text-sm font-bold">Monthly receipts · {data.selected_year}</h3><div className="grid gap-2">{data.monthly.map(r => <div key={r.month} className="grid grid-cols-[2rem_1fr_8rem] items-center gap-2 text-xs"><span>{r.label}</span><div className="h-3 rounded bg-slate-100"><div className={`h-3 rounded ${Number(r[metric]) < 0 ? "bg-rose-500" : "bg-teal-600"}`} style={{ width: `${Math.abs(Number(r[metric])) / maxMonthly * 100}%` }} /></div><span className="text-right tabular-nums">{r.row_count ? rupees(r[metric]) : "No records"}</span></div>)}</div></div>
        </div>
        <details><summary className="cursor-pointer text-sm font-bold">Policy breakdown · {data.selected_year}</summary><div className="overflow-auto"><table className="mt-2 w-full"><thead><tr><th className={th}>Policy</th><th className={th}>Receipts</th><th className={th}>{metricLabel}</th></tr></thead><tbody>{data.policies.map(r => <tr key={r.policy}><td className={td}>{r.policy}</td><td className={td}>{r.row_count}</td><td className={td}>{rupees(r[metric])}</td></tr>)}</tbody></table></div></details>
        <details><summary className="cursor-pointer text-sm font-bold">Source data-quality notes ({data.source.warnings.length})</summary><ul className="mt-2 max-h-48 overflow-auto text-xs">{data.source.warnings.map((w, i) => <li key={i}>Main Sheet row {w.row}: {w.message}</li>)}</ul></details>
        <div className="flex items-center justify-between"><h3 className="text-sm font-bold">Receipt ledger · {data.selected_year}</h3><Button size="sm" variant="secondary" onClick={exportReceipts} disabled={!data.rows.length}>Export filtered CSV</Button></div>
        <div className="overflow-auto"><table className="w-full"><thead><tr>{["Source row", "Date", "Details / firm", "Policy / head", "Receipt reference", metricLabel].map(h => <th className={th} key={h}>{h}</th>)}</tr></thead><tbody>{data.rows.slice((page-1)*25, page*25).map(r => <tr key={r.source_row}><td className={td}>{r.source_row}</td><td className={`${td} whitespace-nowrap`}>{r.receipt_date || "Not recorded"}</td><td className={`${td} min-w-56`}>{r.details || "—"}<p className="text-xs text-muted">{r.firm}</p></td><td className={td}>{r.policy || "—"}<p className="text-xs text-muted">{r.detailed_head}</p></td><td className={td}>{r.receipt_reference || "—"}</td><td className={`${td} whitespace-nowrap tabular-nums`}>{rupees(r[metric])}</td></tr>)}</tbody></table>{!data.rows.length && <p className="p-4 text-sm">No receipts match these filters.</p>}</div>
        <div className="flex items-center justify-end gap-3 text-sm"><Button size="sm" variant="secondary" disabled={page === 1} onClick={() => setPage(p => p-1)}>Previous</Button><span>Page {page} of {Math.max(1, Math.ceil(data.rows.length/25))}</span><Button size="sm" variant="secondary" disabled={page*25 >= data.rows.length} onClick={() => setPage(p => p+1)}>Next</Button></div>
      </> : <p className="text-sm text-muted">No historical earnings imported yet. Upload the earnings workbook above to begin.</p>)}
    </div>
  </Panel>;
}
