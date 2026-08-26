"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, CheckCircle2, Download, FileSpreadsheet, RefreshCw, Search, UploadCloud } from "lucide-react";
import { API_URL, fetchJson } from "../lib/api";
import { Badge, Button, Panel, cx } from "./ui";

type Station = { station_code?: string; station_name?: string; division?: string };
type MetricRow = {
  metric_id?: number;
  station_code: string;
  metric_month?: string;
  passenger_footfall?: number | null;
  uts_tickets?: number | null;
  uts_earnings?: number | null;
  prs_tickets?: number | null;
  prs_earnings?: number | null;
  remarks?: string | null;
};

const fields = [
  ["passenger_footfall", "Footfall"],
  ["uts_tickets", "UTS tickets"],
  ["uts_earnings", "UTS earnings"],
  ["prs_tickets", "PRS tickets"],
  ["prs_earnings", "PRS earnings"],
] as const;

const monthKey = (value?: string) => String(value || "").slice(0, 7);
const currentMonth = () => new Date().toISOString().slice(0, 7);
const numberText = (value?: number | null) => value == null ? "" : String(value);
const formatNumber = (value?: number | null) => value == null ? "—" : Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });

function csvCell(value: unknown) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function parseCsv(text: string) {
  const table: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (char === '"') {
      if (quoted && text[index + 1] === '"') { cell += '"'; index += 1; }
      else quoted = !quoted;
    } else if (char === "," && !quoted) { row.push(cell.trim()); cell = ""; }
    else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && text[index + 1] === "\n") index += 1;
      row.push(cell.trim());
      if (row.some(Boolean)) table.push(row);
      row = []; cell = "";
    } else cell += char;
  }
  row.push(cell.trim());
  if (row.some(Boolean)) table.push(row);
  if (table.length < 2) return [];
  const headers = table[0].map((header) => header.trim().toLowerCase().replaceAll(" ", "_"));
  return table.slice(1).map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] || ""])));
}

