"use client";

import {useState, type FormEvent} from "react";
import {deskflowError, deskflowResponse} from "../lib/deskflow-errors";

type Fields=Record<string,unknown>;
type Auction={date:string;catalogue?:string;lot?:string;previous_lot?:string;outcome:string;bid_rate?:string|number;bid_source?:string;awardee?:string;awardee_source?:string};
type BidPatch={identity:string;bid_rate:string;bid_source:string;awardee:string;awardee_source:string};
export type ReviewLot={key:string;rate_unit:string;review?:{revision:string;inputs:Fields;contract:Fields;auctions:Auction[]};proposal?:{revision:string;status:string;value?:string|null;formula?:string;base?:string;factor?:string;justification?:string}};
const families=["Parking / Pay & Use","Parcel","Publicity","Catering / MPS","Food truck","Shop (case by case)"];
const contractStates=["Unknown","No previous contract","Running","Completed","Foreclosed","Not commenced","Not signed","Cancelled (reason unknown)"];
const units=["Annual Licensing Fee","Per Trip Licensing Fee","Per Round Trip Licensing Fee","Full Contract value"];
const text=(value:unknown)=>value==null?"":String(value);
const inputClass="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-2 text-sm";

function Field({label,value,onChange,type="text"}:{label:string;value:unknown;onChange:(value:string)=>void;type?:string}){
  return <label className="block text-xs text-slate-700">{label}<input type={type} min={type==="number"?0:undefined} step={type==="number"?"any":undefined} maxLength={type==="text"?2000:undefined} value={text(value)} onChange={e=>onChange(e.target.value)} className={inputClass}/></label>;
}

