"use client";

import {useCallback, useEffect, useMemo, useState, type FormEvent} from "react";
import {ArrowLeft, LockKeyhole, RefreshCw} from "lucide-react";
import Link from "next/link";
import {DeskflowWorkbookHistory} from "./deskflow-workbook-history";

type History={date:string;status:string;status_date:string;lot:string;category:string;description:string;accepted_rate:string|number;rate_unit:string};
type Lot={key:string;asset:string;lot:string;category:string;subcategory:string;date:string;station:string;train:string;catalogue:string;details:string;rate_unit:string;value:string|number|null;justification:string;rule:string;history:History[]};
type Progress={busy:boolean;phase:string;message:string;error?:string};
type Overview={collected_at:string|null;categories:string[];lots:Lot[];progress:Progress;desktop_connected?:boolean};
type SoftwareUpdate={phase:string;message:string;revision?:string|null};
const LOCAL="/api/deskflow";
const TOKEN_KEY="sbcnav-deskflow-token";
const dateText=(value?:string)=>value?new Date(`${value.slice(0,10)}T00:00:00`).toLocaleDateString("en-IN",{day:"2-digit",month:"short",year:"numeric"}):"—";
const valueText=(value:number|string|null|undefined)=>value===null||value===undefined||value===""?"Pending evidence":`₹${Number(value).toLocaleString("en-IN",{maximumFractionDigits:2})}`;
const statusTone=(status:string)=>/running|completed|sold/i.test(status)?"bg-emerald-50 text-emerald-700":/withdrawn|rejected|failed|foreclosed|cancelled/i.test(status)?"bg-red-50 text-red-700":"bg-amber-50 text-amber-700";

