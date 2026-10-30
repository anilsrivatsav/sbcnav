"use client";

import {useCallback, useEffect, useMemo, useState, type FormEvent} from "react";
import {ArrowLeft, LockKeyhole} from "lucide-react";
import Link from "next/link";
import {DeskflowWorkbookHistory} from "./deskflow-workbook-history";
import {deskflowError, deskflowResponse} from "../lib/deskflow-errors";
import {loadWorkbookWorkings, type WorkbookWorking} from "../lib/deskflow-history";
import {latestAuctionFirst} from "../lib/deskflow-dates";

import {DeskflowReview,type ReviewLot} from "./deskflow-review";
import {DeskflowWorkflow,type LibraryStatus,type WorkflowAction} from "./deskflow-workflow";

type History={outcome?:string;source?:string;date:string;status:string;status_date:string;lot:string;category:string;description:string;accepted_rate:string|number;rate_unit:string};
type Verification={status:"verified"|"needs_review"|"blocked";revision:string;checks:{code:string;state:"pass"|"warn"|"fail";message:string}[]};
type Lot=ReviewLot&{key:string;asset:string;lot:string;category:string;subcategory:string;date:string;station:string;train:string;catalogue:string;details:string;rate_unit:string;value:string|number|null;justification:string;calculation_notes?:string;rule:string;history:History[];verification?:Verification;auctionSchedule?:{date:string;scheduleId:string;catalogueId:string;status:string}};
type Progress={busy:boolean;phase:string;message:string;error?:string};
type ArchiveSync={phase:string;message:string;error?:string;busy?:boolean;revision?:string;rows?:number;records?:number};
type Overview={collected_at:string|null;categories:string[];lots:Lot[];progress:Progress;desktop_connected?:boolean;archive_sync?:ArchiveSync;history_library?:LibraryStatus};
type SoftwareUpdate={phase:string;message:string;error?:string;revision?:string|null};
const LOCAL="/api/deskflow";
const TOKEN_KEY="sbcnav-deskflow-token";
const dateText=(value?:string)=>value?value.slice(0,10).split("-").reverse().join("-"):"—";
const valueText=(value:number|string|null|undefined)=>value===null||value===undefined||value===""?"Pending evidence":`₹${Number(value).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2})}`;

