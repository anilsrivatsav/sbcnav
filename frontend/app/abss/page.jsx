"use client";

import { useEffect, useMemo, useState } from "react";
import { Download, Pencil, Plus, RotateCcw, Save, Search, Trash2, X } from "lucide-react";
import abssData from "../../data/abss-station-output.json";

const departments = ["All", "Civil", "Electrical", "S&T"];
const editableDepartments = ["Civil", "Electrical", "S&T"];
const remarkFilters = ["All", "With Remarks", "Deficiency", "Poor Quality", "Blank Remarks"];
const fields = ["Department", "Scope", "Existing_Facility", "Facility_Under_ABSS", "Remarks", "TDC"];

const emptyRow = {
  Department: "Civil",
  Scope: "",
  Existing_Facility: "",
  Facility_Under_ABSS: "",
  Remarks: "",
  TDC: "",
};

const text = (value) => (value === null || value === undefined ? "" : String(value));
const normal = (value) => text(value).toLowerCase().replace(/\s+/g, " ").trim();
const hasDeficiency = (row) => normal(row.Remarks).includes("deficiency:");
const hasPoorQuality = (row) => normal(row.Remarks).includes("poor quality:");
const hasRemarks = (row) => Boolean(normal(row.Remarks));
const cx = (...classes) => classes.filter(Boolean).join(" ");

const deptClass = {
  Civil: "border-orange-300 bg-orange-50 text-orange-700",
  Electrical: "border-blue-300 bg-blue-50 text-blue-700",
  "S&T": "border-emerald-300 bg-emerald-50 text-emerald-700",
};

function summarizeStations(rows) {
  const byStation = new Map();
  for (const station of abssData.stations) {
    byStation.set(station.Station, {
      Station: station.Station,
      Station_Name: station.Station_Name,
      row_count: 0,
      civil_rows: 0,
      electrical_rows: 0,
      st_rows: 0,
      deficiency_rows: 0,
      poor_quality_rows: 0,
    });
  }
  for (const row of rows) {
    const item = byStation.get(row.Station) || {
      Station: row.Station,
      Station_Name: row.Station_Name || row.Station,
      row_count: 0,
      civil_rows: 0,
      electrical_rows: 0,
      st_rows: 0,
      deficiency_rows: 0,
      poor_quality_rows: 0,
    };
    item.row_count += 1;
    if (row.Department === "Civil") item.civil_rows += 1;
    if (row.Department === "Electrical") item.electrical_rows += 1;
    if (row.Department === "S&T") item.st_rows += 1;
    if (hasDeficiency(row)) item.deficiency_rows += 1;
    if (hasPoorQuality(row)) item.poor_quality_rows += 1;
    byStation.set(row.Station, item);
  }
  return Array.from(byStation.values()).filter((item) => item.Station).sort((a, b) => a.Station.localeCompare(b.Station));
}

function Chip({ active, children, onClick, subtext }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cx(
        "focus-ring min-w-[104px] shrink-0 rounded-lg border px-3 py-2 text-left transition",
        active ? "border-accent bg-accent text-white shadow-raised" : "border-line bg-surface text-ink hover:border-accent hover:bg-surfaceStrong",
      )}
    >
      <div className="text-sm font-black">{children}</div>
      <div className={cx("mt-0.5 text-[11px] font-bold", active ? "text-white/80" : "text-muted")}>{subtext}</div>
    </button>
  );
}

function DepartmentPill({ value }) {
  return (
    <span className={cx("inline-flex rounded-full border px-2.5 py-1 text-[11px] font-black uppercase", deptClass[value] || "border-line bg-surfaceStrong text-muted")}>
      {value || "NA"}
    </span>
  );
}

function CellText({ value, muted = false }) {
  const display = text(value).trim();
  return <div className={cx("whitespace-pre-wrap leading-5", muted ? "text-muted" : "text-ink")}>{display || "NA"}</div>;
}

