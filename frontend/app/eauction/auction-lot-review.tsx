'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ChevronDown, ClipboardCheck, History } from 'lucide-react';
import { type Booking, labelDate, labelTime, normalizeTime } from '../../lib/eauction-scheduler';
import { deskflowError, deskflowResponse } from '../../lib/deskflow-errors';

type Proposal = {
  status?: string; value?: string | number; formula?: string; justification?: string; policy_version?: string;
};
type Review = {
  collected_at?: string; key?: string; rate_unit?: string; rule?: string; proposal?: Proposal;
  basis?: { benchmark_source?: string; continuation?: { source?: string; policy?: string } };
  contract?: { contract_id?: string; id?: string; status?: string; source?: string };
  workbook?: { workbook?: string; path?: string; sheet?: string; row?: number };
  precedents?: { date: string; lot: string; outcome: string; accepted_rate?: string; rate_unit?: string; source?: string }[];
};
type Schedule = { catalogue: string; lot: string; start: string; category: string; description: string };
type Event = { at: string } & ({ kind: 'schedule'; data: Schedule } | { kind: 'review'; data: Review });
type Status = 'ready' | 'pending' | 'reviewed' | 'saved';
type Lot = Schedule & { current: boolean; status: Status; reasons: string[]; review: Review; events: Event[] };
type Queue = { checked_at?: string; lots: Lot[] };
type Filter = 'all' | 'ready' | 'reviewed' | 'exceptions';

const statusLabels: Record<Status, string> = { ready: 'Ready for review', pending: 'Needs evidence', reviewed: 'Reviewed', saved: 'Workbook verified' };
const indianTime = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit',
});
const rupees = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });
const monthInIST = () => new Date(Date.now() + 330 * 60000).toISOString().slice(0, 7);
const formatStamp = (stamp: string) => indianTime.format(new Date(stamp));

function worksheetIssue(lot: Lot, bookings: Booking[] | null) {
  const matches = (bookings ?? []).filter(row => row.catalogueId?.trim().toUpperCase() === lot.catalogue.trim().toUpperCase());
  if (!matches.length) return '';
  if (matches.length > 1) return `The schedule workbook has ${matches.length} rows for this catalogue.`;
  const row = matches[0];
  const expectedTime = lot.start.slice(11, 16);
  const workbookTime = row.time ? normalizeTime(row.time) : null;
  const day = lot.start.slice(0, 10);
  if (row.date !== day || workbookTime !== expectedTime) {
    return `IREPS shows ${labelDate(day)} at ${labelTime(expectedTime)} IST. The workbook shows ${labelDate(row.date)} at ${workbookTime ? labelTime(workbookTime) + ' IST' : 'no valid time'}.`;
  }
  const expectedTab = new Intl.DateTimeFormat('en-GB', { month: 'short', timeZone: 'UTC' }).format(new Date(day)) + ' ' + day.slice(2, 4);
  if (row.sheetTab && row.sheetTab.toLowerCase() !== expectedTab.toLowerCase() &&
      /^\p{L}+ \d{2}$/u.test(row.sheetTab)) {
    const canonicalTab = row.sheetTab.replace(/^(\p{L}{3})\p{L}+/u, '$1');
    if (canonicalTab.toLowerCase() !== expectedTab.toLowerCase())
      return `The workbook lists this catalogue in ${row.sheetTab}. Its auction belongs in ${expectedTab}.`;
  }
  if (row.status !== 'scheduled') return `The workbook marks this auction ${row.status}.`;
  return '';
}

function Money({ value }: { value: string | number }) {
  return <>{rupees.format(Number(value))}</>;
}

