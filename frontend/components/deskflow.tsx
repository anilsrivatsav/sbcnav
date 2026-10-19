"use client";

import {useCallback, useEffect, useMemo, useState, type FormEvent} from "react";
import {ArrowLeft, LockKeyhole, RefreshCw} from "lucide-react";
import Link from "next/link";
import {DeskflowWorkbookHistory} from "./deskflow-workbook-history";
import {deskflowError, deskflowResponse} from "../lib/deskflow-errors";

type History={date:string;status:string;status_date:string;lot:string;category:string;description:string;accepted_rate:string|number;rate_unit:string};
type Verification={status:"verified"|"needs_review"|"blocked";revision:string;checks:{code:string;state:"pass"|"warn"|"fail";message:string}[]};
type Lot={key:string;asset:string;lot:string;category:string;subcategory:string;date:string;station:string;train:string;catalogue:string;details:string;rate_unit:string;value:string|number|null;justification:string;rule:string;history:History[];verification?:Verification;auctionSchedule?:{date:string;scheduleId:string;catalogueId:string;status:string}};
type Progress={busy:boolean;phase:string;message:string;error?:string};
type ArchiveSync={phase:string;message:string;error?:string;busy?:boolean;revision?:string;rows?:number;records?:number};
type Overview={collected_at:string|null;categories:string[];lots:Lot[];progress:Progress;desktop_connected?:boolean;archive_sync?:ArchiveSync};
type SoftwareUpdate={phase:string;message:string;error?:string;revision?:string|null};
const LOCAL="/api/deskflow";
const TOKEN_KEY="sbcnav-deskflow-token";
const dateText=(value?:string)=>value?value.slice(0,10).split("-").reverse().join("-"):"—";
const valueText=(value:number|string|null|undefined)=>value===null||value===undefined||value===""?"Pending evidence":`₹${Number(value).toLocaleString("en-IN",{maximumFractionDigits:2})}`;