function IconButton({ label, children, tone = "neutral", ...props }) {
  const tones = {
    neutral: "border-line text-muted hover:border-accent hover:text-accentStrong",
    danger: "border-red-300 text-red-600 hover:bg-red-50",
    primary: "border-accent bg-accent text-white hover:bg-accentStrong",
  };
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cx("focus-ring inline-flex h-9 w-9 items-center justify-center rounded-lg border transition", tones[tone])}
      {...props}
    >
      {children}
    </button>
  );
}

function exportCsv(rows, station) {
  const headers = ["Department", "Scope", "Existing Facility", "Facility under ABSS", "Remarks", "TDC"];
  const escape = (value) => {
    const raw = text(value);
    return /[",\n]/.test(raw) ? `"${raw.replaceAll('"', '""')}"` : raw;
  };
  const csv = [headers.join(","), ...rows.map((row) => fields.map((key) => escape(row[key])).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `abss-${station}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function EditModal({ open, mode, value, onChange, onClose, onSave }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-3">
      <form onSubmit={onSave} className="max-h-[92vh] w-full max-w-4xl overflow-hidden rounded-lg border border-line bg-surface shadow-overlay">
        <div className="flex items-start justify-between gap-4 border-b border-line bg-surfaceStrong px-4 py-4">
          <div>
            <div className="text-[11px] font-black uppercase tracking-[0.18em] text-accentStrong">{mode === "add" ? "Add Row" : "Edit Row"}</div>
            <h2 className="mt-1 text-xl font-black">{value.Station || "ABSS scope item"}</h2>
          </div>
          <button type="button" onClick={onClose} className="focus-ring rounded-lg border border-line p-2 text-muted hover:text-ink" aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="max-h-[calc(92vh-156px)] overflow-auto p-4">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="grid gap-1">
              <span className="text-[11px] font-black uppercase tracking-[0.14em] text-muted">Department</span>
              <select
                value={value.Department || "Civil"}
                onChange={(event) => onChange({ ...value, Department: event.target.value })}
                className="h-10 rounded-lg border border-line bg-surfaceStrong px-3 text-sm font-bold outline-none focus:border-accent"
              >
                {editableDepartments.map((item) => <option key={item}>{item}</option>)}
              </select>
            </label>
            <label className="grid gap-1">
              <span className="text-[11px] font-black uppercase tracking-[0.14em] text-muted">TDC</span>
              <input
                value={value.TDC || ""}
                onChange={(event) => onChange({ ...value, TDC: event.target.value })}
                className="h-10 rounded-lg border border-line bg-surfaceStrong px-3 text-sm outline-none focus:border-accent"
              />
            </label>
            <label className="grid gap-1 md:col-span-2">
              <span className="text-[11px] font-black uppercase tracking-[0.14em] text-muted">Scope</span>
              <input
                value={value.Scope || ""}
                onChange={(event) => onChange({ ...value, Scope: event.target.value })}
                required
                className="h-10 rounded-lg border border-line bg-surfaceStrong px-3 text-sm outline-none focus:border-accent"
              />
            </label>
            <label className="grid gap-1">
              <span className="text-[11px] font-black uppercase tracking-[0.14em] text-muted">Existing Facility</span>
              <textarea
                value={value.Existing_Facility || ""}
                onChange={(event) => onChange({ ...value, Existing_Facility: event.target.value })}
                rows={5}
                className="rounded-lg border border-line bg-surfaceStrong px-3 py-2 text-sm outline-none focus:border-accent"
              />
            </label>
            <label className="grid gap-1">
              <span className="text-[11px] font-black uppercase tracking-[0.14em] text-muted">Facility under ABSS</span>
              <textarea
                value={value.Facility_Under_ABSS || ""}
                onChange={(event) => onChange({ ...value, Facility_Under_ABSS: event.target.value })}
                rows={5}
                className="rounded-lg border border-line bg-surfaceStrong px-3 py-2 text-sm outline-none focus:border-accent"
              />
            </label>
            <label className="grid gap-1 md:col-span-2">
              <span className="text-[11px] font-black uppercase tracking-[0.14em] text-muted">Remarks</span>
              <textarea
                value={value.Remarks || ""}
                onChange={(event) => onChange({ ...value, Remarks: event.target.value })}
                rows={7}
                className="rounded-lg border border-line bg-surfaceStrong px-3 py-2 text-sm outline-none focus:border-accent"
              />
            </label>
          </div>
        </div>
        <div className="flex flex-col-reverse gap-2 border-t border-line bg-surfaceStrong px-4 py-3 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} className="focus-ring inline-flex h-10 items-center justify-center rounded-lg border border-line px-4 text-sm font-black text-ink hover:border-accent">
            Cancel
          </button>
          <button type="submit" className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-accent bg-accent px-4 text-sm font-black text-white hover:bg-accentStrong">
            <Save size={16} />
            Save
          </button>
        </div>
      </form>
    </div>
  );
}

export default function AbssPage() {
  const [rows, setRows] = useState(abssData.rows || []);
  const [station, setStation] = useState("KGI");
  const [department, setDepartment] = useState("All");
  const [remarkFilter, setRemarkFilter] = useState("All");
  const [query, setQuery] = useState("");
  const [modal, setModal] = useState({ open: false, mode: "add", row: null });
  const [saveState, setSaveState] = useState("Saved");

  useEffect(() => {
    let active = true;
    fetch("/api/abss", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (active && data?.rows?.length) setRows(data.rows);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const stations = useMemo(() => summarizeStations(rows), [rows]);
  const selectedStation = stations.find((item) => item.Station === station) || stations[0];
  const stationRows = useMemo(() => rows.filter((row) => row.Station === station), [rows, station]);

  const filteredRows = useMemo(() => {
    const q = normal(query);
    return stationRows.filter((row) => {
      const deptOk = department === "All" || row.Department === department;
      const remarkOk =
        remarkFilter === "All" ||
        (remarkFilter === "With Remarks" && hasRemarks(row)) ||
        (remarkFilter === "Deficiency" && hasDeficiency(row)) ||
        (remarkFilter === "Poor Quality" && hasPoorQuality(row)) ||
        (remarkFilter === "Blank Remarks" && !hasRemarks(row));
      const queryOk = !q || [row.Scope, row.Existing_Facility, row.Facility_Under_ABSS, row.Remarks, row.TDC].some((value) => normal(value).includes(q));
      return deptOk && remarkOk && queryOk;
    });
  }, [department, query, remarkFilter, stationRows]);

  const counts = useMemo(() => ({
    civil: stationRows.filter((row) => row.Department === "Civil").length,
    electrical: stationRows.filter((row) => row.Department === "Electrical").length,
    st: stationRows.filter((row) => row.Department === "S&T").length,
    remarks: stationRows.filter(hasRemarks).length,
  }), [stationRows]);

  const persist = async (nextRows) => {
    setRows(nextRows);
    setSaveState("Saving");
    try {
      const response = await fetch("/api/abss", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rows: nextRows }),
      });
      if (!response.ok) throw new Error("save failed");
      const data = await response.json();
      if (data?.rows) setRows(data.rows);
      setSaveState("Saved");
    } catch {
      setSaveState("Not saved");
    }
  };

  const openAdd = () => {
    const row = {
      ...emptyRow,
      Station: station,
      Station_Name: selectedStation?.Station_Name || station,
      id: Math.max(0, ...rows.map((item) => Number(item.id) || 0)) + 1,
    };
    setModal({ open: true, mode: "add", row });
  };

  const openEdit = (row) => setModal({ open: true, mode: "edit", row: { ...row } });
  const closeModal = () => setModal({ open: false, mode: "add", row: null });

  const saveModal = async (event) => {
    event.preventDefault();
    const row = { ...modal.row, Station: modal.row.Station || station, Station_Name: modal.row.Station_Name || selectedStation?.Station_Name || station };
    const nextRows = modal.mode === "add" ? [...rows, row] : rows.map((item) => (item.id === row.id ? row : item));
    closeModal();
    await persist(nextRows);
  };

  const deleteRow = async (row) => {
    const ok = window.confirm(`Delete this ${row.Department || ""} row from ${row.Station}?`);
    if (!ok) return;
    await persist(rows.filter((item) => item.id !== row.id));
  };

  const resetFromOriginal = async () => {
    const ok = window.confirm("Reset the table to the last generated source data?");
    if (!ok) return;
    await persist(abssData.rows || []);
  };

  return (
    <main className="abss-page min-h-screen bg-page px-4 py-5 text-ink sm:px-6">
      <style jsx global>{`
        .abss-page {
          min-height: 100vh;
          padding: 20px 24px;
          background: #e8edf1;
          color: #1e2a35;
          font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        .abss-page > div:first-of-type {
          max-width: 1800px;
          margin: 0 auto;
        }

        .abss-page header {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          gap: 16px;
          padding-bottom: 16px;
          border-bottom: 1px solid #c5cfd7;
        }

        .abss-page h1 {
          margin: 4px 0 0;
          font-size: 24px;
          line-height: 1.2;
          font-weight: 900;
        }

        .abss-page p {
          margin: 4px 0 0;
        }

        .abss-page section {
          margin-top: 16px;
        }

        .abss-page button,
        .abss-page input,
        .abss-page select,
        .abss-page textarea {
          font: inherit;
        }

        .abss-page button {
          cursor: pointer;
        }

        .abss-page input,
        .abss-page select,
        .abss-page textarea {
          border: 1px solid #c5cfd7;
          border-radius: 8px;
          background: #f9fbfc;
          color: #1e2a35;
        }

        .abss-page table {
          width: 100%;
          min-width: 1320px;
          border-collapse: collapse;
          background: #eff3f6;
          font-size: 14px;
        }

        .abss-page th {
          position: sticky;
          top: 0;
          z-index: 2;
          padding: 12px;
          border-bottom: 1px solid #c5cfd7;
          background: #f9fbfc;
          color: #5e6b77;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        .abss-page td {
          padding: 12px;
          border-bottom: 1px solid rgba(197, 207, 215, 0.8);
          vertical-align: top;
          white-space: pre-wrap;
          line-height: 1.45;
        }

        .abss-page tr:hover td {
          background: #f9fbfc;
        }

        .abss-page .fixed.inset-0 {
          position: fixed;
          inset: 0;
          z-index: 50;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 12px;
          background: rgba(15, 23, 42, 0.55);
        }

        .abss-page .fixed.inset-0 form {
          width: min(920px, 100%);
          max-height: 92vh;
          overflow: hidden;
          border: 1px solid #c5cfd7;
          border-radius: 8px;
          background: #eff3f6;
          box-shadow: 0 18px 50px rgba(30, 42, 53, 0.22);
        }

        @media (max-width: 900px) {
          .abss-page {
            padding: 16px;
          }

          .abss-page header {
            align-items: flex-start;
            flex-direction: column;
          }
        }
      `}</style>
      <div className="mx-auto max-w-[1800px] space-y-4">
        <header className="flex flex-col gap-3 border-b border-line pb-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-[11px] font-black uppercase tracking-[0.18em] text-accentStrong">ABSS Scope Review</div>
            <h1 className="mt-1 text-2xl font-black">Station-wise Editable Source Table</h1>
            <p className="mt-1 text-sm font-semibold text-muted">
              {selectedStation?.Station_Name || station} | {stationRows.length} rows | Civil {counts.civil}, Electrical {counts.electrical}, S&T {counts.st}, Remarks {counts.remarks}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className={cx("inline-flex h-10 items-center rounded-lg border px-3 text-xs font-black", saveState === "Saved" ? "border-emerald-300 bg-emerald-50 text-emerald-700" : saveState === "Saving" ? "border-blue-300 bg-blue-50 text-blue-700" : "border-red-300 bg-red-50 text-red-700")}>
              {saveState}
            </span>
            <button type="button" onClick={openAdd} className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-accent bg-accent px-3 text-sm font-black text-white shadow-raised transition hover:bg-accentStrong">
              <Plus size={16} />
              Add
            </button>
            <button type="button" onClick={() => exportCsv(filteredRows, station)} className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-line bg-surface px-3 text-sm font-black shadow-raised transition hover:border-accent">
              <Download size={16} />
              Export
            </button>
            <IconButton label="Reset from generated data" onClick={resetFromOriginal}>
              <RotateCcw size={16} />
            </IconButton>
          </div>
        </header>

        <section className="soft-inset soft-scroll flex gap-2 overflow-x-auto rounded-lg border border-line p-2">
          {stations.map((item) => (
            <Chip key={item.Station} active={station === item.Station} onClick={() => setStation(item.Station)} subtext={`${item.row_count} rows`}>
              {item.Station}
            </Chip>
          ))}
        </section>

        <section className="grid gap-3 rounded-lg border border-line bg-surface p-3 shadow-raised lg:grid-cols-[1fr_180px_180px]">
          <label className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search scope, facility, remarks or TDC"
              className="h-10 w-full rounded-lg border border-line bg-surfaceStrong pl-10 pr-9 text-sm outline-none focus:border-accent"
            />
            {query ? (
              <button type="button" onClick={() => setQuery("")} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted hover:text-ink" aria-label="Clear search">
                <X size={16} />
              </button>
            ) : null}
          </label>
          <select value={department} onChange={(event) => setDepartment(event.target.value)} className="h-10 rounded-lg border border-line bg-surfaceStrong px-3 text-sm font-bold outline-none focus:border-accent">
            {departments.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={remarkFilter} onChange={(event) => setRemarkFilter(event.target.value)} className="h-10 rounded-lg border border-line bg-surfaceStrong px-3 text-sm font-bold outline-none focus:border-accent">
            {remarkFilters.map((item) => <option key={item}>{item}</option>)}
          </select>
        </section>

        <section className="overflow-hidden rounded-lg border border-line bg-surface shadow-raised">
          <div className="soft-scroll max-h-[72vh] overflow-auto">
            <table className="w-full min-w-[1320px] border-collapse text-left text-sm">
              <thead className="sticky top-0 z-10 bg-surfaceStrong text-[11px] font-black uppercase tracking-[0.14em] text-muted">
                <tr>
                  <th className="w-[96px] border-b border-line px-3 py-3">Actions</th>
                  <th className="w-[118px] border-b border-line px-3 py-3">Department</th>
                  <th className="w-[190px] border-b border-line px-3 py-3">Scope</th>
                  <th className="w-[170px] border-b border-line px-3 py-3">Existing Facility</th>
                  <th className="w-[250px] border-b border-line px-3 py-3">Facility under ABSS</th>
                  <th className="border-b border-line px-3 py-3">Remarks</th>
                  <th className="w-[90px] border-b border-line px-3 py-3">TDC</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => (
                  <tr key={row.id} className="border-b border-line/70 align-top last:border-0 hover:bg-surfaceStrong">
                    <td className="px-3 py-3">
                      <div className="flex gap-1.5">
                        <IconButton label="Edit row" onClick={() => openEdit(row)}>
                          <Pencil size={15} />
                        </IconButton>
                        <IconButton label="Delete row" tone="danger" onClick={() => deleteRow(row)}>
                          <Trash2 size={15} />
                        </IconButton>
                      </div>
                    </td>
                    <td className="px-3 py-3"><DepartmentPill value={row.Department} /></td>
                    <td className="px-3 py-3 font-semibold"><CellText value={row.Scope} /></td>
                    <td className="px-3 py-3"><CellText value={row.Existing_Facility} muted={!row.Existing_Facility} /></td>
                    <td className="px-3 py-3"><CellText value={row.Facility_Under_ABSS} /></td>
                    <td className="px-3 py-3"><CellText value={row.Remarks} muted={!row.Remarks} /></td>
                    <td className="px-3 py-3 font-bold"><CellText value={row.TDC} muted={!row.TDC} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!filteredRows.length ? (
              <div className="p-6 text-center text-sm font-semibold text-muted">No rows match the selected filters.</div>
            ) : null}
          </div>
        </section>
      </div>
      <EditModal
        open={modal.open}
        mode={modal.mode}
        value={modal.row || emptyRow}
        onChange={(row) => setModal((current) => ({ ...current, row }))}
        onClose={closeModal}
        onSave={saveModal}
      />
    </main>
  );
}