export function StationMetricsMaster({ stations, onActivity }: { stations: Station[]; onActivity?: (message: string) => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<MetricRow[]>([]);
  const [selectedMonth, setSelectedMonth] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState("");
  const [pendingRows, setPendingRows] = useState<any[]>([]);
  const [message, setMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchJson(`${API_URL}/api/station-metrics`);
      const nextRows = data.items || [];
      setRows(nextRows);
      setSelectedMonth((value) => value || monthKey(nextRows[0]?.metric_month) || currentMonth());
    } catch (error: any) {
      setMessage({ tone: "danger", text: error.message || "Monthly station data could not be loaded." });
      setSelectedMonth((value) => value || currentMonth());
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const months = useMemo(() => Array.from(new Set(rows.map((row) => monthKey(row.metric_month)).filter(Boolean))).sort().reverse(), [rows]);
  const byStation = useMemo(() => new Map(rows.filter((row) => monthKey(row.metric_month) === selectedMonth).map((row) => [row.station_code, row])), [rows, selectedMonth]);
  const visibleStations = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return stations.filter((station) => !needle || `${station.station_code} ${station.station_name} ${station.division}`.toLowerCase().includes(needle));
  }, [stations, query]);
  const populated = stations.filter((station) => byStation.has(String(station.station_code))).length;
  const totals = useMemo(() => fields.map(([key]) => rows.filter((row) => monthKey(row.metric_month) === selectedMonth).reduce((sum, row) => sum + Number(row[key] || 0), 0)), [rows, selectedMonth]);

  const templateRows = () => stations.map((station) => {
    const existing = byStation.get(String(station.station_code));
    return [station.station_code, station.station_name, selectedMonth, ...fields.map(([key]) => numberText(existing?.[key])), existing?.remarks || ""];
  });

  const downloadTemplate = () => {
    const header = ["station_code", "station_name", "month", ...fields.map(([key]) => key), "remarks"];
    const csv = [header, ...templateRows()].map((row) => row.map(csvCell).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url; link.download = `station-master-${selectedMonth}.csv`; link.click();
    URL.revokeObjectURL(url);
  };

  const chooseFile = async (file?: File) => {
    if (!file) return;
    const parsed = parseCsv(await file.text());
    setFileName(file.name); setPendingRows(parsed); setMessage(null);
  };

  const invalidRows = useMemo(() => {
    const codes = new Set(stations.map((station) => String(station.station_code || "").toUpperCase()));
    return pendingRows.filter((row) => !codes.has(String(row.station_code || "").trim().toUpperCase()));
  }, [pendingRows, stations]);
  const pendingCodes = useMemo(() => pendingRows.map((row) => String(row.station_code || "").trim().toUpperCase()).filter(Boolean), [pendingRows]);
  const duplicateCodes = useMemo(() => pendingCodes.filter((code, index) => pendingCodes.indexOf(code) !== index), [pendingCodes]);
  const missingCodes = useMemo(() => {
    const included = new Set(pendingCodes);
    return stations.map((station) => String(station.station_code || "").toUpperCase()).filter((code) => !included.has(code));
  }, [pendingCodes, stations]);
  const invalidValueRows = useMemo(() => pendingRows.filter((row) => fields.some(([key]) => {
    const raw = row[key];
    const parsed = Number(String(raw ?? "").replaceAll(",", ""));
    return raw === "" || raw == null || !Number.isFinite(parsed) || parsed < 0;
  })), [pendingRows]);
  const uploadHasErrors = Boolean(invalidRows.length || duplicateCodes.length || missingCodes.length || invalidValueRows.length);

  const upload = async () => {
    if (!pendingRows.length || uploadHasErrors) return;
    setUploading(true); setMessage(null);
    try {
      const payloadRows = pendingRows.map((row) => ({
        ...row,
        station_code: String(row.station_code || "").trim().toUpperCase(),
        month: row.month || selectedMonth,
        ...Object.fromEntries(fields.map(([key]) => [key, row[key] === "" || row[key] == null ? null : Number(String(row[key]).replaceAll(",", ""))])),
      }));
      const result = await fetchJson(`${API_URL}/api/station-metrics/bulk`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ month: selectedMonth, require_complete: true, rows: payloadRows }) });
      const text = `${result.processed} station rows saved: ${result.created} created, ${result.updated} updated.`;
      setMessage({ tone: "success", text }); setPendingRows([]); setFileName(""); onActivity?.(text);
      if (fileRef.current) fileRef.current.value = "";
      await load();
    } catch (error: any) { setMessage({ tone: "danger", text: error.message || "Bulk upload failed." }); }
    finally { setUploading(false); }
  };

  return (
    <div className="space-y-4">
      <Panel title="Monthly station master" subtitle="One latest-first workspace for Footfall, UTS and PRS data across the full station list." action={<Badge tone="accent">{stations.length} stations</Badge>}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[220px_minmax(260px,1fr)_auto]">
          <label className="grid gap-1"><span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">Reporting month</span><select value={selectedMonth} onChange={(event) => setSelectedMonth(event.target.value)} className="soft-inset h-11 rounded-lg border border-line px-3 text-sm"><option value={currentMonth()}>{currentMonth()} {months.includes(currentMonth()) ? "" : "· new"}</option>{months.filter((month) => month !== currentMonth()).map((month) => <option key={month} value={month}>{month}</option>)}</select></label>
          <label className="grid gap-1"><span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">Find station</span><span className="relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Code, station or division" className="soft-inset h-11 w-full rounded-lg border border-line pl-10 pr-3 text-sm outline-none focus:border-accent" /></span></label>
          <Button variant="secondary" className="self-end" onClick={load} disabled={loading}><RefreshCw size={16} className={loading ? "animate-spin" : ""} />Refresh</Button>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-3 xl:grid-cols-6">
          <div className="rounded-xl border border-line bg-surfaceStrong p-3"><div className="text-xs font-bold text-muted">Coverage</div><div className="mt-1 text-xl font-black text-ink">{populated}/{stations.length}</div></div>
          {fields.map(([, label], index) => <div key={label} className="rounded-xl border border-line bg-surfaceStrong p-3"><div className="text-xs font-bold text-muted">{label}</div><div className="mt-1 truncate text-lg font-black text-ink">{formatNumber(totals[index])}</div></div>)}
        </div>
      </Panel>

      <Panel title="Bulk upload" subtitle={`Download the ${selectedMonth} master, fill it in Excel, then upload it once. Existing values are included so corrections are safe.`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Button variant="secondary" onClick={downloadTemplate}><Download size={16} />Download {stations.length}-station CSV</Button>
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(event) => chooseFile(event.target.files?.[0])} />
          <Button variant="secondary" onClick={() => fileRef.current?.click()}><UploadCloud size={16} />Choose completed CSV</Button>
          <Button onClick={upload} disabled={!pendingRows.length || uploadHasErrors || uploading}>{uploading ? <RefreshCw size={16} className="animate-spin" /> : <FileSpreadsheet size={16} />}Upload {pendingRows.length || "all"} rows</Button>
        </div>
        {fileName ? <div className="mt-3 flex flex-wrap items-center gap-2 text-sm"><Badge tone={uploadHasErrors ? "danger" : "success"}>{fileName}</Badge><span className="text-muted">{pendingRows.length} rows read</span>{invalidRows.length ? <span className="font-bold text-red-600">{invalidRows.length} unknown code(s)</span> : null}{duplicateCodes.length ? <span className="font-bold text-red-600">{new Set(duplicateCodes).size} duplicate code(s)</span> : null}{missingCodes.length ? <span className="font-bold text-red-600">{missingCodes.length} station(s) missing</span> : null}{invalidValueRows.length ? <span className="font-bold text-red-600">{invalidValueRows.length} row(s) need all five values</span> : null}{!uploadHasErrors ? <span className="font-bold text-emerald-700">All {stations.length} stations ready</span> : null}</div> : null}
        {message ? <div className={cx("mt-3 flex items-start gap-2 rounded-xl border p-3 text-sm font-semibold", message.tone === "success" ? "border-emerald-300 bg-emerald-500/10 text-emerald-700" : "border-red-300 bg-red-500/10 text-red-700")}>{message.tone === "success" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}<span>{message.text}</span></div> : null}
      </Panel>

      <Panel title={selectedMonth ? `${selectedMonth} station data` : "Station data"} subtitle="Latest available month is selected automatically. Missing entries remain visible instead of disappearing from the master.">
        <div className="soft-scroll overflow-x-auto rounded-xl border border-line">
          <table className="min-w-[980px] w-full border-collapse text-sm">
            <thead className="sticky top-0 bg-surfaceStrong text-left text-[11px] font-black uppercase tracking-[0.12em] text-muted"><tr><th className="px-3 py-3">Station</th>{fields.map(([, label]) => <th key={label} className="px-3 py-3 text-right">{label}</th>)}<th className="px-3 py-3">Status</th></tr></thead>
            <tbody>{visibleStations.map((station) => { const metric = byStation.get(String(station.station_code)); return <tr key={station.station_code} className="border-t border-line hover:bg-accentSoft/40"><td className="px-3 py-3"><div className="font-black text-ink">{station.station_code} <span className="font-semibold">· {station.station_name || "Unnamed station"}</span></div><div className="text-xs text-muted">{station.division || "Division not set"}</div></td>{fields.map(([key]) => <td key={key} className="px-3 py-3 text-right tabular-nums text-ink">{formatNumber(metric?.[key])}</td>)}<td className="px-3 py-3"><Badge tone={metric ? "success" : "neutral"}>{metric ? "Available" : "Missing"}</Badge></td></tr>; })}</tbody>
          </table>
          {!visibleStations.length ? <div className="p-8 text-center text-sm text-muted">No station matches this search.</div> : null}
        </div>
      </Panel>
    </div>
  );
}