export function Deskflow(){
  const [token,setToken]=useState("");
  const [password,setPassword]=useState("");
  const [overview,setOverview]=useState<Overview|null>(null);
  const [category,setCategory]=useState("");
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
    setCategory(current=>data.categories.includes(current)?current:"");
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
  async function collect(action:"collect"|"history"|"sync-workbooks") {setBusy(true);setError("");try{
    const response=await fetch(`${LOCAL}/${action}`,{method:"POST",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},body:"{}",signal:AbortSignal.timeout(10000)});
    await deskflowResponse(response,"Command could not start.");await fetchOverview(token);
  }catch(e){setError(deskflowError(e,"Command could not start."));}finally{setBusy(false);}}
  async function updateDesktop(){setBusy(true);setError("");try{
    const response=await fetch(`${LOCAL}/software-update`,{method:"POST",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},body:"{}",signal:AbortSignal.timeout(10000)});
    const data=await deskflowResponse<SoftwareUpdate&{queued?:boolean}>(response,"Desktop update could not start.");setSoftwareUpdate(data.queued?{phase:"starting",message:"Desktop update queued. Waiting for the Windows companion."}:data);
  }catch(e){setError(deskflowError(e,"Desktop update could not start."));}finally{setBusy(false);}}
  const lots=useMemo(()=>overview?.lots.filter(lot=>!category||lot.category===category)||[],[overview,category]);
  const updateBusy=["starting","checking","downloading","installing"].includes(softwareUpdate?.phase||"");
  const working=busy||!overview?.desktop_connected||overview?.progress.busy||updateBusy;
  return <main className="min-h-screen bg-slate-50 px-4 py-6 text-slate-900 sm:px-8">
    <div className="mx-auto max-w-6xl">
      <header className="mb-5 flex items-center justify-between gap-4"><div className="flex items-center gap-3"><Link href="/" aria-label="Back to SBCNAV" className="rounded-lg border border-slate-200 bg-white p-2"><ArrowLeft size={18}/></Link><h1 className="text-2xl font-bold">Deskflow</h1></div>{token&&<button onClick={()=>{sessionStorage.removeItem(TOKEN_KEY);setToken("");setOverview(null);}} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">Lock</button>}</header>
      {!token?<form onSubmit={unlock} className="mx-auto mt-16 max-w-sm rounded-xl border border-slate-200 bg-white p-6"><LockKeyhole className="mb-3 text-emerald-700" size={24}/><h2 className="text-lg font-semibold">Unlock Deskflow</h2><label htmlFor="deskflow-password" className="mt-5 block text-sm">Password</label><input id="deskflow-password" type="password" autoFocus required value={password} onChange={e=>setPassword(e.target.value)} className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2"/><button disabled={busy} className="mt-4 w-full rounded-lg bg-emerald-700 px-4 py-2 font-semibold text-white disabled:opacity-50">Unlock</button>{error&&<p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}</form>:<div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2"><label htmlFor="deskflow-category" className="sr-only">Category</label><select id="deskflow-category" value={category} onChange={e=>setCategory(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">All categories</option>{overview?.categories.map(item=><option key={item}>{item}</option>)}</select><button disabled={working} onClick={()=>collect("collect")} className="inline-flex items-center gap-2 rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"><RefreshCw size={15}/>Collect lots</button><button disabled={working||!overview?.lots.length} onClick={()=>collect("history")} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50">Collect live history</button><span className="ml-auto text-xs text-slate-500">{overview?.collected_at?`Updated ${dateText(overview.collected_at)}`:""}</span></div>
        <div className="flex flex-wrap items-center gap-2"><button disabled={working||overview?.archive_sync?.busy} onClick={()=>collect("sync-workbooks")} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50">Sync local workbooks</button><button disabled={working} onClick={updateDesktop} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50">Update desktop app</button></div>
        {error&&<div role="alert" className="flex justify-between gap-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800"><span>{error}</span><button onClick={()=>setError("")} aria-label="Dismiss command error" className="underline">Dismiss</button></div>}
        {overviewError&&<p role="alert" className="text-sm text-red-700">{overviewError} {overview?"Showing previously loaded rows.":""}</p>}
        {(overview?.progress.message||overview?.progress.error)&&<p role={overview.progress.error||overview.progress.phase==="error"?"alert":"status"} className={`text-sm ${overview.progress.error||overview.progress.phase==="error"?"text-red-700":"text-slate-600"}`}>{overview.progress.error?`${overview.progress.message} ${overview.progress.error}`:overview.progress.message}</p>}
        {overview&&!overview.desktop_connected&&<p role="status" className="text-sm text-amber-800">Desktop companion offline. Open it on Windows to refresh or sync.</p>}
        {overview?.archive_sync&&<p role={overview.archive_sync.error||overview.archive_sync.phase==="error"?"alert":"status"} className={`text-sm ${overview.archive_sync.error||overview.archive_sync.phase==="error"?"text-red-700":"text-slate-600"}`}>Workbook sync: {overview.archive_sync.error||overview.archive_sync.message}</p>}
        {softwareError&&<p role="alert" className="text-sm text-red-700">{softwareError}</p>}
        {(softwareUpdate&&softwareUpdate.phase!=="ready")&&<p role={softwareUpdate?.phase==="error"||softwareUpdate?.error?"alert":"status"} className={`text-sm ${softwareUpdate?.phase==="error"||softwareUpdate?.error?"text-red-700":"text-slate-600"}`}>Desktop app: {softwareUpdate?.error||softwareUpdate?.message}</p>}
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white"><table className="w-full min-w-[640px] text-left text-sm"><caption className="sr-only">Auction date, lot number, proposed value and justification</caption><thead className="border-b border-slate-200 bg-slate-100 text-slate-700"><tr><th scope="col" className="w-32 px-4 py-3">Auction date</th><th scope="col" className="w-24 px-4 py-3">Lot number</th><th scope="col" className="w-36 px-4 py-3">Proposed value (₹)</th><th scope="col" className="px-4 py-3">Justification</th></tr></thead><tbody>{lots.map(lot=><LotRow key={lot.key} lot={lot}/>)}{!lots.length&&<tr><td colSpan={4} className="px-4 py-8 text-center text-slate-500">{!overview?overviewError?"Rows could not be loaded.":"Loading lots…":"No lots in this category."}</td></tr>}</tbody></table></div>
        <details open className="rounded-lg border border-slate-200 bg-white p-4"><summary className="cursor-pointer text-sm font-medium">Workbook history</summary><div className="mt-4"><DeskflowWorkbookHistory token={token} revision={overview?.archive_sync?.revision}/></div></details>
      </div>}
    </div>
  </main>;
}

const shortIssue:Record<string,string>={asset_identity:"Confirm this asset and its earlier lots.",benchmark_source:"Add the benchmark source.",standard_conditions:"Review the applicable conditions.",bid_and_lar:"Confirm the accepted rate and awardee.",previous_outcome:"Add the previous auction result.",contract_link:"Check the contract rate and awardee against the sold lot.",local_workbook:"Save the reviewed value to the workbook.",history_coverage:"Refresh auction history.",scheduled_freshness:"Refresh current lots.",auction_schedule:"Check the auction schedule."};
function LotRow({lot}:{lot:Lot}){
  const checks=lot.verification?.checks||[];
  const issues=checks.filter(check=>check.state!=="pass");
  const issue=issues.find(check=>check.state==="fail")||issues[0];
  return <tr className="border-b border-slate-200 align-top last:border-0">
    <td className="whitespace-nowrap px-4 py-3">{dateText(lot.date)}</td>
    <td className="px-4 py-3 font-medium">{lot.lot}</td>
    <td className="whitespace-nowrap px-4 py-3 tabular-nums">{valueText(lot.value).replace(/^₹/,"")}</td>
    <td className="px-4 py-3"><p className="leading-6">{lot.justification?.replace(/\s+/g," ").trim()||"Pending evidence."}</p>
      {issue&&<p className={`mt-1 text-xs ${issue.state==="fail"?"text-red-700":"text-amber-800"}`}>{issue.state==="fail"?"Error: ":"Review: "}{shortIssue[issue.code]||issue.message}</p>}
      {!lot.verification&&<p className="mt-1 text-xs text-amber-800">Review: Verification is pending.</p>}
      <details className="mt-2 text-sm text-slate-600"><summary className="cursor-pointer font-medium text-emerald-800">Asset details, previous lots &amp; verification</summary>
        <dl className="mt-3 grid gap-x-4 gap-y-2 sm:grid-cols-2"><div><dt className="text-xs text-slate-500">Asset</dt><dd>{lot.asset}</dd></div><div><dt className="text-xs text-slate-500">Category</dt><dd>{[lot.category,lot.subcategory].filter(Boolean).join(" / ")}</dd></div><div><dt className="text-xs text-slate-500">Catalogue</dt><dd>{lot.catalogue}</dd></div><div><dt className="text-xs text-slate-500">Station / train</dt><dd>{[lot.station,lot.train].filter(Boolean).join(" / ")||"—"}</dd></div><div><dt className="text-xs text-slate-500">Rate unit</dt><dd>{lot.rate_unit||"—"}</dd></div><div><dt className="text-xs text-slate-500">Calculation rule</dt><dd>{lot.rule||"Pending evidence"}</dd></div></dl>
        {lot.details&&<p className="mt-3">{lot.details}</p>}
        <h3 className="mt-4 font-semibold">Previous similar lots</h3>
        <p className="mt-1 text-xs text-slate-500">Check that previous lots refer to the same asset.</p>
        {lot.history.length?<div className="mt-2 overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr><th className="py-2 pr-3">Auction date</th><th className="pr-3">Lot</th><th className="pr-3">Status</th><th className="pr-3">Status date</th><th>Accepted rate / unit</th></tr></thead><tbody>{lot.history.map((row,i)=><tr key={i} className="border-t border-slate-100"><td className="py-2 pr-3">{dateText(row.date)}</td><td className="pr-3">{row.lot}</td><td className="pr-3">{row.status}</td><td className="pr-3">{dateText(row.status_date)}</td><td>{row.accepted_rate?`${valueText(row.accepted_rate)} ${row.rate_unit||""}`:"—"}</td></tr>)}</tbody></table></div>:<p className="mt-2 text-xs">No earlier auction evidence collected for this lot.</p>}
        <h3 className="mt-4 font-semibold">Full verification checks</h3>
        <ul className="mt-2 space-y-1 text-xs">{[...issues,...checks.filter(check=>check.state==="pass")].map(check=><li key={check.code} className={check.state==="fail"?"text-red-700":check.state==="warn"?"text-amber-800":"text-emerald-800"}>{check.state==="fail"?"Error: ":check.state==="warn"?"Review: ":"Passed: "}{check.message}</li>)}</ul>
        {lot.auctionSchedule?<p className="mt-3 text-xs">Auction {lot.auctionSchedule.status} · {dateText(lot.auctionSchedule.date)} · {lot.auctionSchedule.scheduleId} · {lot.auctionSchedule.catalogueId}</p>:<p className="mt-3 text-xs">No schedule row linked yet.</p>}
        <Link href={`/eauction?category=${encodeURIComponent(lot.category)}&lotKey=${encodeURIComponent(lot.key)}`} className="mt-2 inline-block text-xs text-emerald-700 underline">Open auction schedule</Link>
      </details>
    </td>
  </tr>;
}