export function Deskflow(){
  const [token,setToken]=useState("");
  const [password,setPassword]=useState("");
  const [overview,setOverview]=useState<Overview|null>(null);
  const [category,setCategory]=useState("");
  const [selectedKey,setSelectedKey]=useState("");
  const [assetQuery,setAssetQuery]=useState("");
  const [assetSearch,setAssetSearch]=useState("");
  const [reviewFilter,setReviewFilter]=useState("all");
  useEffect(()=>{const timer=setTimeout(()=>setAssetSearch(assetQuery.trim()),300);return()=>clearTimeout(timer);},[assetQuery]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [overviewError,setOverviewError]=useState("");
  const [softwareError,setSoftwareError]=useState("");
  const [softwareUpdate,setSoftwareUpdate]=useState<SoftwareUpdate|null>(null);
  useEffect(()=>{setToken(sessionStorage.getItem(TOKEN_KEY)||"");},[]);
  const fetchOverview=useCallback(async(accessToken:string)=>{
    const response=await fetch(`${LOCAL}/overview`,{headers:{Authorization:`Bearer ${accessToken}`},cache:"no-store",signal:AbortSignal.timeout(8000)});
    if(response.status===401){sessionStorage.removeItem(TOKEN_KEY);setToken("");setOverview(null);setError("Session expired. Unlock Deskflow again.");throw Error("Session expired. Unlock Deskflow again.");}
    const data=await deskflowResponse<Overview>(response,"Lots could not be refreshed.");setOverview(data);setOverviewError("");
  },[]);
  const fetchSoftwareUpdate=useCallback(async(accessToken:string)=>{
    const response=await fetch(`${LOCAL}/software-update`,{headers:{Authorization:`Bearer ${accessToken}`},cache:"no-store",signal:AbortSignal.timeout(8000)});
    setSoftwareUpdate(await deskflowResponse<SoftwareUpdate>(response,"Desktop update status could not be checked."));setSoftwareError("");
  },[]);
  useEffect(()=>{if(!token)return;const refresh=()=>{void fetchOverview(token).catch(e=>setOverviewError(deskflowError(e,"Lots could not be refreshed.")));void fetchSoftwareUpdate(token).catch(e=>setSoftwareError(deskflowError(e,"Desktop update status could not be checked.")));};refresh();const timer=setInterval(refresh,4000);return()=>clearInterval(timer);},[token,fetchOverview,fetchSoftwareUpdate]);
  async function unlock(event:FormEvent){event.preventDefault();setBusy(true);setError("");try{
    const response=await fetch(`${LOCAL}/unlock`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password}),signal:AbortSignal.timeout(8000)});
    const data=await deskflowResponse<{token:string}>(response,"Unable to unlock Deskflow.");
    sessionStorage.setItem(TOKEN_KEY,data.token);setPassword("");setToken(data.token);
  }catch(e){setError(deskflowError(e,"Unable to unlock Deskflow."));}finally{setBusy(false);}}
  async function collect(action:WorkflowAction) {setBusy(true);setError("");try{
    const response=await fetch(`${LOCAL}/${action}`,{method:"POST",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},body:"{}",signal:AbortSignal.timeout(10000)});
    await deskflowResponse(response,"Command could not start.");await fetchOverview(token);
  }catch(e){setError(deskflowError(e,"Command could not start."));}finally{setBusy(false);}}
  async function updateDesktop(){setBusy(true);setError("");try{
    const response=await fetch(`${LOCAL}/software-update`,{method:"POST",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},body:"{}",signal:AbortSignal.timeout(10000)});
    const data=await deskflowResponse<SoftwareUpdate&{queued?:boolean}>(response,"Desktop update could not start.");setSoftwareUpdate(data.queued?{phase:"starting",message:"Desktop update queued. Waiting for the Windows companion."}:data);
  }catch(e){setError(deskflowError(e,"Desktop update could not start."));}finally{setBusy(false);}}
  const lots=useMemo(()=>overview?.lots.filter(lot=>(reviewFilter==="all"||lot.proposal?.status===reviewFilter)&&(!category||lot.category===category)&&(!assetSearch||[lot.asset,lot.lot,lot.station,lot.train,lot.catalogue,lot.details,...lot.history.map(row=>row.description)].join(" ").toLowerCase().includes(assetSearch.toLowerCase()))).sort(latestAuctionFirst)||[],[overview,category,assetSearch,reviewFilter]);
  const selected=lots.find(lot=>lot.key===selectedKey)||lots[0];
  const updateBusy=["starting","checking","downloading","installing"].includes(softwareUpdate?.phase||"");
  const working=busy||!overview?.desktop_connected||overview?.progress.busy||updateBusy;
  return <main className="min-h-screen bg-slate-50 px-4 py-6 text-slate-900 sm:px-8">
    <div className="mx-auto max-w-6xl">
      <header className="mb-5 flex items-center justify-between gap-4"><div className="flex items-center gap-3"><Link href="/" aria-label="Back to SBCNAV" className="rounded-lg border border-slate-200 bg-white p-2"><ArrowLeft size={18}/></Link><h1 className="text-2xl font-bold">Deskflow</h1></div>{token&&<button onClick={()=>{sessionStorage.removeItem(TOKEN_KEY);setToken("");setOverview(null);}} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">Lock</button>}</header>
      {!token?<form onSubmit={unlock} className="mx-auto mt-16 max-w-sm rounded-xl border border-slate-200 bg-white p-6"><LockKeyhole className="mb-3 text-emerald-700" size={24}/><h2 className="text-lg font-semibold">Unlock Deskflow</h2><label htmlFor="deskflow-password" className="mt-5 block text-sm">Password</label><input id="deskflow-password" type="password" autoFocus required value={password} onChange={e=>setPassword(e.target.value)} className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2"/><button disabled={busy} className="mt-4 w-full rounded-lg bg-emerald-700 px-4 py-2 font-semibold text-white disabled:opacity-50">Unlock</button>{error&&<p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}</form>:<div className="space-y-4">
        <label className="block text-sm font-medium">Search asset, train, station or lot<input type="search" value={assetQuery} onChange={e=>setAssetQuery(e.target.value)} placeholder="e.g. 17294, Yelahanka, parking" className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2"/></label>
        <DeskflowWorkflow library={overview?.history_library} working={Boolean(working)} collecting={Boolean(overview?.progress.busy)} archiveBusy={Boolean(overview?.archive_sync?.busy)} reviewed={overview?.lots.filter(lot=>lot.proposal?.status==="reviewed").length||0} command={action=>void collect(action)} updateDesktop={()=>void updateDesktop()} filter={reviewFilter} setFilter={setReviewFilter}/>
        {error&&<div role="alert" className="flex justify-between gap-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800"><span>{error}</span><button onClick={()=>setError("")} aria-label="Dismiss command error" className="underline">Dismiss</button></div>}
        {overviewError&&<p role="alert" className="text-sm text-red-700">{overviewError} {overview?"Showing previously loaded rows.":""}</p>}
        {(overview?.progress.message||overview?.progress.error)&&<p role={overview.progress.error||overview.progress.phase==="error"?"alert":"status"} className={`text-sm ${overview.progress.error||overview.progress.phase==="error"?"text-red-700":"text-slate-600"}`}>{overview.progress.error?`${overview.progress.message} ${overview.progress.error}`:overview.progress.message}</p>}
        {overview&&!overview.desktop_connected&&<p role="status" className="text-sm text-amber-800">Desktop companion offline. Open it on Windows to refresh or sync.</p>}
        {overview?.archive_sync&&<p role={overview.archive_sync.error||overview.archive_sync.phase==="error"?"alert":"status"} className={`text-sm ${overview.archive_sync.error||overview.archive_sync.phase==="error"?"text-red-700":"text-slate-600"}`}>Workbook sync: {overview.archive_sync.error||overview.archive_sync.message}</p>}
        {softwareError&&<p role="alert" className="text-sm text-red-700">{softwareError}</p>}
        {(softwareUpdate&&softwareUpdate.phase!=="ready")&&<p role={softwareUpdate?.phase==="error"||softwareUpdate?.error?"alert":"status"} className={`text-sm ${softwareUpdate?.phase==="error"||softwareUpdate?.error?"text-red-700":"text-slate-600"}`}>Desktop app: {softwareUpdate?.error||softwareUpdate?.message}</p>}
        <div className="flex flex-wrap items-center justify-between gap-3"><label className="text-sm font-medium">Category<select value={category} onChange={event=>{setCategory(event.target.value);setSelectedKey("");}} className="ml-3 rounded-lg border border-slate-300 bg-white px-3 py-2"><option value="">All categories</option>{overview?.categories.map(item=><option key={item}>{item}</option>)}</select></label><span className="text-sm text-slate-500">{lots.length} current lots</span></div>
        {lots.length?<div className="grid items-start gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
          <nav aria-label="Current lots" className="space-y-2 lg:sticky lg:top-4 lg:max-h-[80vh] lg:overflow-y-auto">{lots.map(lot=><button key={lot.key} aria-pressed={selected?.key===lot.key} onClick={()=>setSelectedKey(lot.key)} className={`w-full rounded-xl border p-4 text-left transition ${selected?.key===lot.key?"border-emerald-600 bg-emerald-50 ring-1 ring-emerald-600":"border-slate-200 bg-white hover:border-emerald-400"}`}><span className="block text-sm font-semibold">{lot.asset||`Lot ${lot.lot}`}</span><span className="mt-2 block text-xs text-slate-600">Lot {lot.lot} · {dateText(lot.date)}</span><span className="mt-1 block text-xs text-slate-500">{lot.category}{lot.station?` · ${lot.station}`:""}</span></button>)}</nav>
          {selected&&<LotCard key={selected.key} lot={selected} token={token} revision={overview?.archive_sync?.revision} disabled={Boolean(working)} onChanged={()=>{void fetchOverview(token).catch(e=>setOverviewError(deskflowError(e,"Lots could not be refreshed.")));}}/>}
        </div>:<p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">{!overview?overviewError?"Lots could not be loaded.":"Loading lots…":assetSearch?"No current lots match. See previous similar assets below.":"No current lots collected."}</p>}
        <details open className="rounded-lg border border-slate-200 bg-white p-4"><summary className="cursor-pointer text-sm font-medium">{assetSearch?"Previous similar assets":"Workbook history"}</summary><div className="mt-4"><DeskflowWorkbookHistory token={token} revision={overview?.archive_sync?.revision} assetSearch={assetSearch}/></div></details>
      </div>}
    </div>
  </main>;
}

const shortIssue:Record<string,string>={asset_identity:"Confirm this asset and its earlier lots.",benchmark_source:"Add the benchmark source.",standard_conditions:"Review the applicable conditions.",bid_and_lar:"Confirm the accepted rate and awardee.",previous_outcome:"Add the previous auction result.",contract_link:"Check the contract rate and awardee against the sold lot.",local_workbook:"Save the reviewed value to the workbook.",history_coverage:"Refresh auction history.",scheduled_freshness:"Refresh current lots.",auction_schedule:"Check the auction schedule."};
function LotCard({lot,token,revision,disabled,onChanged}:{lot:Lot;token:string;revision?:string;disabled:boolean;onChanged:()=>void}){
  const [working,setWorking]=useState<WorkbookWorking>();
  const [workingError,setWorkingError]=useState("");
  const query=/^\d{5}/.exec(lot.lot)?.[0]||lot.lot;
  useEffect(()=>{
    let current=true;setWorking(undefined);setWorkingError("");
    loadWorkbookWorkings(token,query,revision).then(rows=>{
      const normalize=(value:string)=>value.toUpperCase().replace(/[^A-Z0-9]/g,"");
      const matches=rows.filter(row=>row.date===lot.date.slice(0,10)&&(/^\d{5}$/.test(query)?new RegExp(`(^|\\D)${query}(?!\\d)`).test(row.asset):normalize(row.asset)===normalize(lot.lot)));
      if(current&&matches.length===1)setWorking(matches[0]);
    }).catch(reason=>{if(current)setWorkingError(deskflowError(reason,"Current workbook value could not be loaded."));});
    return()=>{current=false;};
  },[token,query,revision,lot.date]);
  const displayedValue=working?.rp??lot.value;
  const displayedJustification=working?.justification||lot.justification;
  const workbookDiffers=working?.rp!=null&&lot.value!=null&&Math.round(working.rp*100)!==Math.round(Number(lot.value)*100);
  const checks=lot.verification?.checks||[];
  const issues=checks.filter(check=>check.state!=="pass");
  const issue=issues.find(check=>check.state==="fail")||issues[0];
  return <article className="min-w-0 space-y-5" aria-label={`Lot ${lot.lot} details`}>
    <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Lot {lot.lot} · {dateText(lot.date)}</p><h2 className="mt-2 text-xl font-bold">{lot.asset||lot.lot}</h2><p className="mt-2 text-sm text-slate-500">{[lot.category,lot.subcategory,lot.station,lot.train].filter(Boolean).join(" · ")}</p></div></div>{lot.details&&<p className="mt-4 whitespace-pre-line text-sm leading-6 text-slate-600">{lot.details}</p>}</section>
    <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 sm:p-6"><h3 className="text-sm font-semibold text-emerald-900">Proposed value</h3><p className="mt-2 text-3xl font-bold tabular-nums text-emerald-950">{valueText(displayedValue)}{displayedValue!==null&&lot.rate_unit&&<span className="ml-2 text-sm font-medium">{lot.rate_unit}</span>}</p>{working?.rp!=null&&<p className="mt-2 text-xs text-emerald-800">Saved workbook · {working.portfolio} · {working.sheet}, row {working.row}</p>}<h3 className="mt-5 text-sm font-semibold">Justification</h3><p className="mt-2 whitespace-pre-line text-sm leading-7">{displayedJustification||"Pending evidence."}</p>
      {workingError&&<p role="alert" className="mt-1 text-xs text-red-700">{workingError}</p>}
      {workbookDiffers?<p className="mt-1 text-xs text-amber-800">Review: Saved workbook value differs from the calculation.</p>:issue&&<p className={`mt-1 text-xs ${issue.state==="fail"&&lot.value!==null?"text-red-700":"text-amber-800"}`}>{issue.state==="fail"?lot.value===null?"Needs evidence: ":"Error: ":"Review: "}{shortIssue[issue.code]||issue.message}</p>}
      {!lot.verification&&<p className="mt-1 text-xs text-amber-800">Review: Verification is pending.</p>}
    </section>
    <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6"><h3 className="text-lg font-bold">Previous data &amp; auction results</h3><p className="mt-1 mb-4 text-xs text-slate-500">Previous workbook values and justifications alongside IREPS results, newest first. Confirm that the asset and scope match.</p><PreviousResults lot={lot} token={token} revision={revision}/></section>
    <details className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-600"><summary className="cursor-pointer font-medium text-emerald-800">Asset details &amp; verification</summary>
        <dl className="mt-3 grid gap-x-4 gap-y-2 sm:grid-cols-2"><div><dt className="text-xs text-slate-500">Asset</dt><dd>{lot.asset}</dd></div><div><dt className="text-xs text-slate-500">Category</dt><dd>{[lot.category,lot.subcategory].filter(Boolean).join(" / ")}</dd></div><div><dt className="text-xs text-slate-500">Catalogue</dt><dd>{lot.catalogue}</dd></div><div><dt className="text-xs text-slate-500">Station / train</dt><dd>{[lot.station,lot.train].filter(Boolean).join(" / ")||"—"}</dd></div><div><dt className="text-xs text-slate-500">Rate unit</dt><dd>{lot.rate_unit||"—"}</dd></div><div><dt className="text-xs text-slate-500">Calculation rule</dt><dd>{lot.rule||"Pending evidence"}</dd></div></dl>
        {lot.details&&<p className="mt-3">{lot.details}</p>}
        {lot.calculation_notes&&<p className="mt-3">{lot.calculation_notes}</p>}
        <h3 className="mt-4 font-semibold">Full verification checks</h3>
        <ul className="mt-2 space-y-1 text-xs">{[...issues,...checks.filter(check=>check.state==="pass")].map(check=><li key={check.code} className={check.state==="fail"?"text-red-700":check.state==="warn"?"text-amber-800":"text-emerald-800"}>{check.state==="fail"?"Error: ":check.state==="warn"?"Review: ":"Passed: "}{check.message}</li>)}</ul>
        {lot.auctionSchedule?<p className="mt-3 text-xs">Auction {lot.auctionSchedule.status} · {dateText(lot.auctionSchedule.date)} · {lot.auctionSchedule.scheduleId} · {lot.auctionSchedule.catalogueId}</p>:<p className="mt-3 text-xs">No schedule row linked yet.</p>}
        <DeskflowReview lot={lot} token={token} disabled={disabled} onChanged={onChanged}/>
        <Link href={`/eauction?category=${encodeURIComponent(lot.category)}&lotKey=${encodeURIComponent(lot.key)}`} className="mt-2 inline-block text-xs text-emerald-700 underline">Open auction schedule</Link>
      </details>
  </article>;
}

function PreviousResults({lot,token,revision}:{lot:Lot;token:string;revision?:string}){
  const [workings,setWorkings]=useState<WorkbookWorking[]>([]);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  const [retry,setRetry]=useState(0);
  const query=/^\d{5}/.exec(lot.lot)?.[0]||lot.lot;
  useEffect(()=>{
    let current=true;setLoading(true);setError("");setWorkings([]);
    loadWorkbookWorkings(token,query,revision).then(rows=>{if(current)setWorkings(rows);}).catch(reason=>{if(current)setError(deskflowError(reason,"Previous RP could not be loaded."));}).finally(()=>{if(current)setLoading(false);});
    return()=>{current=false;};
  },[token,query,revision,lot.history.length,retry]);
  const history=[...lot.history].sort(latestAuctionFirst);
  const workbookOnly=workings.filter(item=>item.date<lot.date.slice(0,10)&&!history.some(row=>row.date.slice(0,10)===item.date)).sort(latestAuctionFirst);
  const entries=[...history.map(row=>({kind:"ireps" as const,date:row.date,row})),...workbookOnly.map(item=>({kind:"workbook" as const,date:item.date,item}))].sort(latestAuctionFirst);
  return <div className="text-sm">{loading&&<p className="mb-2 text-slate-500">Loading previous RP…</p>}{error&&<p role="alert" className="mb-2 text-red-700">{error} <button onClick={()=>setRetry(n=>n+1)} className="underline">Retry</button></p>}<ul className="space-y-3">{entries.map((entry,index)=>{
    if(entry.kind==="workbook")return <PreviousWorkbookCard key={entry.item.id} item={entry.item}/>;
    const row=entry.row;
    const outcome=row.outcome||({Failed:"No Bids",Running:"Sold",Completed:"Sold",Foreclosed:"Sold"}[row.status]||row.status);
    const matches=workings.filter(item=>item.date===row.date.slice(0,10));
    const working=matches.length===1?matches[0]:undefined;
    return <li key={`${row.date}-${row.lot}-${index}`} className="rounded-xl border border-slate-200 bg-slate-50 p-4"><div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{dateText(row.date)} · Lot {row.lot}</span><span className={`rounded px-2 py-0.5 font-medium ${outcome==="Sold"?"bg-emerald-50 text-emerald-800":outcome==="No Bids"?"bg-amber-50 text-amber-900":"bg-slate-100 text-slate-700"}`}>{outcome==="No Bids"?"No bids":outcome}</span></div>{!loading&&!error&&<div className="mt-1 space-y-1 text-slate-600">{matches.length>1?<p>Multiple workbook matches — check the exact asset.</p>:<><p title={working?`${working.asset} · ${working.portfolio} · ${working.sheet}, row ${working.row}`:undefined}><b>Workbook RP:</b> {working?.rp!=null?valueText(working.rp):"Not recorded"}</p><p className="whitespace-pre-line leading-6"><b>Justification:</b> {working?.justification||"Not recorded"}</p>{working&&<p className="text-slate-500">Workbook asset: {working.asset}</p>}</>}</div>}{outcome==="Sold"&&row.accepted_rate&&<p className="mt-1 text-slate-600"><b>IREPS accepted rate:</b> {valueText(row.accepted_rate)} {row.rate_unit}</p>}</li>;
  })}</ul>{!loading&&!error&&!history.length&&!workbookOnly.length&&<p className="text-slate-500">No previous data collected for this lot.</p>}</div>;
}

function PreviousWorkbookCard({item}:{item:WorkbookWorking}){
  return <li className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="font-semibold">{dateText(item.date)} · {item.asset}</p><p className="mt-2"><b>Workbook RP:</b> {item.rp==null?"Not recorded":valueText(item.rp)}</p><p className="mt-2 whitespace-pre-line leading-6"><b>Justification:</b> {item.justification||"Not recorded"}</p><p className="mt-2 text-xs text-slate-500">{item.portfolio} · {item.sheet}, row {item.row} · IREPS result not collected</p></li>;
}
