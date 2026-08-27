"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Eye, Pencil, Plus, Search, X } from "lucide-react";

export const cx = (...classes) => classes.filter(Boolean).join(" ");

const buttonClasses = {
  primary: "border border-accent bg-accent text-white shadow-raised hover:bg-accentStrong active:shadow-pressed",
  secondary: "soft-control text-ink hover:border-accent hover:text-accentStrong active:shadow-pressed",
  ghost: "border border-transparent text-muted hover:border-line hover:bg-surfaceStrong hover:text-ink",
  danger: "soft-control border-red-400/70 text-red-600 hover:bg-red-500/10 active:shadow-pressed",
};

export function Button({ children, variant = "primary", size = "md", className = "", ...props }: any) {
  return (
    <button
      type="button"
      className={cx(
        "focus-ring inline-flex items-center justify-center gap-2 rounded-lg font-extrabold transition disabled:cursor-not-allowed disabled:opacity-60",
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

export function Badge({ children, tone = "neutral" }: any) {
  const tones = {
    neutral: "border-line bg-surfaceStrong text-muted",
    accent: "border-accent/30 bg-accentSoft text-accentStrong",
    danger: "border-red-300/70 bg-red-500/10 text-red-600",
    warning: "border-amber-300/70 bg-amber-500/10 text-amber-700",
    success: "border-emerald-300/70 bg-emerald-500/10 text-emerald-700",
  };
  return (
    <span className={cx("inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-black uppercase tracking-[0.12em]", tones[tone])}>
      {children}
    </span>
  );
}

export function Surface({ children, className = "" }: any) {
  return <section className={cx("soft-surface rounded-lg border p-5", className)}>{children}</section>;
}

export function KpiCard({ icon: Icon, label, value, subtext }: any) {
  return (
    <div className="soft-surface rounded-lg border p-5 transition hover:-translate-y-0.5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-black uppercase tracking-[0.18em] text-muted">{label}</div>
          <div className="mt-2 text-2xl font-black text-ink">{value}</div>
        </div>
        <div className="soft-raised rounded-lg border border-accent/20 bg-accentSoft p-3 text-accentStrong">
          <Icon size={18} />
        </div>
      </div>
      <div className="mt-3 text-xs font-semibold text-muted">{subtext}</div>
    </div>
  );
}

export function Panel({ title, subtitle, action, children, className = "" }: any) {
  return (
    <section className={cx("soft-surface rounded-lg border p-5", className)}>
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

export function Tabs({ tabs, value, onChange }: any) {
  return (
    <div className="soft-inset soft-scroll flex gap-2 overflow-x-auto rounded-lg border border-line p-1.5">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const active = value === tab.value;
        return (
          <button
            key={tab.value}
            type="button"
            onClick={() => onChange(tab.value)}
            className={cx(
              "focus-ring inline-flex h-10 shrink-0 items-center gap-2 rounded-md px-3 text-xs font-black uppercase tracking-[0.12em] transition",
              active ? "bg-accent text-white shadow-raised" : "text-muted hover:bg-surfaceStrong hover:text-ink",
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

export function SearchInput({ value, onChange, placeholder = "Search current view" }: any) {
  return (
    <label className="relative block w-full">
      <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="soft-inset h-11 w-full rounded-lg border border-line pl-10 pr-3 text-sm outline-none placeholder:text-muted focus:border-accent"
        placeholder={placeholder}
      />
    </label>
  );
}

export function FormField({ label, children }: any) {
  return (
    <label className="grid gap-1">
      <span className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">{label}</span>
      {children}
    </label>
  );
}

export function FilterSelect({ label, value, onChange, options }: any) {
  return (
    <FormField label={label}>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="soft-inset h-11 rounded-lg border border-line px-3 text-sm outline-none focus:border-accent">
        {options.map((item) => (
          <option key={item} value={item}>{item}</option>
        ))}
      </select>
    </FormField>
  );
}

export function FilterBar({ filters }: any) {
  if (!filters.length) return null;
  return (
    <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {filters.map(([label, value, onChange, options]) => (
        <FilterSelect key={label} label={label} value={value} onChange={onChange} options={options} />
      ))}
    </div>
  );
}

export function ListShell({ children }: any) {
  return <div className="soft-scroll max-h-[62vh] overflow-auto pr-1">{children}</div>;
}

export function ListFooter({ shown, total, onMore, onLess }: any) {
  if (total <= shown && shown <= 24) return null;
  return (
    <div className="soft-inset mt-4 flex flex-col items-center justify-between gap-3 rounded-lg border border-line px-4 py-3 text-sm text-muted sm:flex-row">
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

export function EmptyState({ title = "No records found", message = "Try changing search or filters." }: any) {
  return (
    <div className="soft-inset rounded-lg border border-dashed border-line p-6 text-center">
      <div className="text-sm font-black text-ink">{title}</div>
      <div className="mt-1 text-sm text-muted">{message}</div>
    </div>
  );
}

const cellValue = (column, row) => {
  const value = column.value ? column.value(row) : row[column.key];
  return value === null || value === undefined ? "" : value;
};

const normalizeText = (value) => String(value === null || value === undefined ? "" : value).toLowerCase().replace(/[–—]/g, "-").replace(/\s+/g, " ").trim();

const csvEscape = (value) => {
  const text = String(value === null || value === undefined ? "" : value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};

export function DataTable({ columns, rows, getKey, onRowClick, onView, onEdit, onAdd, renderExpanded, emptyTitle = "No records found", fileName = "export.csv", pageSizeOptions = [10, 25, 50, 100], defaultPageSize, enableColumnFilters = true }: any) {
  const hasActions = Boolean(onView || onEdit || onRowClick || renderExpanded);
  const [filters, setFilters] = useState({});
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(defaultPageSize || pageSizeOptions[1] || 25);
  const [compact, setCompact] = useState(true);
  const [showFilters, setShowFilters] = useState(false);
  const [expandedKey, setExpandedKey] = useState(null);

  useEffect(() => {
    setPage(1);
    setFilters({});
    setExpandedKey(null);
  }, [rows]);

  const filteredRows = useMemo(() => {
    return rows.filter((row) => columns.every((column) => {
      const query = normalizeText(filters[column.key]);
      if (!query) return true;
      return normalizeText(cellValue(column, row)).includes(query);
    }));
  }, [columns, filters, rows]);

  const displayRows = filteredRows;

  const pageCount = Math.max(1, Math.ceil(displayRows.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const visibleRows = displayRows.slice((safePage - 1) * pageSize, safePage * pageSize);

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

  if (!rows.length) return <div className="space-y-3"><EmptyState title={emptyTitle} />{onAdd ? <Button size="sm" onClick={onAdd}><Plus size={14} /> Add</Button> : null}</div>;
  return (
    <div className="space-y-3">
      <div className="soft-inset flex flex-col gap-2 rounded-lg border border-line p-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-xs font-bold text-muted">{displayRows.length} filtered rows from {rows.length}</div>
        <div className="flex flex-wrap gap-2">
          {onAdd ? <Button size="sm" onClick={onAdd}><Plus size={14} /> Add</Button> : null}
          {enableColumnFilters ? <Button variant="ghost" size="sm" onClick={() => setShowFilters((value) => !value)}>{showFilters ? "Hide filters" : "Filter columns"}</Button> : null}
          <Button variant="secondary" size="sm" onClick={() => setCompact((value) => !value)}>
            {compact ? "Detailed view" : "Compact view"}
          </Button>
          <Button variant="secondary" size="sm" onClick={exportVisible}>
            Export visible
          </Button>
          <select value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }} className="soft-inset h-9 rounded-lg border border-line px-2 text-xs font-bold outline-none">
            {pageSizeOptions.map((option) => <option key={option} value={option}>{option} rows</option>)}
          </select>
        </div>
      </div>
      <div className="soft-inset soft-scroll max-h-[58vh] overflow-auto rounded-lg border border-line">
        <table className="w-full min-w-[860px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-surfaceStrong text-[11px] font-black uppercase tracking-[0.16em] text-muted">
            <tr>
              {columns.map((column) => (
                <th key={column.key} className="border-b border-line px-3 py-2">
                  <span>{column.label}</span>
                </th>
              ))}
              {hasActions ? <th className="border-b border-line px-3 py-2 text-right">Actions</th> : null}
            </tr>
            {enableColumnFilters && showFilters ? <tr>
              {columns.map((column) => (
                <th key={`${column.key}-filter`} className="border-b border-line px-3 py-2">
                  <input
                    value={filters[column.key] || ""}
                    onChange={(event) => { setFilters((current) => ({ ...current, [column.key]: event.target.value })); setPage(1); }}
                    placeholder="Filter"
                    className="soft-inset h-8 w-full rounded-md border border-line px-2 text-xs normal-case tracking-normal outline-none placeholder:text-muted focus:border-accent"
                  />
                </th>
              ))}
              {hasActions ? <th className="border-b border-line px-3 py-2" /> : null}
            </tr> : null}
          </thead>
          <tbody>
            {visibleRows.map((row, index) => (
              <>
                <tr
                  key={getKey(row, index)}
                  onClick={() => onRowClick?.(row)}
                  onKeyDown={(event) => {
                    if (onRowClick && (event.key === "Enter" || event.key === " ")) {
                      event.preventDefault();
                      onRowClick(row);
                    }
                  }}
                  tabIndex={onRowClick ? 0 : undefined}
                  className={cx("border-b border-line/70 transition last:border-0", onRowClick ? "cursor-pointer hover:bg-accentSoft/60 focus:bg-accentSoft/60 focus:outline-none" : "")}
                >
                  {columns.map((column) => (
                    <td key={column.key} className={cx("align-top text-ink", compact ? "px-3 py-2 text-xs" : "px-4 py-4 text-sm")}>
                      {column.render ? column.render(row) : cellValue(column, row)}
                    </td>
                  ))}
                  {hasActions ? (
                    <td className={cx("align-top text-right", compact ? "px-3 py-2" : "px-4 py-4")}>
                      <div className="flex justify-end gap-1">
                        {renderExpanded ? <Button variant="ghost" size="sm" title={expandedKey === getKey(row, index) ? "Collapse payments" : "Expand payments"} aria-label={expandedKey === getKey(row, index) ? "Collapse payments" : "Expand payments"} onClick={(event) => { event.stopPropagation(); setExpandedKey((current) => current === getKey(row, index) ? null : getKey(row, index)); }}><ChevronDown size={14} className={cx("transition", expandedKey === getKey(row, index) ? "rotate-180" : "")} /></Button> : null}
                        {(onView || onRowClick) ? <Button variant="ghost" size="sm" title="View" aria-label="View" onClick={(event) => { event.stopPropagation(); (onView || onRowClick)(row); }}><Eye size={14} /></Button> : null}
                        {onEdit ? <Button variant="ghost" size="sm" title="Edit" aria-label="Edit" onClick={(event) => { event.stopPropagation(); onEdit(row); }}><Pencil size={14} /></Button> : null}
                      </div>
                    </td>
                  ) : null}
                </tr>
                {renderExpanded && expandedKey === getKey(row, index) ? <tr key={`${getKey(row, index)}-expanded`} className="border-b border-line/70 bg-accentSoft/20"><td colSpan={columns.length + (hasActions ? 1 : 0)} className="px-4 py-3">{renderExpanded(row)}</td></tr> : null}
              </>
            ))}
          </tbody>
        </table>
        {!visibleRows.length ? <div className="p-4"><EmptyState title="No rows match column filters" /></div> : null}
      </div>
      <div className="soft-inset flex flex-col gap-2 rounded-lg border border-line px-3 py-2 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
        <span>Showing {displayRows.length ? (safePage - 1) * pageSize + 1 : 0}–{Math.min(safePage * pageSize, displayRows.length)} of {displayRows.length} · Page {safePage} of {pageCount}</span>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={safePage <= 1}>Previous</Button>
          <Button variant="secondary" size="sm" onClick={() => setPage((value) => Math.min(pageCount, value + 1))} disabled={safePage >= pageCount}>Next</Button>
        </div>
      </div>
    </div>
  );
}

export function KeyValueGrid({ rows }: any) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {rows.map(([label, value]) => (
        <div key={label} className="soft-raised rounded-lg border border-line p-3">
          <dt className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">{label}</dt>
          <dd className="mt-1 text-sm font-semibold text-ink">{value === null || value === undefined || value === "" ? "NA" : String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Modal({ open, title, subtitle, onClose, children }: any) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event) => event.key === "Escape" && onClose();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose, open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-3">
      <div role="dialog" aria-modal="true" aria-label={title} className="max-h-[92vh] w-full max-w-5xl overflow-hidden rounded-lg border border-line bg-surface shadow-overlay">
        <div className="flex items-start justify-between gap-4 border-b border-line bg-surfaceStrong px-4 py-4">
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

export function BottomSheet({ open, title, subtitle, onClose, children }: any) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event) => event.key === "Escape" && onClose();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose, open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/55 px-0 pt-10 sm:px-3" onMouseDown={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="soft-surface flex max-h-[88dvh] w-full max-w-5xl flex-col overflow-hidden rounded-t-lg border border-b-0 shadow-overlay"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex justify-center py-2">
          <span className="h-1 w-12 rounded-full bg-line" aria-hidden="true" />
        </div>
        <header className="flex items-start justify-between gap-4 border-b border-line px-4 pb-4 sm:px-6">
          <div className="min-w-0">
            <div className="text-[11px] font-black uppercase tracking-[0.18em] text-accent">Station snapshot</div>
            <h2 className="mt-1 truncate text-xl font-black text-ink sm:text-2xl">{title}</h2>
            {subtitle ? <p className="mt-1 text-sm text-muted">{subtitle}</p> : null}
          </div>
          <button type="button" onClick={onClose} className="focus-ring soft-control shrink-0 rounded-full p-2 text-ink transition hover:border-accent active:shadow-pressed" aria-label="Close station snapshot">
            <X size={18} />
          </button>
        </header>
        <div className="soft-scroll min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">{children}</div>
      </section>
    </div>
  );
}