function ReviewDetails({ lot }: { lot: Lot }) {
  const review = lot.review;
  const proposal = review.proposal;
  const workbook = review.workbook;
  const workbookPath = workbook?.workbook || workbook?.path;
  const source = review.basis?.benchmark_source || review.basis?.continuation?.source;
  return <div className="auction-review-details">
    {proposal?.value != null && <dl className="auction-review-facts">
      <div><dt>Proposed RP</dt><dd><Money value={proposal.value}/> {review.rate_unit}</dd></div>
      {proposal.formula && <div><dt>Calculation</dt><dd>{proposal.formula}</dd></div>}
      {source && <div><dt>Evidence source</dt><dd>{source}</dd></div>}
      {(review.rule || proposal.policy_version) && <div><dt>Rule</dt><dd>{[review.rule?.replaceAll('_', ' '), proposal.policy_version].filter(Boolean).join(' · ')}</dd></div>}
    </dl>}
    {proposal?.justification && <p className="auction-review-remark"><strong>IREPS justification</strong> <small>{proposal.justification.length}/300 characters</small><br/>{proposal.justification}</p>}
    {workbookPath && <p className="hint">Workbook record · {workbookPath}{workbook?.sheet && ` · ${workbook.sheet}`}{workbook?.row && ` · row ${workbook.row}`}</p>}
    {!!review.precedents?.length && <details className="auction-review-history">
      <summary>Prior auction evidence <span>{review.precedents.length}</span></summary>
      <ul>{review.precedents.map((event, index) => <li key={index}>
        <strong>{event.date.slice(0, 10)}</strong> · {event.lot} · {event.outcome}
        {event.accepted_rate && <> · {event.accepted_rate} {event.rate_unit}</>}
        {event.source && <small>{event.source}</small>}
      </li>)}</ul>
    </details>}
    <details className="auction-review-history">
      <summary>Lot history <span>{lot.events.length}</span></summary>
      <ol>{[...lot.events].reverse().map((event, index) => <li key={index}>
        <small>{formatStamp(event.at)} IST</small>
        {event.kind === 'schedule'
          ? <>{index === lot.events.length - 1 ? 'Schedule recorded' : 'Schedule changed'} · {formatStamp(event.data.start)} IST</>
          : <>RP evidence recorded{event.data.proposal?.value != null && <> · <Money value={event.data.proposal.value}/> {event.data.rate_unit}</>}{event.data.proposal?.status && ` · ${event.data.proposal.status.replaceAll('_', ' ')}`}</>}
        {event.kind === 'review' && <>
          {event.data.proposal?.formula && <small>{event.data.proposal.formula}</small>}
          {event.data.basis?.benchmark_source && <small>{event.data.basis.benchmark_source}</small>}
        </>}
      </li>)}</ol>
    </details>
    <Link className="button outline" href={`/deskflow?asset=${encodeURIComponent(lot.lot)}`}>Open Deskflow</Link>
  </div>;
}

