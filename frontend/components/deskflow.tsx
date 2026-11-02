"use client";

import {useCallback, useEffect, useState, type FormEvent} from "react";
import {ArrowLeft, LockKeyhole} from "lucide-react";
import Link from "next/link";
import {deskflowError, deskflowResponse} from "../lib/deskflow-errors";

import {DeskflowAnalysis} from "./deskflow-analysis";
import {type ReviewLot} from "./deskflow-review";
import {DeskflowWorkflow,type LibraryStatus,type WorkflowAction} from "./deskflow-workflow";

type History={outcome?:string;source?:string;date:string;status:string;status_date:string;lot:string;category:string;description:string;accepted_rate:string|number;rate_unit:string};
type Verification={status:"verified"|"needs_review"|"blocked";revision:string;checks:{code:string;state:"pass"|"warn"|"fail";message:string}[]};
type Lot=ReviewLot&{key:string;asset:string;lot:string;category:string;subcategory:string;date:string;station:string;train:string;catalogue:string;details:string;rate_unit:string;value:string|number|null;justification:string;calculation_notes?:string;rule:string;history:History[];verification?:Verification;auctionSchedule?:{date:string;scheduleId:string;catalogueId:string;status:string}};
type Progress={busy:boolean;phase:string;message:string;error?:string};
type ArchiveSync={phase:string;message:string;error?:string;busy?:boolean;revision?:string;rows?:number;records?:number};
type Overview={analysis_library?:{revision:string;encoding:string;data:string};collected_at:string|null;categories:string[];lots:Lot[];progress:Progress;desktop_connected?:boolean;archive_sync?:ArchiveSync;history_library?:LibraryStatus};
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
  const [libraryCategories,setLibraryCategories]=useState<string[]>([]);
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
    const response=await fetch(`${LOCAL}/overview`,{headers:{Authorization:`Bearer ${accessToken}`},cache:"no-store",signal:AbortSignal.timeout(18000)});
    if(response.status===401){sessionStorage.removeItem(TOKEN_KEY);setToken("");setOverview(null);setError("Session expired. Unlock Deskflow again.");throw Error("Session expired. Unlock Deskflow again.");}
    const data=await deskflowResponse<Overview>(response,"Lots could not be refreshed.");setOverview(data);setOverviewError("");
  },[]);
  const fetchSoftwareUpdate=useCallback(async(accessToken:string)=>{
    const response=await fetch(`${LOCAL}/software-update`,{headers:{Authorization:`Bearer ${accessToken}`},cache:"no-store",signal:AbortSignal.timeout(8000)});
    setSoftwareUpdate(await deskflowResponse<SoftwareUpdate>(response,"Desktop update status could not be checked."));setSoftwareError("");
  },[]);
  useEffect(()=>{if(!token)return;let stopped=false;let timer:ReturnType<typeof setTimeout>;
    const refresh=async()=>{await Promise.allSettled([fetchOverview(token).catch(e=>setOverviewError(deskflowError(e,"Evidence could not be refreshed."))),fetchSoftwareUpdate(token).catch(e=>setSoftwareError(deskflowError(e,"Desktop update status could not be checked.")))]);if(!stopped)timer=setTimeout(refresh,15000);};
    void refresh();return()=>{stopped=true;clearTimeout(timer);};},[token,fetchOverview,fetchSoftwareUpdate]);

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
  const updateBusy=["starting","checking","downloading","installing"].includes(softwareUpdate?.phase||"");
  const working=busy||!overview?.desktop_connected||overview?.progress.busy||updateBusy;
  return <main className="min-h-screen bg-slate-50 px-4 py-6 text-slate-900 sm:px-8">
    <div className="mx-auto max-w-6xl">
      <header className="mb-5 flex items-center justify-between gap-4"><div className="flex items-center gap-3"><Link href="/" aria-label="Back to SBCNAV" className="rounded-lg border border-slate-200 bg-white p-2"><ArrowLeft size={18}/></Link><h1 className="text-2xl font-bold">Deskflow</h1></div>{token&&<button onClick={()=>{sessionStorage.removeItem(TOKEN_KEY);setToken("");setOverview(null);}} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">Lock</button>}</header>
      {!token?<form onSubmit={unlock} className="mx-auto mt-16 max-w-sm rounded-xl border border-slate-200 bg-white p-6"><LockKeyhole className="mb-3 text-emerald-700" size={24}/><h2 className="text-lg font-semibold">Unlock Deskflow</h2><label htmlFor="deskflow-password" className="mt-5 block text-sm">Password</label><input id="deskflow-password" type="password" autoFocus required value={password} onChange={e=>setPassword(e.target.value)} className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2"/><button disabled={busy} className="mt-4 w-full rounded-lg bg-emerald-700 px-4 py-2 font-semibold text-white disabled:opacity-50">Unlock</button>{error&&<p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}</form>:<div className="space-y-4">
        <label className="block text-sm font-medium">Search asset, train, station or lot<input type="search" value={assetQuery} onChange={e=>setAssetQuery(e.target.value)} placeholder="e.g. 17294, Yelahanka, parking" className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2"/></label>
        <details className="rounded-xl border border-slate-200 bg-white p-4"><summary className="cursor-pointer text-sm font-semibold text-slate-700">Refresh, sync and review tools</summary><div className="mt-4"><DeskflowWorkflow library={overview?.history_library} working={Boolean(working)} collecting={Boolean(overview?.progress.busy)} archiveBusy={Boolean(overview?.archive_sync?.busy)} reviewed={overview?.lots.filter(lot=>lot.proposal?.status==="reviewed").length||0} command={action=>void collect(action)} updateDesktop={()=>void updateDesktop()} filter={reviewFilter} setFilter={setReviewFilter}/></div></details>
        {error&&<div role="alert" className="flex justify-between gap-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800"><span>{error}</span><button onClick={()=>setError("")} aria-label="Dismiss command error" className="underline">Dismiss</button></div>}
        {overviewError&&<p role="alert" className="text-sm text-red-700">{overviewError} {overview?"Showing previously loaded rows.":""}</p>}
        {(overview?.progress.message||overview?.progress.error)&&<p role={overview.progress.error||overview.progress.phase==="error"?"alert":"status"} className={`text-sm ${overview.progress.error||overview.progress.phase==="error"?"text-red-700":"text-slate-600"}`}>{overview.progress.error?`${overview.progress.message} ${overview.progress.error}`:overview.progress.message}</p>}
        {overview&&!overview.desktop_connected&&<p role="status" className="text-sm text-amber-800">Desktop companion offline. Open it on Windows to refresh or sync.</p>}
        {overview?.archive_sync&&<p role={overview.archive_sync.error||overview.archive_sync.phase==="error"?"alert":"status"} className={`text-sm ${overview.archive_sync.error||overview.archive_sync.phase==="error"?"text-red-700":"text-slate-600"}`}>Workbook sync: {overview.archive_sync.error||overview.archive_sync.message}</p>}
        {softwareError&&<p role="alert" className="text-sm text-red-700">{softwareError}</p>}
        {(softwareUpdate&&softwareUpdate.phase!=="ready")&&<p role={softwareUpdate?.phase==="error"||softwareUpdate?.error?"alert":"status"} className={`text-sm ${softwareUpdate?.phase==="error"||softwareUpdate?.error?"text-red-700":"text-slate-600"}`}>Desktop app: {softwareUpdate?.error||softwareUpdate?.message}</p>}
        <div className="flex flex-wrap items-center justify-between gap-3"><label className="min-w-0 max-w-full text-sm font-medium">Category<select value={category} onChange={event=>{setCategory(event.target.value);}} className="mt-1 block w-full max-w-full rounded-lg border border-slate-300 bg-white px-3 py-2 sm:ml-3 sm:mt-0 sm:inline-block sm:w-auto sm:max-w-[24rem]"><option value="">All categories</option>{[...new Set([...(overview?.categories||[]),...libraryCategories])].sort().map(item=><option key={item}>{item}</option>)}</select></label><span className="text-xs text-slate-500">Search includes all captured history</span></div>
        <DeskflowAnalysis onCategories={setLibraryCategories} packed={overview?.analysis_library} lots={overview?.lots||[]} query={assetSearch} category={category} reviewFilter={reviewFilter} token={token} disabled={Boolean(working)} onChanged={()=>{void fetchOverview(token).catch(e=>setOverviewError(deskflowError(e,"Evidence could not be refreshed.")));}}/>

      </div>}
    </div>
  </main>;
}
