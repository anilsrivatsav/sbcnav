"use client";
import {useCallback,useEffect,useRef,useState} from "react";
import {RefreshCw,Pause,Play,CheckCircle2} from "lucide-react";
import {fetchJson} from "../lib/api";
import {Button,Panel} from "./ui";
import {McdoDeadlines,type Deadlines} from "./mcdo-deadlines";

type Run={run_id:string;state:string;mode?:string;summary?:Record<string,number>;result?:Record<string,unknown>;warnings?:string[];overdue?:unknown[][];error?:string};
type Status={configured:boolean;busy:boolean;phase:string;message:string;error?:string;start?:string;end?:string;run?:Run;logs:string[]};
type Summary={deadlines?:Deadlines;earnings:{latest_receipt_date:string|null;source:{row_count:number}|null}};
const LOCAL="http://127.0.0.1:48722";
const money=(v:number|undefined)=>v===undefined?"—":v.toLocaleString("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2});
const date=(v:string|null|undefined)=>v?new Date(v).toLocaleDateString("en-IN",{timeZone:"Asia/Kolkata"}):"Not yet checked";

export function Mcdo({onUpdated}:{onUpdated?:()=>void}) {
  const [status,setStatus]=useState<Status|null>(null),[summary,setSummary]=useState<Summary|null>(null);
  const [reachable,setReachable]=useState(false),[checking,setChecking]=useState(true),[sending,setSending]=useState(false);
  const [error,setError]=useState(""),[reportError,setReportError]=useState("");
  const completed=useRef("");
  const onUpdatedRef=useRef(onUpdated);onUpdatedRef.current=onUpdated;
  const refreshReport=useCallback(async()=>{
    try{setSummary(await fetchJson(`${window.location.origin}/api/mcdo`));setReportError("");}
    catch{setReportError("The report could not refresh. Your saved update is retained; try Refresh report.");}
  },[]);
  const check=useCallback(async()=>{
    try{
      const response=await fetch(`${LOCAL}/status`,{cache:"no-store",signal:AbortSignal.timeout(5000)});
      if(!response.ok)throw new Error("Connection unavailable");
      const next:Status=await response.json();setStatus(next);setReachable(true);
      if(next.phase==="complete"&&next.run?.run_id!==completed.current){
        completed.current=next.run?.run_id||"";void refreshReport();onUpdatedRef.current?.();
      }
    }catch{setReachable(false);}finally{setChecking(false);}
  },[refreshReport]);
  useEffect(()=>{
    let mounted=true,polling=false;
    const poll=async()=>{if(!mounted||polling)return;polling=true;try{await check();}finally{polling=false;}};
    void poll();void refreshReport();const timer=setInterval(poll,3000);
    return()=>{mounted=false;clearInterval(timer);};
  },[check,refreshReport]);
  async function command(action:"start"|"resume"|"pause"|"sync"){
    setSending(true);setError("");
    try{
      const response=await fetch(`${LOCAL}/${action}`,{method:"POST",headers:{"Content-Type":"application/json"},body:"{}",signal:AbortSignal.timeout(15000)});
      const result=await response.json();if(!response.ok)throw new Error(result.error||"Unable to start this operation.");
      setStatus(result);setReachable(true);
    }catch(e){setError(e instanceof Error?e.message:"Could not reach the desktop updater. Reconnect and check saved progress before trying again.");void check();}
    finally{setSending(false);}
  }
  const busy=Boolean(status?.busy),paused=status?.phase==="paused",run=status?.run;
  const resume=Boolean(run&&["error","interrupted","paused"].includes(status?.phase||""));
  const ready=reachable&&status?.configured&&!sending;
  const oracleOnly=run?.mode==="sheets_to_oracle";
  const steps=[
    {label:"Read IREPS payments and contract status",done:Boolean(run?.result?.earnings_verified)||["validating","applying","complete"].includes(status?.phase||""),active:["login","collecting","validating"].includes(status?.phase||""),skip:oracleOnly},
    {label:"Update and verify both Google Sheets",done:Boolean(run?.result?.earnings_verified&&run?.result?.master_verified),active:status?.phase==="applying"&&run?.result?.active_stage!==5,skip:oracleOnly},
    {label:"Import and verify Oracle",done:run?.state==="complete",active:status?.phase==="applying"&&run?.result?.active_stage===5,skip:false}
  ];
  return <div className="space-y-4">
    <Panel title="Update from IREPS" subtitle="The working desktop updater, controlled from this page.">
      <p className="text-sm text-muted">Connect your digital token and choose <strong>Check for new payments</strong>. Sign in to IREPS when Chrome opens. The updater reads the dates, updates both Sheets and verifies Oracle automatically.</p>
      <div className="my-4 rounded-lg border border-line p-4">
        <p className="font-bold text-ink">Latest receipt in Oracle: {date(summary?.earnings.latest_receipt_date)}</p>
        {status?.start&&status.end&&<p className="mt-1 text-sm text-muted">{busy?"Checking":"Last check"}: {status.start} to {status.end}. Existing invoices are skipped.</p>}
      </div>
      {!reachable&&<div className="mb-4 rounded-lg border border-amber-400 p-4 text-sm" role="status">
        <p className="font-bold">{checking?"Connecting to the desktop updater…":"Connect this computer"}</p>
        {!checking&&<><p className="mt-2">Open <strong>SBC NAV Updater</strong> on your desktop. If Chrome asks to connect to devices on your local network, allow access for SBC NAV, then choose Reconnect.</p><div className="mt-3 flex gap-3"><a className="font-bold text-blue underline" href="sbcnav-updater://open">Open desktop connection</a><button className="font-bold text-blue underline" onClick={()=>{setChecking(true);void check();}}>Reconnect</button></div><p className="mt-2 text-xs text-muted">No operator key or browser extension is required on this configured PC. The connection starts automatically when you sign in to Windows.</p></>}
      </div>}
      {reachable&&!status?.configured&&<p role="alert" className="mb-4 text-sm text-red-700">The desktop connection needs administrator setup on this computer.</p>}
      <div className="flex flex-wrap gap-3">
        {resume&&<Button onClick={()=>command("resume")} disabled={!ready||(busy&&!paused)}><Play size={16}/>Resume saved update</Button>}
        <Button onClick={()=>command("start")} disabled={!ready||busy}><RefreshCw size={16}/>{busy?status?.phase==="login"?"Waiting for IREPS sign-in…":"Update in progress…":"Check for new payments"}</Button>
        {busy&&!paused&&<Button variant="secondary" onClick={()=>command("pause")} disabled={!ready}><Pause size={16}/>Pause safely</Button>}
      </div>
      <p role="status" aria-live="polite" className="mt-4 text-sm font-bold text-ink">{reachable?status?.message:"The dashboard remains available while the desktop connection is offline."}</p>
      <p className="mt-2 text-xs text-muted">You can close this page during an update. Keep the computer and updater Chrome window open; reopen this page to see progress.</p>
      {(error||status?.error)&&<p role="alert" className="mt-4 rounded-lg border border-red-300 p-3 text-sm text-red-700">{error||status?.error}</p>}
      {run&&<>
        <ol aria-label="Update progress" className="mt-4 grid gap-2 md:grid-cols-3">{steps.map((s,i)=><li key={s.label} className="rounded-lg border border-line p-3 text-sm"><p className="font-bold">{i+1}. {s.label}</p><p className="mt-2 flex items-center gap-2 text-muted">{s.skip?"Existing Sheets import — skipped":s.done?<><CheckCircle2 size={16}/>Verified</>:s.active?"In progress":paused?"Paused":"Waiting"}</p></li>)}</ol>
        {run.summary&&<p className="mt-4 text-sm text-muted">{run.summary.new_invoices??0} new invoices · {run.summary.new_contracts??0} new contracts · {money(run.summary.earnings_amount)} licence earnings</p>}
        {run.warnings?.map((w,i)=><p key={i} className="mt-2 text-xs text-amber-700">{w}</p>)}
        {Boolean(run.overdue?.length)&&<div className="mt-4 overflow-auto"><table className="w-full text-left text-xs"><caption className="mb-2 text-left font-bold">Payments unpaid beyond the seven-day grace period</caption><thead><tr>{["Contract","Contractor","Amount due","Due date","Grace ends","Days past grace"].map(h=><th key={h} className="p-2">{h}</th>)}</tr></thead><tbody>{run.overdue?.map((r,i)=><tr key={i}>{r.map((v,j)=><td key={j} className="border-t border-line p-2">{String(v)}</td>)}</tr>)}</tbody></table></div>}
      </>}
      <details className="mt-4 rounded-lg border border-line p-3"><summary className="cursor-pointer text-sm font-bold">Activity and other options</summary><p className="mt-3 text-sm text-muted">If you have edited Sheets yourself, import those changes into Oracle without checking IREPS.</p><div className="mt-3 flex flex-wrap gap-3"><Button variant="secondary" disabled={!ready||busy} onClick={()=>command("sync")}>Import existing Sheets into Oracle</Button><Button variant="secondary" onClick={()=>refreshReport()}>Refresh report</Button></div><pre className="mt-4 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-muted">{status?.logs.join("\n")||"No activity in this connection yet."}</pre></details>
      {reportError&&<p role="alert" className="mt-3 text-sm text-red-700">{reportError}</p>}
    </Panel>
    <McdoDeadlines data={summary?.deadlines}/>
  </div>;
}
