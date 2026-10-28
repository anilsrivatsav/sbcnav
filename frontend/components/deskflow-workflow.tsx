"use client";

export type LibraryStatus={workbook_rows:number;auction_records:number;catalogues_saved:number;outcomes_pending?:number;outcomes_due?:number;coverage:{from_date:string;through:string|null;complete:boolean};proposals:Record<string,number>;policy_version:string};
export type WorkflowAction="collect"|"history"|"sync-workbooks"|"save-reviewed"|"cancel";
const dateText=(value:string)=>value.slice(0,10).split("-").reverse().join("-");
const secondary="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-50";

export function DeskflowWorkflow({library,working,collecting,archiveBusy,reviewed,command,updateDesktop,filter,setFilter}:{library?:LibraryStatus;working:boolean;collecting:boolean;archiveBusy:boolean;reviewed:number;command:(action:WorkflowAction)=>void;updateDesktop:()=>void;filter:string;setFilter:(value:string)=>void}){
  return <>
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="font-semibold">Collect, review, save</h2>
      <p className="mt-1 text-sm text-slate-600">Update RP-pending lots, match verified history, review exceptions, then save the same proposal and justification to Excel and SBC NAV.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button disabled={working||archiveBusy} onClick={()=>command("sync-workbooks")} className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Update Deskflow</button>
        <button disabled={working||archiveBusy||!reviewed} onClick={()=>command("save-reviewed")} className="rounded-lg border border-emerald-700 px-3 py-2 text-sm font-medium text-emerald-800 disabled:opacity-50">Save reviewed proposals ({reviewed})</button>
        {collecting&&<button onClick={()=>command("cancel")} className={secondary}>Stop after saved progress</button>}
      </div>
    </section>
    {library&&<section aria-label="Historical database coverage" className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="grid gap-3 text-sm sm:grid-cols-3">{[["Local workbook rows",library.workbook_rows],["Stored EA outcomes",library.auction_records],["Completed catalogue checkpoints",library.catalogues_saved]].map(([label,value])=><div key={label}><p className="text-slate-500">{label}</p><p className="mt-1 text-lg font-semibold tabular-nums">{Number(value).toLocaleString("en-IN")}</p></div>)}</div>
      <p className={`mt-3 text-sm ${library.coverage.complete?"text-emerald-800":"text-amber-800"}`}>{library.coverage.complete?`Historical outcome coverage verified from ${dateText(library.coverage.from_date)} through ${dateText(library.coverage.through!)}. Future runs refresh new and recent results.`:`Initial outcome backfill is incomplete. Completed catalogues are retained. Coverage starts ${dateText(library.coverage.from_date)}.`}</p>
      {library.outcomes_pending!==undefined&&<p className="mt-2 text-sm text-slate-600">{library.outcomes_pending} lots awaiting an outcome; {library.outcomes_due||0} eligible for checking after their auction date. Delayed decisions stay on the follow-up list.</p>}
      <p className="mt-1 text-xs text-slate-500">Unavailable bid rates, awardees and contract evidence remain flagged for review. No RP is submitted on IREPS.</p>
    </section>}
    <details className="rounded-lg border border-slate-200 bg-white p-4"><summary className="cursor-pointer text-sm font-medium">Collection and desktop options</summary><div className="mt-3 flex flex-wrap gap-2"><button disabled={working} onClick={()=>command("collect")} className={secondary}>Collect pending lots only</button><button disabled={working} onClick={()=>command("history")} className={secondary}>Build / resume EA outcomes history</button><button disabled={working} onClick={updateDesktop} className={secondary}>Update desktop app</button></div></details>
    <label className="block text-sm">Review status<select value={filter} onChange={e=>setFilter(e.target.value)} className="ml-2 rounded border border-slate-300 bg-white px-2 py-1"><option value="all">All current lots</option><option value="needs_evidence">Needs evidence</option><option value="ready_for_review">Ready for review</option><option value="reviewed">Reviewed, awaiting save</option><option value="saved">Saved</option></select></label>
  </>;
}
