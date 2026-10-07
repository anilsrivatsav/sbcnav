"use client";
import {useEffect,useRef,useState} from "react";
import {CheckCircle2,Download,ExternalLink,RefreshCw,ShieldCheck} from "lucide-react";
import {API_URL,fetchJson} from "../lib/api";
import {Button,Panel} from "./ui";
import {PublicityEarnings} from "./publicity-earnings";

type Run={run_id:string;state:string;mode?:string;updated_at?:string;summary:Record<string,number>;warnings:string[];error?:string;created_at?:string;result?:Record<string,unknown>;overdue?:unknown[][];connector?:unknown};
type Month={month:number;label:string;row_count:number;pub_earnings:string|null;nfr_earnings:string|null};
type Summary={configured:boolean;contracts:Record<string,number>;earnings:{selected_year:string;source:{filename:string;row_count:number}|null;latest_receipt_date:string|null;options:{years:string[]};monthly:Month[]}};
const money=(v:number|string|null|undefined)=>v==null?"—":Number(v).toLocaleString("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2});
const states:Record<string,string>={awaiting_ireps:"Waiting for IREPS check",preview_ready:"Preview ready",applying:"Updating and verifying",needs_review:"Needs review",complete:"Verified and imported"};

export function Mcdo({onUpdated}:{onUpdated?:()=>void}) {
  const [summary,setSummary]=useState<Summary|null>(null),[year,setYear]=useState(""),[month,setMonth]=useState(0);
  const [token,setToken]=useState(""),[connected,setConnected]=useState(false),[run,setRun]=useState<Run|null>(null),[history,setHistory]=useState<Run[]>([]);
  const [busy,setBusy]=useState(false),[scanning,setScanning]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState("");
  const [revision,setRevision]=useState(0);
  const nonce=useRef(""),runId=useRef(""),keyRef=useRef("");
  keyRef.current=token;
  async function api(path:string,body?:unknown) {
    return fetchJson(`${API_URL}/api/mcdo${path}`,{method:body===undefined?"GET":"POST",headers:{Authorization:`Bearer ${keyRef.current}`,"Content-Type":"application/json"},...(body===undefined?{}:{body:JSON.stringify(body)})});
  }
  function bridge(action:string,config?:unknown) {
    window.postMessage({channel:"sbcnav-mcdo-request",nonce:nonce.current,action,config},window.location.origin);
  }
  useEffect(()=>{
    nonce.current=crypto.randomUUID();
    const listener=async(event:MessageEvent)=>{
      if(event.source!==window||event.origin!==window.location.origin||event.data?.channel!=="sbcnav-mcdo-response"||event.data.nonce!==nonce.current)return;
      const response=event.data;
      if(response.ready)setConnected(true);
      if(response.opened)setMessage("Sign in on the IREPS tab with your digital token, then return here and click Check IREPS.");
      if(response.progress)setMessage(response.progress);
      if(response.error){setError(response.error);setBusy(false);setScanning(false);}
      if(response.evidence) {
        setMessage("Validating invoice PDFs, agreements and the proposed sheet changes…");setScanning(false);
        try {
          const result=await api(`/runs/${runId.current}/evidence`,response.evidence);
          setRun(result);setMessage("Preview ready. Review the changes, then update both sheets and Oracle.");
          setHistory(await api("/runs"));
        }catch(e){setError(e instanceof Error?e.message:"Evidence validation failed.");}
        finally{setBusy(false);}
      }
    };
    window.addEventListener("message",listener);bridge("ping");
    return()=>window.removeEventListener("message",listener);
    // The API callback reads the current access key from its ref.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);
  useEffect(()=>{
    if(!scanning)return;
    const heartbeat=setInterval(()=>bridge("ping"),15000);
    const timeout=setTimeout(()=>{setScanning(false);setBusy(false);setError("The browser check timed out. No sheet changes were applied; start a fresh check.");},25*60*1000);
    return()=>{clearInterval(heartbeat);clearTimeout(timeout);};
  },[scanning]);
  useEffect(()=>{
    const controller=new AbortController();
    fetchJson(`${API_URL}/api/mcdo${year?`?year=${encodeURIComponent(year)}`:""}`,{signal:controller.signal})
      .then(data=>{setSummary(data);setError("");})
      .catch(e=>{if(!controller.signal.aborted)setError(e.message);});
    return()=>controller.abort();
  },[year,revision]);
  useEffect(()=>{
    if(run?.state!=="applying")return;
    const timer=setInterval(async()=>{
      try {
        const next=await api(`/runs/${run.run_id}`);setRun(next);
        if(next.state!=="applying") {
          setBusy(false);setHistory(await api("/runs"));
          if(next.state==="complete"){setMessage("Both sources verified and imported into Oracle.");setRevision(v=>v+1);onUpdated?.();}
          if(next.error)setError(next.error);
        }
      }catch(e){setError(e instanceof Error?e.message:"Unable to read sync status.");}
    },3000);
    return()=>clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[run?.run_id,run?.state]);
  async function operation(mode:"check"|"apply"|"sync"|"history"|"recover") {
    setBusy(true);setError("");setMessage("");
    try {
      if(mode==="history"){setHistory(await api("/runs"));setMessage("Saved update history loaded.");setBusy(false);return;}
      if(mode==="recover"&&run){setRun(await api(`/runs/${run.run_id}/recover`,{}));setBusy(false);setMessage("Interrupted run recovered. Review and resume it, or sync the current sheets again.");return;}
      if(mode==="check") {
        if(!connected)throw new Error("Install the SBC NAV browser connector, reload this page, and sign in to IREPS first.");
        setMessage("Reading current Google Sheets and preparing the IREPS check…");
        const next=await api("/runs",{});setRun(next);runId.current=next.run_id;setScanning(true);
        nonce.current=crypto.randomUUID();
        bridge("collect",next.connector);
      }else if(mode==="apply"&&run) {
        const next=await api(`/runs/${run.run_id}/apply`,{});setRun({...run,...next});setMessage("Updating Google Sheets, verifying the results, then importing both sources into Oracle…");
      }else if(mode==="sync") {
        setRun(await api("/sync-sheets",{}));setMessage("Importing the latest complete Google Sheets into Oracle…");
      }
    }catch(e){setError(e instanceof Error?e.message:"Update failed.");setBusy(false);setScanning(false);}
  }
  const months=summary?.earnings.monthly||[];
  const selected=months.find(m=>m.month===month)||[...months].reverse().find(m=>m.row_count>0);
  const upto=selected?months.slice(0,months.indexOf(selected)+1):[];
  function download() {
    if(!summary)return;
    const cells=(v:unknown)=>`"${String(v??"").replace(/^[=+@-]/,"'$&").replaceAll('"','""')}"`;
    const records=[["Financial year","Month","Receipts","PUB earnings INR","NFR earnings INR"],...months.map(m=>[summary.earnings.selected_year,m.label,m.row_count,m.pub_earnings,m.nfr_earnings])];
    const url=URL.createObjectURL(new Blob(["\uFEFF",records.map(r=>r.map(cells).join(",")).join("\r\n")],{type:"text/csv;charset=utf-8"}));
    const anchor=document.createElement("a");anchor.href=url;anchor.download=`SBC-MCDO-${summary.earnings.selected_year}.csv`;anchor.click();URL.revokeObjectURL(url);
  }
  return <div className="space-y-4">
    <Panel title="MCDO · Monthly commercial report" subtitle="Verified earnings and contract status from Oracle." action={<Button variant="secondary" size="sm" onClick={download} disabled={!summary}><Download size={14}/> Export report</Button>}>
      <div className="flex flex-wrap gap-3">
        <label className="grid gap-1 text-xs font-bold text-muted">Financial year<select className="soft-inset rounded-lg border border-line p-2 text-ink" value={year||summary?.earnings.selected_year||""} onChange={e=>{setYear(e.target.value);setMonth(0);}}>{summary?.earnings.options.years.map(y=><option key={y}>{y}</option>)}</select></label>
        <label className="grid gap-1 text-xs font-bold text-muted">Report month<select className="soft-inset rounded-lg border border-line p-2 text-ink" value={selected?.month||0} onChange={e=>setMonth(Number(e.target.value))}>{months.map(m=><option value={m.month} key={m.month}>{m.label}</option>)}</select></label>
        <p className="self-end text-xs text-muted">Latest receipt: {summary?.earnings.latest_receipt_date||"No imported ledger"} · Main Sheet only</p>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[["Month · PUB",money(selected?.pub_earnings)],["Month · NFR",money(selected?.nfr_earnings)],["Year to month · PUB",upto.some(m=>m.pub_earnings!==null)?money(upto.reduce((n,m)=>n+Number(m.pub_earnings||0),0)):"—"],["Running contracts",summary?.contracts.running??"—"]].map(([label,value])=><div key={label} className="soft-inset rounded-lg border border-line p-4"><p className="text-xs font-bold text-muted">{label}</p><p className="mt-2 text-xl font-black text-ink">{value}</p></div>)}
      </div>
      <p className="mt-3 text-xs text-muted">PUB and NFR overlap; they are reported separately. Rows without a month remain in annual earnings totals.</p>
    </Panel>
    <Panel title="Update from IREPS" subtitle="Sign in → check and preview → update Google Sheets → verify and sync Oracle.">
      <div className="mb-4 flex flex-wrap gap-3 text-xs font-bold text-muted"><span className="flex items-center gap-1"><ShieldCheck size={14}/> Digital-token sign-in stays in IREPS</span><span>{connected?"Browser connector connected":"Browser connector not connected"}</span><span>{summary?.configured?"Google Sheets connection configured":"Oracle connection setup required"}</span></div>
      <div className="mb-4 rounded-lg border border-line p-3 text-sm text-muted">Use the SBC NAV browser connector once in Chrome or Edge. The MCDO tab controls every update; no Windows updater is needed. <a className="font-bold text-blue underline" href="/mcdo-connector.zip" download>Download connector</a> · <a className="font-bold text-blue underline" href="/mcdo-connector-setup.txt" target="_blank" rel="noreferrer">Setup instructions</a></div>
      <label className="mb-4 grid max-w-md gap-1 text-xs font-bold text-muted">Operator access key<input type="password" autoComplete="off" value={token} onChange={e=>setToken(e.target.value)} placeholder="Enter your MCDO operator key" className="soft-inset rounded-lg border border-line p-3 text-sm text-ink"/></label>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={()=>{setError("");if(connected)bridge("open");else window.open("https://www.ireps.gov.in/epsn/home/showHome.do","_blank","noopener,noreferrer");}} disabled={busy}><ExternalLink size={15}/> Sign in to IREPS</Button>
        <Button onClick={()=>operation("check")} disabled={busy||!token||!connected||!summary?.configured}><RefreshCw size={15}/> Check IREPS</Button>
        <Button onClick={()=>operation("apply")} disabled={busy||!token||!run||run.mode==="sheets_to_oracle"||!["preview_ready","needs_review"].includes(run.state)}><CheckCircle2 size={15}/> {run?.state==="needs_review"?"Resume saved update":"Update sheets & Oracle"}</Button>
        <Button variant="secondary" onClick={()=>operation("sync")} disabled={busy||!token||!summary?.configured}>Sync existing sheets to Oracle</Button>
        <Button variant="secondary" onClick={()=>operation("history")} disabled={busy||!token}>Update history</Button>
        {run?.state==="applying"&&run.updated_at&&Date.now()-new Date(run.updated_at).getTime()>300000?<Button variant="secondary" onClick={()=>operation("recover")} disabled={!token||scanning}>Recover interrupted update</Button>:null}
      </div>
      {message&&<p role="status" className="mt-4 text-sm font-bold text-ink">{message}</p>}
      {error&&<p role="alert" className="mt-4 rounded-lg border border-red-300 bg-red-500/10 p-3 text-sm text-red-700">{error}</p>}
      {run&&<div className="mt-4 rounded-lg border border-line p-4"><p className="font-black text-ink">{states[run.state]||run.state}</p><div className="mt-2 flex flex-wrap gap-4 text-sm text-muted"><span>{run.summary?.new_invoices??0} new invoices</span><span>{run.summary?.new_contracts??0} new contracts</span><span>{money(run.summary?.earnings_amount)} earnings</span><span>{run.summary?.failed_payments??0} source payment failures</span></div>{run.warnings?.map((w,i)=><p key={i} className="mt-2 text-xs text-amber-700">{w}</p>)}{run.error&&<p className="mt-2 text-sm text-red-700">{run.error}</p>}{Boolean(run.overdue?.length)&&<div className="mt-3 overflow-auto"><table className="w-full text-left text-xs"><caption className="mb-2 text-left font-bold">IREPS-listed dues beyond seven-day grace</caption><thead><tr>{["Contract","Contractor","Amount due","Due date","Grace ends","Days past grace"].map(h=><th key={h} className="p-2">{h}</th>)}</tr></thead><tbody>{run.overdue?.map((r,i)=><tr key={i}>{r.map((c,j)=><td key={j} className="border-t border-line p-2">{String(c)}</td>)}</tr>)}</tbody></table></div>}</div>}
      {history.length>0&&<div className="mt-4 space-y-2">{history.map(h=><button key={h.run_id} className="flex w-full justify-between rounded-lg border border-line p-3 text-left text-xs text-ink" disabled={busy} onClick={()=>{setRun(h);setError("");}}><span>{h.created_at?new Date(h.created_at).toLocaleString("en-IN"):h.run_id}</span><span>{states[h.state]||h.state}</span></button>)}</div>}
    </Panel>
    <PublicityEarnings key={revision} operatorKey={token}/>
  </div>;
}