export default function AuctionLotReview({ token, scheduleCheckedAt, bookings }:
  { token: string; scheduleCheckedAt?: string; bookings: Booking[] | null }) {
  const [view, setView] = useState<'upcoming' | 'history'>('upcoming');
  const [month, setMonth] = useState(monthInIST);
  const [filter, setFilter] = useState<Filter>('all');
  const [result, setResult] = useState<{ query: string; data?: Queue; error?: string }>();
  const query = view === 'history' ? `?month=${month}` : '';

  useEffect(() => {
    if (view === 'history' && !month) return;
    const controller = new AbortController();
    let busy = false;
    async function load() {
      if (document.hidden || busy) return;
      busy = true;
      try {
        const response = await fetch(`/api/deskflow/auction-lots${query}`, {
          headers: { Authorization: `Bearer ${token}` }, cache: 'no-store',
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(18000)]),
        });
        const data = await deskflowResponse<Queue>(response, 'Auction lot review is unavailable.');
        if (!controller.signal.aborted) setResult({ query, data });
      } catch (error) {
        if (!controller.signal.aborted) {
          setResult(previous => ({
            query, data: previous?.query === query ? previous.data : undefined,
            error: deskflowError(error, 'Auction lot review is unavailable.'),
          }));
        }
      } finally {
        busy = false;
      }
    }
    void load();
    const timer = window.setInterval(load, 20000);
    document.addEventListener('visibilitychange', load);
    return () => {
      controller.abort();
      clearInterval(timer);
      document.removeEventListener('visibilitychange', load);
    };
  }, [token, query, view, month, scheduleCheckedAt]);

  const data = result?.query === query ? result.data : undefined;
  const error = result?.query === query ? result.error : undefined;
  const lots = useMemo(() => (data?.lots ?? []).map(lot => ({ ...lot, conflict: worksheetIssue(lot, bookings) })), [data, bookings]);
  const ready = lots.filter(lot => lot.status === 'ready' && !lot.conflict).length;
  const exceptions = lots.filter(lot => lot.status === 'pending' || lot.conflict).length;
  const reviewed = lots.length - ready - exceptions;
  const visible = lots.filter(lot => filter === 'all' || (filter === 'exceptions'
    ? lot.status === 'pending' || lot.conflict
    : filter === 'reviewed' ? ['reviewed', 'saved'].includes(lot.status) && !lot.conflict
    : lot.status === filter && !lot.conflict));
  const next = view === 'upcoming' ? lots[0] : undefined;

  return <section className="work-area auction-review" aria-labelledby="auction-review-heading">
    <div className="auction-review-header">
      <div>
        <h2 id="auction-review-heading"><ClipboardCheck size={19} aria-hidden/> Auction lot review</h2>
        {next && <p>Next auction · <strong>{formatStamp(next.start)} IST</strong></p>}
      </div>
      <div className="auction-review-view" aria-label="Auction lot view">
        <button type="button" className="button" aria-pressed={view === 'upcoming'} onClick={() => { setView('upcoming'); setFilter('all'); }}>Upcoming</button>
        <button type="button" className="button" aria-pressed={view === 'history'} onClick={() => { setView('history'); setFilter('all'); }}><History size={14} aria-hidden/> History</button>
      </div>
    </div>
    <div className="auction-review-meta">
      {view === 'history' && <label>Auction month <input type="month" value={month} onChange={event => setMonth(event.target.value)} /></label>}
      {data?.checked_at && <span>IREPS schedule checked {formatStamp(data.checked_at)} IST</span>}
      {bookings === null && <span>Workbook schedule comparison unavailable</span>}
    </div>
    {error && <p className="schedule-pdf-error auction-review-notice" role="status">{error}{data && ' Showing the last loaded results.'}</p>}
    {!data && !error && <p className="hint" role="status">{view === 'history' && !month ? 'Choose an auction month.' : 'Loading auction lots…'}</p>}
    {data && <>
      <div className="auction-review-filters" aria-label="Filter auction lots">
        {([
          ['all', lots.length, 'All lots'], ['ready', ready, 'Ready for review'],
          ['exceptions', exceptions, 'Need attention'], ['reviewed', reviewed, 'Reviewed'],
        ] as const).map(([value, count, label]) => <button type="button" key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>
          <strong>{count}</strong><span>{label}</span>
        </button>)}
      </div>
      {visible.length ? <div className="auction-review-list">{visible.map(lot => <details className="auction-review-lot" key={`${lot.catalogue}|${lot.lot}`}>
        <summary>
          <div className="auction-review-id"><strong>{lot.lot}</strong><small>{lot.catalogue} · {lot.category}</small></div>
          <span className="auction-review-date">{view === 'history' && !lot.current && <>Recorded · </>}{labelDate(lot.start.slice(0, 10))} · {labelTime(lot.start.slice(11, 16))} IST</span>
          <span className={`auction-review-state ${lot.conflict ? 'conflict' : lot.status}`}>{lot.conflict ? 'Schedule conflict' : statusLabels[lot.status]}</span>
          <ChevronDown className="auction-review-chevron" size={16} aria-hidden/>
          {(lot.conflict || lot.reasons[0]) && <span className="auction-review-reason">{lot.conflict || lot.reasons[0]}</span>}
        </summary>
        {lot.description && <p className="auction-review-description">{lot.description}</p>}
        {(lot.conflict || lot.reasons.length > 0) && <ul className="auction-review-reasons">
          {lot.conflict && <li>{lot.conflict}</li>}{lot.reasons.map((reason, index) => <li key={index}>{reason}</li>)}
        </ul>}
        <ReviewDetails lot={lot}/>
      </details>)}</div> : <p className="auction-review-empty">{lots.length
        ? 'No lots match this filter.'
        : view === 'history' ? 'No lot history has been recorded for this month.'
        : data.checked_at ? 'No upcoming SBC lots in the latest IREPS schedule.' : 'Update from IREPS to load the next auction.'}</p>}
    </>}
  </section>;
}
