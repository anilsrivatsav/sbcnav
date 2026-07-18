"use client";

import { useMemo, useState } from "react";
import { ChevronRight, Search, X } from "lucide-react";

export const cx = (...classes) => classes.filter(Boolean).join(" ");

const buttonClasses = {
  primary: "bg-accent text-white shadow-glow hover:bg-accent/90",
  secondary: "border border-line bg-surface/80 text-ink hover:border-accent hover:bg-surfaceStrong",
  ghost: "text-muted hover:bg-surface/75 hover:text-ink",
  danger: "border border-red-300/70 bg-surface/80 text-red-600 hover:bg-red-500/10",
};

export function Button({ children, variant = "primary", size = "md", className = "", ...props }) {
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

export function Badge({ children, tone = "neutral" }) {
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

export function Surface({ children, className = "" }) {
  return <section className={cx("glass rounded-3xl border p-5", className)}>{children}</section>;
}

export function KpiCard({ icon: Icon, label, value, subtext }) {
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

export function Panel({ title, subtitle, action, children, className = "" }) {
  return (
    <section className={cx("glass rounded-2xl border p-5", className)}>
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

export function Tabs({ tabs, value, onChange }) {
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

export function SearchInput({ value, onChange, placeholder = "Search current view" }) {
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

export function FormField({ label, children }) {
  return (
    <label className="grid gap-1">
      <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">{label}</span>
      {children}
    </label>
  );
}

export function FilterSelect({ label, value, onChange, options }) {
  return (
    <FormField label={label}>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="h-11 rounded-xl border border-line bg-surface/85 px-3 text-sm outline-none focus:border-accent">
        {options.map((item) => (
          <option key={item} value={item}>{item}</option>
        ))}
      </select>
    </FormField>
  );
}

export function FilterBar({ filters }) {
  if (!filters.length) return null;
  return (
    <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {filters.map(([label, value, onChange, options]) => (
        <FilterSelect key={label} label={label} value={value} onChange={onChange} options={options} />
      ))}
    </div>
  );
}

export function ListShell({ children }) {
  return <div className="soft-scroll max-h-[62vh] overflow-auto pr-1">{children}</div>;
}

export function ListFooter({ shown, total, onMore, onLess }) {
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

export function EmptyState({ title = "No records found", message = "Try changing search or filters." }) {
  return (
    <div className="rounded-2xl border border-dashed border-line bg-surface/55 p-6 text-center">
      <div className="text-sm font-black text-ink">{title}</div>
      <div className="mt-1 text-sm text-muted">{message}</div>
    </div>
  );
}

const cellValue = (column, row) => {
  const value = column.value ? column.value(row) : row[column.key];
  return value === null || value === undefined ? "" : value;
};

const csvEscape = (value) => {
  const text = String(value === null || value === undefined ? "" : value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};

export function DataTable({ columns, rows, getKey, onRowClick, emptyTitle = "No records found", fileName = "export.csv", pageSizeOptions = [10, 25, 50, 100] }) {
  const [sort, setSort] = useState({ key: columns[0]?.key, direction: "asc" });
  const [filters, setFilters] = useState({});
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(pageSizeOptions[1] || 25);
  const [compact, setCompact] = useState(true);

  const filteredRows = useMemo(() => {
    return rows.filter((row) => columns.every((column) => {
      const query = String(filters[column.key] || "").trim().toLowerCase();
      if (!query) return true;
      return String(cellValue(column, row)).toLowerCase().includes(query);
    }));
  }, [columns, filters, rows]);

  const sortedRows = useMemo(() => {
    const column = columns.find((item) => item.key === sort.key);
    const direction = sort.direction === "desc" ? -1 : 1;
    return [...filteredRows].sort((a, b) => {
      const av = cellValue(column || {}, a);
      const bv = cellValue(column || {}, b);
      const an = Number(av);
      const bn = Number(bv);
      if (!Number.isNaN(an) && !Number.isNaN(bn)) return (an - bn) * direction;
      return String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: "base" }) * direction;
    });
  }, [columns, filteredRows, sort]);

  const pageCount = Math.max(1, Math.ceil(sortedRows.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const visibleRows = sortedRows.slice((safePage - 1) * pageSize, safePage * pageSize);

  const toggleSort = (key) => {
    setSort((current) => current.key === key ? { key, direction: current.direction === "asc" ? "desc" : "asc" } : { key, direction: "asc" });
  };

  const exportVisible = () => {
    const header = columns.map((column) => csvEscape(column.label)).join(",");
    const body = visibleRows.map((row) => columns.map((column) => csvEscape(cellValue(column, row))).join(",")).join("\n");
    const blob = new Blob([[header, body].filter(Boolean).join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (!rows.length) return <EmptyState title={emptyTitle} />;
  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 rounded-2xl border border-line bg-surface/55 p-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-xs font-bold text-muted">{sortedRows.length} filtered rows from {rows.length}</div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => setCompact((value) => !value)}>
            {compact ? "Detailed view" : "Compact view"}
          </Button>
          <Button variant="secondary" size="sm" onClick={exportVisible}>
            Export visible
          </Button>
          <select value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }} className="h-9 rounded-xl border border-line bg-surface px-2 text-xs font-bold outline-none">
            {pageSizeOptions.map((option) => <option key={option} value={option}>{option} rows</option>)}
          </select>
        </div>
      </div>
      <div className="soft-scroll max-h-[58vh] overflow-auto rounded-2xl border border-line bg-surface/55">
        <table className="w-full min-w-[860px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-surfaceStrong/95 text-[11px] font-black uppercase tracking-[0.16em] text-muted backdrop-blur">
            <tr>
              {columns.map((column) => (
                <th key={column.key} className="border-b border-line px-3 py-2">
                  <button type="button" onClick={() => toggleSort(column.key)} className="flex w-full items-center justify-between gap-2 text-left">
                    <span>{column.label}</span>
                    <span className="text-[10px]">{sort.key === column.key ? (sort.direction === "asc" ? "ASC" : "DESC") : "SORT"}</span>
                  </button>
                </th>
              ))}
            </tr>
            <tr>
              {columns.map((column) => (
                <th key={`${column.key}-filter`} className="border-b border-line px-3 py-2">
                  <input
                    value={filters[column.key] || ""}
                    onChange={(event) => { setFilters((current) => ({ ...current, [column.key]: event.target.value })); setPage(1); }}
                    placeholder="Filter"
                    className="h-8 w-full rounded-lg border border-line bg-surface/85 px-2 text-xs normal-case tracking-normal outline-none placeholder:text-muted focus:border-accent"
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, index) => (
              <tr
                key={getKey(row, index)}
                onClick={() => onRowClick?.(row)}
                className={cx("border-b border-line/70 transition last:border-0", onRowClick ? "cursor-pointer hover:bg-accentSoft/60" : "")}
              >
                {columns.map((column) => (
                  <td key={column.key} className={cx("align-top text-ink", compact ? "px-3 py-2 text-xs" : "px-4 py-4 text-sm")}>
                    {column.render ? column.render(row) : cellValue(column, row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {!visibleRows.length ? <div className="p-4"><EmptyState title="No rows match column filters" /></div> : null}
      </div>
      <div className="flex flex-col gap-2 rounded-2xl border border-line bg-surface/55 px-3 py-2 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
        <span>Page {safePage} of {pageCount}</span>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={safePage <= 1}>Previous</Button>
          <Button variant="secondary" size="sm" onClick={() => setPage((value) => Math.min(pageCount, value + 1))} disabled={safePage >= pageCount}>Next</Button>
        </div>
      </div>
    </div>
  );
}

export function KeyValueGrid({ rows }) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {rows.map(([label, value]) => (
        <div key={label} className="rounded-xl border border-line bg-surface p-3">
          <dt className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">{label}</dt>
          <dd className="mt-1 text-sm font-semibold text-ink">{value === null || value === undefined || value === "" ? "NA" : String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Modal({ open, title, subtitle, onClose, children }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-3">
      <div className="glass max-h-[92vh] w-full max-w-5xl overflow-hidden rounded-3xl border shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-line bg-surface/60 px-4 py-4">
          <div>
            <div className="text-[11px] font-black uppercase tracking-[0.2em] text-accent">Workspace</div>
            <h3 className="mt-1 text-xl font-black text-ink">{title}</h3>
            {subtitle ? <p className="mt-1 text-sm text-muted">{subtitle}</p> : null}
          </div>
          <button type="button" onClick={onClose} className="focus-ring rounded-full border border-line bg-surface p-2 text-ink transition hover:border-accent hover:bg-surfaceStrong">
            <X size={18} />
          </button>
        </div>
        <div className="soft-scroll max-h-[calc(92vh-88px)] overflow-auto p-4">{children}</div>
      </div>
    </div>
  );
}