export function DeskflowReview({lot,token,disabled,onChanged}:{lot:ReviewLot;token:string;disabled:boolean;onChanged:()=>void}){
  const [open,setOpen]=useState(false);
  const [revision,setRevision]=useState("");
  const [inputs,setInputs]=useState<Fields>({});
  const [contract,setContract]=useState<Fields>({});
  const [bids,setBids]=useState<BidPatch[]>([]);
  const [previous,setPrevious]=useState("");
  const [scopeSource,setScopeSource]=useState("");
  const [confirmed,setConfirmed]=useState(false);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  if(!lot.review||!lot.proposal)return null;
  const stale=open&&revision!==lot.review.revision;
  function reload(){
    const review=lot.review!;setRevision(review.revision);setInputs({...review.inputs});setContract({...review.contract});
    setBids(review.auctions.filter(a=>a.outcome==="Sold"||a.outcome==="Rejected").map(a=>({identity:`${a.date}|${a.catalogue||""}|${a.previous_lot||a.lot||""}`,bid_rate:text(a.bid_rate),bid_source:a.bid_source||"",awardee:a.awardee||"",awardee_source:a.awardee_source||""})));
    setError("");setMessage("");
  }
  async function command(action:string,payload:Fields){
    setBusy(true);setError("");setMessage("");
    try{
      const response=await fetch(`/api/deskflow/${action}`,{method:"POST",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},body:JSON.stringify({key:lot.key,revision,...payload}),signal:AbortSignal.timeout(10000)});
      await deskflowResponse(response,"The review could not be queued.");setMessage("Review queued. The result will refresh when the desktop companion has checked it.");onChanged();
    }catch(e){setError(deskflowError(e,"The review could not be queued."));}finally{setBusy(false);}
  }
  function save(event:FormEvent){
    event.preventDefault();
    const allowedInputs=["family","benchmark_source","identity_verified","conditions_reviewed","new_asset","previous_rp","initial_rp","finance_fee","earlier_failures","reductions","important_amenity","use_market_bid"];
    const allowedContract=["status","source","awardee","lar","rate_unit","award_date","start","end","closed","termination_source","second_bidder_verified","second_bidder_rate"];
    const select=(values:Fields,allowed:string[])=>Object.fromEntries(Object.entries(values).filter(([key])=>allowed.includes(key)));
    void command("save-review",{inputs:select(inputs,allowedInputs),contract:select(contract,allowedContract),auctions:bids});
  }
  const blocked=disabled||busy||stale;
  return <section className="mt-3 border-t border-slate-200 pt-3">
    <button type="button" onClick={()=>{if(!open)reload();setOpen(!open);}} aria-expanded={open} className="text-sm font-medium text-emerald-800 underline">{open?"Close review":"Review evidence and proposal"}</button>
    {open&&<div className="mt-3 space-y-4">
      <p className="text-xs text-slate-600">Status: {lot.proposal.status.replaceAll("_"," ")}. Save evidence, check the calculation, then mark the exact proposal reviewed.</p>
      {stale&&<p role="alert" className="text-xs text-amber-800">The source evidence has changed. Your unsaved fields are retained. <button type="button" onClick={reload} className="underline">Reload current evidence</button> before saving.</p>}
      <form onSubmit={save} className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs">Asset family<select value={text(inputs.family)} onChange={e=>setInputs(v=>({...v,family:e.target.value}))} className={inputClass}><option value="">Select family</option>{families.map(name=><option key={name}>{name}</option>)}</select></label>
          <Field label="Policy / Finance / benchmark reference" value={inputs.benchmark_source} onChange={benchmark_source=>setInputs(v=>({...v,benchmark_source}))}/>
          {[["previous_rp","Previous approved RP"],["initial_rp","Original benchmark RP"],["finance_fee","Finance-vetted fee"],["earlier_failures","Earlier failures outside collected history"],["reductions","Reductions already applied"]].map(([key,label])=><Field key={key} label={label} type="number" value={inputs[key]} onChange={value=>setInputs(v=>({...v,[key]:value}))}/>)}
        </div>
        <div className="space-y-2 text-xs">{[["identity_verified","I verified the exact asset, area / compartment and scope."],["conditions_reviewed","I reviewed the applicable catalogue and standard conditions."],["new_asset","This is a new asset with no previous sold contract."],["important_amenity","The recorded important-amenity policy applies."],["use_market_bid","I approve case-by-case adoption of the sourced market bid."]].map(([key,label])=><label key={key} className="flex items-start gap-2"><input type="checkbox" checked={Boolean(inputs[key])} onChange={e=>setInputs(v=>({...v,[key]:e.target.checked}))}/>{label}</label>)}</div>
        <details className="rounded border border-slate-200 p-3"><summary className="cursor-pointer text-sm font-medium">Previous contract and LAR</summary><div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs">Contract status<select value={text(contract.status)||"Unknown"} onChange={e=>setContract(v=>({...v,status:e.target.value}))} className={inputClass}>{contractStates.map(name=><option key={name}>{name}</option>)}</select></label>
          <label className="text-xs">Contract rate unit<select value={text(contract.rate_unit)} onChange={e=>setContract(v=>({...v,rate_unit:e.target.value}))} className={inputClass}><option value="">Verify rate unit</option>{units.map(name=><option key={name}>{name}</option>)}</select></label>
          {[["source","Contract evidence reference"],["awardee","Awarded contractor"],["lar","Accepted rate / LAR"],["award_date","Award date"],["start","Contract start"],["end","Contract end"],["closed","Actual foreclosure date"],["termination_source","Cancellation / termination decision reference"],["second_bidder_rate","Second-highest distinct bidder rate"]].map(([key,label])=><Field key={key} label={label} value={contract[key]} type={key==="lar"||key==="second_bidder_rate"?"number":["award_date","start","end","closed"].includes(key)?"date":"text"} onChange={value=>setContract(v=>({...v,[key]:value}))}/>)}
          <label className="flex items-start gap-2 text-xs"><input type="checkbox" checked={Boolean(contract.second_bidder_verified)} onChange={e=>setContract(v=>({...v,second_bidder_verified:e.target.checked}))}/>I verified the distinct second bidder, or confirmed a single bidder.</label>
        </div></details>
        {!!bids.length&&<details className="rounded border border-slate-200 p-3"><summary className="cursor-pointer text-sm font-medium">Verify previous sold / rejected bid evidence ({bids.length})</summary><div className="mt-3 space-y-4">{bids.map((bid,index)=><fieldset key={bid.identity} className="border-t border-slate-100 pt-3"><legend className="text-xs font-medium">{bid.identity.replaceAll("|"," · ")}</legend><div className="mt-2 grid gap-3 sm:grid-cols-2">{[["bid_rate","Bid rate in the catalogue unit"],["bid_source","Bid-rate source"],["awardee","Verified awardee"],["awardee_source","Awardee / contract source"]].map(([key,label])=><Field key={key} label={label} type={key==="bid_rate"?"number":"text"} value={bid[key as keyof BidPatch]} onChange={value=>setBids(rows=>rows.map((row,n)=>n===index?{...row,[key]:value}:row))}/>)}</div></fieldset>)}</div></details>}
        <button disabled={blocked} className="rounded bg-emerald-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">Save evidence and calculate</button>
      </form>
      <details className="rounded border border-slate-200 p-3"><summary className="cursor-pointer text-sm font-medium">Link a changed previous lot code</summary><div className="mt-3 space-y-3"><Field label="Previous lot code already collected in the library" value={previous} onChange={setPrevious}/><Field label="Evidence confirming identical asset and scope" value={scopeSource} onChange={setScopeSource}/><label className="flex items-start gap-2 text-xs"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>I verified that these codes refer to the same asset and scope.</label><button type="button" disabled={blocked||!confirmed||!previous.trim()||!scopeSource.trim()} onClick={()=>void command("link-asset",{previous_lot:previous,source:scopeSource,confirmed})} className="rounded border border-slate-300 px-3 py-2 text-sm disabled:opacity-50">Save verified link</button></div></details>
      {lot.proposal.value!=null&&<div className="rounded bg-emerald-50 p-3 text-sm"><p className="font-semibold">Proposed RP: ₹{Number(lot.proposal.value).toLocaleString("en-IN",{maximumFractionDigits:2})}</p><p className="mt-1">{lot.proposal.justification}</p><p className="mt-1 text-xs">Base {lot.proposal.base}; factor {lot.proposal.factor}. Full working and policy reference remain in the audit history.</p><button type="button" disabled={blocked||lot.proposal.status!=="ready_for_review"} onClick={()=>void command("review-proposal",{proposal_revision:lot.proposal!.revision})} className="mt-3 rounded border border-emerald-700 px-3 py-2 text-sm disabled:opacity-50">Mark this proposal reviewed</button></div>}
      {message&&<p role="status" className="text-xs text-slate-600">{message}</p>}{error&&<p role="alert" className="text-xs text-red-700">{error}</p>}
    </div>}
  </section>;
}
