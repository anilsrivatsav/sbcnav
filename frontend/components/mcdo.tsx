"use client";
import {useEffect,useRef,useState} from "react";
import {Download,RefreshCw} from "lucide-react";
import {fetchJson} from "../lib/api";
import {Button,Panel} from "./ui";
import {McdoDeadlines,type Deadlines} from "./mcdo-deadlines";

type Run={run_id:string;state:string;mode?:string;updated_at?:string;summary:Record<string,number>;warnings:string[];error?:string;created_at?:string;result?:Record<string,unknown>;overdue?:unknown[][];connector?:unknown};
type Month={month:number;label:string;row_count:number;pub_earnings:string|null;nfr_earnings:string|null};
type Summary={configured:boolean;contracts:Record<string,number>;deadlines?:Deadlines;earnings:{selected_year:string;source:{filename:string;row_count:number}|null;latest_receipt_date:string|null;options:{years:string[]};monthly:Month[]}};
const money=(v:number|string|null|undefined)=>v==null?"—":Number(v).toLocaleString("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2});
const states:Record<string,string>={awaiting_ireps:"Waiting for IREPS check",preview_ready:"Preview ready",applying:"Updating and verifying",needs_review:"Needs review",complete:"Verified and imported"};

export function Mcdo({onUpdated}:{onUpdated?:()=>void}) {
  const [summary,setSummary]=useState<Summary|null>(null),[year,setYear]=useState(""),[month,setMonth]=useState(0);
  const [token,setToken]=useState(""),[authenticated,setAuthenticated]=useState(false),[connected,setConnected]=useState(false),[run,setRun]=useState<Run|null>(null),[history,setHistory]=useState<Run[]>([]);
  const [busy,setBusy]=useState(false),[scanning,setScanning]=useState(false),[waiting,setWaiting]=useState(false),[irepsReady,setIrepsReady]=useState(false),[refreshed,setRefreshed]=useState(false);
  const [message,setMessage]=useState(""),[error,setError]=useState(""),[revision,setRevision]=useState(0);
  const nonce=useRef(""),runId=useRef(""),waitingRef=useRef(false),launching=useRef(false),keyRef=useRef("");
  waitingRef.current=waiting;keyRef.current=token;
  async function api(path:string,body?:unknown) {
    const response=await fetch(`${window.location.origin}/api/mcdo${path}`,{cache:"no-store",method:body===undefined?"GET":"POST",headers:{"Content-Type":"application/json",...(path==="/session"&&body!==undefined?{Authorization:`Bearer ${keyRef.current}`}:{})},...(body===undefined?{}:{body:JSON.stringify(body)})});
    const json=await response.json();
    if(response.status===401){setAuthenticated(false);setBusy(false);setScanning(false);setWaiting(false);waitingRef.current=false;}
    if(!response.ok||json.success===false)throw new Error(typeof json.detail==="string"?json.detail:json.message||`Update request failed (${response.status}).`);
    return json.data;
  }
  async function restoreRun(){
    const previous:Run[]=await api("/runs");
    const latest=previous[0];
    if(latest){setRun(latest);runId.current=latest.run_id;setBusy(latest.state==="applying");setRefreshed(false);if(latest.state==="complete")setRevision(v=>v+1);}
  }
  function bridge(action:string,config?:unknown){window.postMessage({channel:"sbcnav-mcdo-request",nonce:nonce.current,action,config},window.location.origin);}
  async function startCheck(){
    try{setMessage("Reading Sheets and checking IREPS...");const next=await api("/runs",{});setRun(next);runId.current=next.run_id;setScanning(true);nonce.current=crypto.randomUUID();bridge("collect",next.connector);}
    catch(e){setError(e instanceof Error?e.message:"Unable to start update.");setBusy(false);}
    finally{launching.current=false;}
  }
  async function signIn(){setError("");try{await api("/session",{});setAuthenticated(true);setToken("");await restoreRun();setMessage("Updater signed in. Click Update now.");}catch(e){setError(e instanceof Error?e.message:"Sign-in failed.");}}
  useEffect(()=>{
    nonce.current=crypto.randomUUID();
    const listener=async(event:MessageEvent)=>{
      if(event.source!==window||event.origin!==window.location.origin||event.data?.channel!=="sbcnav-mcdo-response"||event.data.nonce!==nonce.current)return;
      const response=event.data;
      if(response.ready)setConnected(true);
      if(response.opened)setMessage("Complete token sign-in on IREPS. This update continues automatically.");
      if(response.authenticated&&waitingRef.current&&!launching.current){launching.current=true;waitingRef.current=false;setWaiting(false);setIrepsReady(true);void startCheck();}
      if(response.progress)setMessage(response.progress);
      if(response.error){setScanning(false);if(/session expired|sign in|signed in/i.test(response.error)){setWaiting(true);setMessage("IREPS needs authentication. Sign in there; the update continues automatically.");bridge("open");}else{setError(response.error);setBusy(false);setWaiting(false);}}
      if(response.evidence){
        setScanning(false);setMessage("Validating IREPS evidence...");
        try{const validated=await api(`/runs/${runId.current}/evidence`,response.evidence);setRun(validated);const next=await api(`/runs/${runId.current}/apply`,{});setRun({...validated,...next});setMessage("IREPS verified. Updating Sheets and Oracle automatically...");}
        catch(e){setError(e instanceof Error?e.message:"Evidence validation failed.");setBusy(false);}
      }
    };
    window.addEventListener("message",listener);bridge("ping");void api("/session").then(async()=>{setAuthenticated(true);try{await restoreRun();}catch(e){setError(e instanceof Error?e.message:"Unable to restore update history.");}}).catch(()=>setAuthenticated(false));
    const heartbeat=setInterval(()=>bridge("ping"),15000);
    return()=>{window.removeEventListener("message",listener);clearInterval(heartbeat);};
    // Callbacks read current run and access values from refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);
  useEffect(()=>{if(!waiting)return;bridge("session");const timer=setInterval(()=>bridge("session"),3000);return()=>clearInterval(timer);},[waiting]);
  useEffect(()=>{if(!scanning)return;const timeout=setTimeout(()=>{setScanning(false);setBusy(false);setError("IREPS check timed out. Start a fresh update; no sheet writes have been confirmed.");},25*60*1000);return()=>clearTimeout(timeout);},[scanning]);
  useEffect(()=>{
    const controller=new AbortController();fetchJson(`${window.location.origin}/api/mcdo${year?`?year=${encodeURIComponent(year)}`:""}`,{signal:controller.signal}).then(data=>{setSummary(data);if(run?.state==="complete")setRefreshed(true);}).catch(e=>{if(!controller.signal.aborted)setError(e.message);});return()=>controller.abort();
    // The completed run is refreshed by revision.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[year,revision]);
  useEffect(()=>{
    if(run?.state!=="applying"||!authenticated)return;let polling=false;
    const timer=setInterval(async()=>{if(polling)return;polling=true;try{const next=await api(`/runs/${run.run_id}`);setRun(next);if(next.state!=="applying"){setBusy(false);if(next.state==="complete"){setMessage("Update complete. Both sheets and Oracle verified.");setRevision(v=>v+1);onUpdated?.();}if(next.error)setError(next.error);}}catch(e){setError(e instanceof Error?e.message:"Unable to read update status.");}finally{polling=false;}},3000);return()=>clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[run?.run_id,run?.state,authenticated]);
  async function operation(mode:"check"|"apply"|"sync"|"history"|"recover"){
    setBusy(true);setError("");setMessage("");setRefreshed(false);
    try{
      if(mode==="history"){setHistory(await api("/runs"));setBusy(false);return;}
      if(mode==="recover"&&run){setRun(await api(`/runs/${run.run_id}/recover`,{}));setBusy(false);return;}
      if(mode==="check"){if(!connected)throw new Error("Install the browser connector once and reload SBC NAV.");setRun(null);setIrepsReady(false);setWaiting(true);setMessage("Checking IREPS sign-in. Authenticate there if requested; this update continues automatically.");bridge("open");}
      else if(mode==="apply"&&run){setRun({...run,...await api(`/runs/${run.run_id}/apply`,{})});setMessage("Resuming the verified update...");}
      else if(mode==="sync"){setRun(await api("/sync-sheets",{}));setMessage("Importing both existing sheets into Oracle...");}
    }catch(e){setError(e instanceof Error?e.message:"Update failed.");setBusy(false);setScanning(false);setWaiting(false);}
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
      <details className="text-sm text-muted"><summary className="cursor-pointer font-bold">Report options</summary>      <div className="flex flex-wrap gap-3">
        <label className="grid gap-1 text-xs font-bold text-muted">Financial year<select className="soft-inset rounded-lg border border-line p-2 text-ink" value={year||summary?.earnings.selected_year||""} onChange={e=>{setYear(e.target.value);setMonth(0);}}>{summary?.earnings.options.years.map(y=><option key={y}>{y}</option>)}</select></label>
        <label className="grid gap-1 text-xs font-bold text-muted">Report month<select className="soft-inset rounded-lg border border-line p-2 text-ink" value={selected?.month||0} onChange={e=>setMonth(Number(e.target.value))}>{months.map(m=><option value={m.month} key={m.month}>{m.label}</option>)}</select></label>
        <p className="self-end text-xs text-muted">Latest receipt: {summary?.earnings.latest_receipt_date||"No imported ledger"} · Main Sheet only</p>
      </div>
</details>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[["Month · PUB",money(selected?.pub_earnings)],["Month · NFR",money(selected?.nfr_earnings)],["Year to month · PUB",upto.some(m=>m.pub_earnings!==null)?money(upto.reduce((n,m)=>n+Number(m.pub_earnings||0),0)):"—"],["Running contracts",summary?.contracts.running??"—"]].map(([label,value])=><div key={label} className="soft-inset rounded-lg border border-line p-4"><p className="text-xs font-bold text-muted">{label}</p><p className="mt-2 text-xl font-black text-ink">{value}</p></div>)}
      </div>
      <p className="mt-3 text-xs text-muted">PUB and NFR overlap; they are reported separately. Rows without a month remain in annual earnings totals.</p>
    </Panel>
    <Panel title="Update from IREPS" subtitle="One update: IREPS, Google Sheets and Oracle.">
      <p className="mb-4 text-sm text-muted">One click checks IREPS, updates both Sheets and imports verified data into Oracle. Authenticate with your digital token only if IREPS requests it.</p>
      <Button onClick={()=>operation(run&&["preview_ready","needs_review"].includes(run.state)?"apply":"check")} disabled={busy||!authenticated||(!connected&&!(run&&["preview_ready","needs_review"].includes(run.state)))||!summary?.configured}><RefreshCw size={15}/>{busy?"Updating...":run&&["preview_ready","needs_review"].includes(run.state)?"Resume update":"Update now"}</Button>
      {!summary?.configured&&<p role="alert" className="mt-3 text-sm text-amber-700">Oracle updater setup is not ready. IREPS sign-in alone cannot update Sheets.</p>}
      {summary?.configured&&!authenticated&&<details open className="mt-4 rounded-lg border border-line p-3"><summary className="cursor-pointer text-sm font-bold">Sign in to updater once</summary><label className="mt-3 grid max-w-md gap-1 text-xs font-bold text-muted">Operator access key<input type="password" autoComplete="off" value={token} onChange={e=>setToken(e.target.value)} className="soft-inset rounded-lg border border-line p-3 text-sm text-ink"/></label><Button onClick={signIn} disabled={!token||busy} className="mt-3">Sign in</Button><p className="mt-2 text-xs text-muted">Session lasts eight hours. The key is not saved in browser storage.</p></details>}
      <details className="mt-4 rounded-lg border border-line p-3"><summary className="cursor-pointer text-sm font-bold">Connection setup and recovery</summary><p className="mt-3 text-sm text-muted">{connected?"Browser connector connected.":"Install the connector once in Chrome or Edge and reload SBC NAV."} <a className="font-bold text-blue underline" href="/mcdo-connector.zip" download>Download connector</a> · <a className="font-bold text-blue underline" href="/mcdo-connector-setup.txt" target="_blank" rel="noreferrer">Instructions</a></p><div className="mt-3 flex flex-wrap gap-2"><Button variant="secondary" onClick={()=>operation("sync")} disabled={busy||!authenticated||!summary?.configured}>Import existing sheets only</Button><Button variant="secondary" onClick={()=>operation("history")} disabled={busy||!authenticated}>Update history</Button>{run?.state==="applying"&&run.updated_at&&Date.now()-new Date(run.updated_at).getTime()>300000?<Button variant="secondary" onClick={()=>operation("recover")} disabled={!authenticated||scanning}>Recover interrupted update</Button>:null}</div></details>
      {(busy||run||irepsReady)&&<ol aria-label="Update progress" aria-live="polite" className="mt-4 space-y-2 text-sm">{[
        ["IREPS authenticated",irepsReady],
        ["IREPS records verified",Boolean(run&&run.mode!=="sheets_to_oracle"&&run.state!=="awaiting_ireps")],
        ["Earnings sheet updated and verified",Boolean(run?.result?.earnings_verified)],
        ["Master sheet updated and verified",Boolean(run?.result?.master_verified)],
        ["Oracle Master and earnings imported and verified",run?.state==="complete"],
        ["Web app refreshed",refreshed]
      ].map(([label,done],i)=><li key={String(label)} className={done?"text-green-700":"text-muted"}>{i+1}. {String(label)} - {run?.mode==="sheets_to_oracle"&&i<4?"Skipped (existing sheets import)":done?"Updated":"Pending"}</li>)}</ol>}
      {message&&<p role="status" className="mt-4 text-sm font-bold text-ink">{message}</p>}
      {error&&<p role="alert" className="mt-4 rounded-lg border border-red-300 bg-red-500/10 p-3 text-sm text-red-700">{error}</p>}
      {run&&<div className="mt-4 rounded-lg border border-line p-4"><p className="font-black text-ink">{states[run.state]||run.state}</p><div className="mt-2 flex flex-wrap gap-4 text-sm text-muted"><span>{run.summary?.new_invoices??0} new invoices</span><span>{run.summary?.new_contracts??0} new contracts</span><span>{money(run.summary?.earnings_amount)} earnings</span><span>{run.summary?.failed_payments??0} source payment failures</span></div>{run.warnings?.map((w,i)=><p key={i} className="mt-2 text-xs text-amber-700">{w}</p>)}{run.error&&<p className="mt-2 text-sm text-red-700">{run.error}</p>}{Boolean(run.overdue?.length)&&<div className="mt-3 overflow-auto"><table className="w-full text-left text-xs"><caption className="mb-2 text-left font-bold">IREPS-listed dues beyond seven-day grace</caption><thead><tr>{["Contract","Contractor","Amount due","Due date","Grace ends","Days past grace"].map(h=><th key={h} className="p-2">{h}</th>)}</tr></thead><tbody>{run.overdue?.map((r,i)=><tr key={i}>{r.map((c,j)=><td key={j} className="border-t border-line p-2">{String(c)}</td>)}</tr>)}</tbody></table></div>}</div>}
      {history.length>0&&<div className="mt-4 space-y-2">{history.map(h=><button key={h.run_id} className="flex w-full justify-between rounded-lg border border-line p-3 text-left text-xs text-ink" disabled={busy} onClick={()=>{setRun(h);runId.current=h.run_id;setRefreshed(false);setError("");if(h.state==="complete")setRevision(v=>v+1);}}><span>{h.created_at?new Date(h.created_at).toLocaleString("en-IN"):h.run_id}</span><span>{states[h.state]||h.state}</span></button>)}</div>}
    </Panel>
    <McdoDeadlines data={summary?.deadlines}/>
    <a className="text-sm font-bold text-blue underline" href="/publicity-earnings">View historical earnings details</a>
  </div>;
}
