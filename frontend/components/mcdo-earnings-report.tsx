"use client";
import {useEffect,useState} from "react";
import {Download} from "lucide-react";
import {fetchJson} from "../lib/api";
import {Button,Panel} from "./ui";
import type {Deadlines} from "./mcdo-deadlines";
type Month={month:number;label:string;row_count:number;pub_earnings:string|null;nfr_earnings:string|null};
type Summary={configured:boolean;contracts:Record<string,number>;deadlines?:Deadlines;earnings:{selected_year:string;source:{filename:string;row_count:number}|null;latest_receipt_date:string|null;options:{years:string[]};monthly:Month[]}};
const money=(v:number|string|null|undefined)=>v==null?"—":Number(v).toLocaleString("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2});
export function McdoEarningsReport(){
  const [summary,setSummary]=useState<Summary|null>(null),[year,setYear]=useState(""),[month,setMonth]=useState(0),[error,setError]=useState("");
  useEffect(()=>{
    const controller=new AbortController();setError("");
    fetchJson(`${window.location.origin}/api/mcdo${year?`?year=${encodeURIComponent(year)}`:""}`,{signal:controller.signal}).then(setSummary).catch(e=>{if(!controller.signal.aborted)setError(e.message);});
    return()=>controller.abort();
  },[year]);
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
    {error&&<p role="alert" className="text-sm text-red-700">{error}</p>}
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
  </div>;
}