export function Deskflow(){
  const [token,setToken]=useState("");
  const [password,setPassword]=useState("");
  const [overview,setOverview]=useState<Overview|null>(null);
  const [category,setCategory]=useState("");
  const [selectedKey,setSelectedKey]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [softwareUpdate,setSoftwareUpdate]=useState<SoftwareUpdate|null>(null);
  useEffect(()=>{setToken(sessionStorage.getItem(TOKEN_KEY)||"");},[]);
  const fetchOverview=useCallback(async(accessToken:string)=>{
    const response=await fetch(`${LOCAL}/overview`,{headers:{Authorization:`Bearer ${accessToken}`},cache:"no-store",signal:AbortSignal.timeout(8000)});
    if(response.status===401){sessionStorage.removeItem(TOKEN_KEY);setToken("");throw Error("Session expired. Unlock Deskflow again.");}
    if(!response.ok)throw Error("Deskflow service is unavailable. Try again shortly.");
    const data:Overview=await response.json();setOverview(data);setError("");
    setCategory(current=>current&&data.categories.includes(current)?current:data.categories[0]||"");
  },[]);
  const fetchSoftwareUpdate=useCallback(async(accessToken:string)=>{
    const response=await fetch(`${LOCAL}/software-update`,{headers:{Authorization:`Bearer ${accessToken}`},cache:"no-store",signal:AbortSignal.timeout(8000)});
    if(!response.ok)return;
    setSoftwareUpdate(await response.json());
  },[]);
  useEffect(()=>{if(!token)return;void fetchOverview(token).catch(e=>setError(e.message));void fetchSoftwareUpdate(token);const timer=setInterval(()=>{void fetchOverview(token).catch(e=>setError(e.message));void fetchSoftwareUpdate(token).catch(()=>{});},4000);return()=>clearInterval(timer);},[token,fetchOverview,fetchSoftwareUpdate]);
  async function unlock(event:FormEvent){event.preventDefault();setBusy(true);setError("");try{
    const response=await fetch(`${LOCAL}/unlock`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password}),signal:AbortSignal.timeout(8000)});
    const data=await response.json();if(!response.ok)throw Error(data.error||data.detail||"Unable to unlock Deskflow.");
    sessionStorage.setItem(TOKEN_KEY,data.token);setPassword("");setToken(data.token);
  }catch(e){setError(e instanceof Error?e.message:"Deskflow service is unavailable.");}finally{setBusy(false);}}
  async function collect(action:"collect"|"history") {setBusy(true);setError("");try{
    const response=await fetch(`${LOCAL}/${action}`,{method:"POST",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},body:"{}",signal:AbortSignal.timeout(10000)});
    const data=await response.json();if(!response.ok)throw Error(data.error||data.detail||"Collection could not start.");await fetchOverview(token);
  }catch(e){setError(e instanceof Error?e.message:"Collection could not start.");}finally{setBusy(false);}}
  async function updateDesktop(){setBusy(true);setError("");try{
    const response=await fetch(`${LOCAL}/software-update`,{method:"POST",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},body:"{}",signal:AbortSignal.timeout(10000)});
    const data=await response.json();if(!response.ok)throw Error(data.error||data.detail||"Desktop update could not start.");setSoftwareUpdate(data.queued?{phase:"starting",message:"Desktop update queued. Waiting for the Windows companion."}:data);
  }catch(e){setError(e instanceof Error?e.message:"Desktop update could not start.");}finally{setBusy(false);}}
  const lots=useMemo(()=>overview?.lots.filter(lot=>lot.category===category)||[],[overview,category]);
  const selected=lots.find(lot=>lot.key===selectedKey)||lots[0];
  return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 sm:px-8">
    <div className="mx-auto max-w-6xl">
      <header className="mb-7 flex items-center justify-between gap-4"><div><div className="flex items-center gap-3"><Link href="/" aria-label="Back to SBCNAV" title="Back to SBCNAV" className="rounded-xl border border-slate-200 bg-white p-2.5 hover:bg-slate-100"><ArrowLeft size={18}/></Link><h1 className="text-2xl font-bold tracking-tight">Deskflow</h1></div><p className="ml-12 mt-1 text-sm text-slate-500">Recent IREPS lots and proposed values</p></div>{token&&<button onClick={()=>{sessionStorage.removeItem(TOKEN_KEY);setToken("");setOverview(null);}} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">Lock</button>}</header>
      {!token?<form onSubmit={unlock} className="mx-auto mt-16 max-w-sm rounded-2xl border border-slate-200 bg-white p-7 shadow-sm"><div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700"><LockKeyhole size={24}/></div><h2 className="text-xl font-semibold">Unlock Deskflow</h2><p className="mt-1 text-sm text-slate-500">Enter the Deskflow password to view collected lots.</p><label htmlFor="deskflow-password" className="mt-6 block text-sm font-medium">Password</label><input id="deskflow-password" type="password" autoFocus required value={password} onChange={e=>setPassword(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-emerald-600"/><button disabled={busy} className="mt-4 w-full rounded-xl bg-emerald-700 px-4 py-3 font-semibold text-white disabled:opacity-60">Unlock</button>{error&&<p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}</form>:
      <div className="space-y-5"><section className="flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-5"><div><label htmlFor="deskflow-category" className="mb-2 block text-sm font-semibold text-slate-600">Category</label><select id="deskflow-category" value={category} onChange={e=>{setCategory(e.target.value);setSelectedKey("");}} className="min-w-60 rounded-xl border border-slate-300 bg-white px-4 py-2.5 font-medium"><option value="">Select category</option>{overview?.categories.map(item=><option key={item} value={item}>{item}</option>)}</select><p className="mt-2 text-xs text-slate-500">Collected {dateText(overview?.collected_at||"")}</p></div><div className="flex flex-wrap gap-2"><button disabled={busy||!overview?.desktop_connected||overview?.progress.busy||["starting","checking","downloading","installing"].includes(softwareUpdate?.phase||"")} onClick={updateDesktop} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold disabled:opacity-50">Update desktop app</button><button disabled={busy||!overview?.desktop_connected||overview?.progress.busy} onClick={()=>collect("collect")} className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><RefreshCw size={16}/> Collect lots</button><button disabled={busy||!overview?.desktop_connected||overview?.progress.busy||!overview?.lots.length} onClick={()=>collect("history")} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold disabled:opacity-50">Collect live history</button></div></section>
      {overview&&!overview.desktop_connected&&<p role="status" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">The Windows desktop companion is offline. Workbook history is available below; open the companion on Windows to collect live lots or update.</p>}
      <DeskflowWorkbookHistory token={token}/>
      {softwareUpdate&&softwareUpdate.phase!=="ready"&&<p role="status" className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">Desktop app: {softwareUpdate.message}</p>}
      {(overview?.progress.busy||overview?.progress.error||error)&&<p role="status" className={`rounded-xl border px-4 py-3 text-sm ${overview?.progress.error||error?"border-red-200 bg-red-50 text-red-700":"border-blue-200 bg-blue-50 text-blue-700"}`}>{error||overview?.progress.error||overview?.progress.message}</p>}
      {!overview?.lots.length?<div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">No recent lots collected yet. Open the desktop companion on Windows, then select Collect lots.</div>:<div className="grid gap-5 lg:grid-cols-[320px_minmax(0,1fr)]"><section className="overflow-hidden rounded-2xl border border-slate-200 bg-white"><div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Recent lots · {lots.length}</div><div className="max-h-[70vh] overflow-auto">{lots.map(lot=><button key={lot.key} onClick={()=>setSelectedKey(lot.key)} className={`block w-full border-b border-slate-100 px-4 py-4 text-left hover:bg-slate-50 ${selected?.key===lot.key?"bg-emerald-50":""}`}><span className="block text-sm font-semibold leading-5">{lot.asset||lot.lot}</span><span className="mt-1 block text-xs text-slate-500">Lot {lot.lot} · {lot.category}{lot.subcategory?` / ${lot.subcategory}`:""}</span></button>)}</div></section>{selected?<article className="space-y-5"><section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="text-base font-bold">Previous similar lots</h2><p className="mt-1 text-xs text-slate-500">Collected under the same IREPS lot number. Check comparability before using the proposed value.</p>{selected.history.length?<div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-slate-200 text-xs text-slate-500"><tr><th className="pb-2 pr-4">Auction date</th><th className="pb-2 pr-4">Lot</th><th className="pb-2 pr-4">Status</th><th className="pb-2 pr-4">Status date</th><th className="pb-2">Accepted rate</th></tr></thead><tbody>{selected.history.map((row,index)=><tr key={`${row.date}-${row.lot}-${index}`} className="border-b border-slate-100 last:border-0"><td className="py-3 pr-4 whitespace-nowrap">{dateText(row.date)}</td><td className="py-3 pr-4">{row.lot||"—"}</td><td className="py-3 pr-4"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusTone(row.status)}`}>{row.status}</span></td><td className="py-3 pr-4 whitespace-nowrap">{dateText(row.status_date)}</td><td className="py-3 whitespace-nowrap">{row.accepted_rate?`${valueText(row.accepted_rate)} ${row.rate_unit||""}`:"—"}</td></tr>)}</tbody></table></div>:<p className="mt-4 text-sm text-slate-500">No earlier auction evidence collected for this lot.</p>}</section>
      <section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="text-lg font-bold">{selected.asset}</h2><div className="mt-4 grid gap-4 text-sm sm:grid-cols-2"><Field label="Auction date" value={dateText(selected.date)}/><Field label="Category" value={[selected.category,selected.subcategory].filter(Boolean).join(" / ")}/><Field label="Lot" value={selected.lot}/><Field label="Catalogue" value={selected.catalogue}/><Field label="Station" value={selected.station}/><Field label="Train" value={selected.train}/></div>{selected.details&&<p className="mt-4 border-t border-slate-100 pt-4 text-sm text-slate-600">{selected.details}</p>}</section><section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6"><div className="text-sm font-semibold text-emerald-800">Proposed value</div><div className="mt-1 text-3xl font-bold tracking-tight text-emerald-950">{valueText(selected.value)}{selected.value!==null&&selected.rate_unit&&<span className="ml-2 text-base font-medium">{selected.rate_unit}</span>}</div><p className="mt-3 text-sm leading-6 text-emerald-900">{selected.justification||"Evidence is needed to calculate a value."}</p></section></article>:<div className="rounded-2xl bg-white p-8 text-slate-500">Select a lot.</div>}</div>}</div>}
    </div>
  </main>;
}
function Field({label,value}:{label:string;value?:string}){return <div><div className="text-xs font-medium text-slate-500">{label}</div><div className="mt-1 font-semibold">{value||"—"}</div></div>;}
