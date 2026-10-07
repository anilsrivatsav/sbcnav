"use client";
import {useState} from "react";
import {Panel} from "./ui";

type Due={contract:string;contractor:string|null;category:string|null;due_date:string;grace_ends:string;days_after_due:number;amount_due:string|null};
type Expiry={contract:string;contractor:string|null;category:string|null;expiry_date:string;days_remaining:number};
export type Deadlines={as_of:string;grace_days:number;in_grace:Due[];past_grace:Due[];expiring:Expiry[];expiry_counts:Record<string,number>};
const dateLabel=(value:string)=>value.split("-").reverse().join("/");
const money=(value:string|null)=>value===null?"—":Number(value).toLocaleString("en-IN",{style:"currency",currency:"INR"});

export function McdoDeadlines({data}:{data?:Deadlines}) {
  const [windowDays,setWindowDays]=useState(7);
  if(!data)return <Panel title="Payment grace and contract expiry"><p className="text-sm text-muted">Loading deadline lists from Oracle…</p></Panel>;
  const expiring=data.expiring.filter(row=>row.days_remaining<=windowDays);
  function payments(rows:Due[],empty:string){return rows.length?<div className="max-h-80 overflow-auto"><table className="w-full text-left text-sm"><thead><tr>{["Contract / contractor","Category","Due date","Grace ends","Days after due","Scheduled balance"].map(label=><th key={label} className="whitespace-nowrap p-2">{label}</th>)}</tr></thead><tbody>{rows.map(row=><tr key={row.contract}><td className="border-t border-line p-2 font-bold">{row.contract}<span className="block text-xs font-normal text-muted">{row.contractor||"—"}</span></td><td className="border-t border-line p-2">{row.category||"—"}</td><td className="whitespace-nowrap border-t border-line p-2">{dateLabel(row.due_date)}</td><td className="whitespace-nowrap border-t border-line p-2">{dateLabel(row.grace_ends)}</td><td className="border-t border-line p-2">{row.days_after_due}</td><td className="whitespace-nowrap border-t border-line p-2">{money(row.amount_due)}</td></tr>)}</tbody></table></div>:<p className="py-3 text-sm text-muted">{empty}</p>;}
  return <Panel title="Payment grace and contract expiry" subtitle={`Master register in Oracle · As of ${dateLabel(data.as_of)} (IST)`}>
    <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[["Within 2-day grace",data.in_grace.length],...([3,5,7] as const).map(days=>[`Expiry within ${days} days`,data.expiry_counts[String(days)]])].map(([label,count])=><div key={label} className="soft-inset rounded-lg border border-line p-3"><p className="text-xs font-bold text-muted">{label}</p><p className="mt-1 text-xl font-black text-ink">{count}</p></div>)}</div>
    <h3 className="font-bold text-ink">Payments within 2-day grace</h3>
    <p className="mt-1 text-xs text-muted">Due today or within two calendar days after the current Master due date. Scheduled balances use Master fees and recorded payments; these dates alone do not prove a payment failure.</p>
    {payments(data.in_grace,"No listed payments are within the 2-day grace period today.")}
    <details className="mt-3 rounded-lg border border-line p-3"><summary className="cursor-pointer text-sm font-bold text-ink">Past the 2-day grace period · {data.past_grace.length}</summary>{payments(data.past_grace,"No listed payments are past the 2-day grace period.")}</details>
    <div className="mt-5 flex flex-wrap items-center justify-between gap-3"><h3 className="font-bold text-ink">Contracts expiring soon</h3><label className="flex items-center gap-2 text-sm text-muted">Expiry window<select aria-label="Contract expiry window" value={windowDays} onChange={event=>setWindowDays(Number(event.target.value))} className="soft-inset rounded-lg border border-line p-2 text-ink">{[3,5,7].map(days=><option key={days} value={days}>Within {days} days</option>)}</select></label></div>
    <p className="mt-1 text-xs text-muted">Includes expiry today. The 5- and 7-day lists include the shorter windows. Completed, cancelled and terminated contracts are excluded.</p>
    {expiring.length?<div className="mt-2 max-h-80 overflow-auto"><table className="w-full text-left text-sm"><thead><tr>{["Contract / contractor","Category","Expiry date","Days remaining"].map(label=><th key={label} className="p-2">{label}</th>)}</tr></thead><tbody>{expiring.map(row=><tr key={row.contract}><td className="border-t border-line p-2 font-bold">{row.contract}<span className="block text-xs font-normal text-muted">{row.contractor||"—"}</span></td><td className="border-t border-line p-2">{row.category||"—"}</td><td className="whitespace-nowrap border-t border-line p-2">{dateLabel(row.expiry_date)}</td><td className="border-t border-line p-2">{row.days_remaining===0?"Today":row.days_remaining}</td></tr>)}</tbody></table></div>:<p className="py-3 text-sm text-muted">No active Master contracts expire within {windowDays} days.</p>}
  </Panel>;
}
