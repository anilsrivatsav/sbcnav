"use client";

import {useEffect, useState, type FormEvent} from "react";
import {deskflowError, deskflowResponse} from "../lib/deskflow-errors";

type Book={id:string;portfolio:string;file:string;rows:number;cells:number};
type RecordItem={id:string;dateLabel:string;asset:string;portfolio:string;assetType:string;rp:number|null;previousValue:number|null;justification:string;outcomeText:string;sheet:string;row:number;file?:string};
type SourceRow={bookId:string;file:string;sheet:string;row:{n:number;v:(string|number|boolean|null)[];f:Record<string,string>}};
type Result={available:boolean;books:Book[];items:(RecordItem|SourceRow)[];total:number;page:number;limit:number;sourceManifest?:Record<string,{sha256:string}>};

export function DeskflowWorkbookHistory({token,revision,assetSearch}:{token:string;revision?:string;assetSearch?:string}){
  const [book,setBook]=useState("");
  const [query,setQuery]=useState("");
  const [search,setSearch]=useState("");
  const [view,setView]=useState<"records"|"rows">("records");
  const [page,setPage]=useState(1);
  const [data,setData]=useState<Result|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  const [retry,setRetry]=useState(0);
  useEffect(()=>{if(assetSearch!==undefined){setQuery(assetSearch);setSearch(assetSearch);setPage(1);setBook("");setView("records");}},[assetSearch]);
  useEffect(()=>{
    const controller=new AbortController();
    const params=new URLSearchParams({book,q:search,view,page:String(page),limit:"30"});
    setLoading(true);setError("");
    fetch(`/api/deskflow/workbook-history?${params}`,{headers:{Authorization:`Bearer ${token}`},cache:"no-store",signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)])})
      .then(response=>deskflowResponse<Result>(response,"Workbook history could not be loaded."))
      .then(setData).catch(reason=>{if(!controller.signal.aborted)setError(deskflowError(reason,"Workbook history could not be loaded."));})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return()=>controller.abort();
  },[token,book,search,view,page,revision,retry]);
  function submit(event:FormEvent){event.preventDefault();setPage(1);setSearch(query.trim());}
  const pages=Math.max(1,Math.ceil((data?.total||0)/30));
  return <section id="workbook-history" className="rounded-2xl border border-slate-200 bg-white p-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-bold">{assetSearch?"Previous similar assets":"Workbook history"}</h2><p className="mt-1 text-sm text-slate-600">{assetSearch?"Matching saved workbook records. Confirm the asset and scope before comparing rates.":"Saved auction records and original workbook rows."}</p></div>{data?.available&&<span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">Encrypted archive</span>}</div>
    <div className="mt-5 flex flex-wrap gap-2"><button onClick={()=>{setData(null);setView("records");setPage(1);}} className={`rounded-lg px-3 py-2 text-sm font-semibold ${view==="records"?"bg-emerald-700 text-white":"border border-slate-300"}`}>Auction records</button><button onClick={()=>{setData(null);setView("rows");setPage(1);}} className={`rounded-lg px-3 py-2 text-sm font-semibold ${view==="rows"?"bg-emerald-700 text-white":"border border-slate-300"}`}>Original rows</button></div>
    <div className="mt-4 flex flex-wrap gap-3"><label className="text-sm font-medium">Workbook<select value={book} onChange={event=>{setBook(event.target.value);setPage(1);}} className="mt-1 block min-w-52 rounded-lg border border-slate-300 bg-white px-3 py-2"><option value="">All workbooks</option>{data?.books.map(item=><option key={item.id} value={item.id}>{item.portfolio}</option>)}</select></label><form onSubmit={submit} className="flex flex-1 items-end gap-2"><label className="min-w-40 flex-1 text-sm font-medium">Search<input value={query} onChange={event=>setQuery(event.target.value)} maxLength={120} placeholder="Asset, lot, date or text" className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2"/></label><button type="submit" className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white">Search</button></form></div>
    {error&&<div role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700"><p>{error}</p><button onClick={()=>setRetry(current=>current+1)} className="mt-2 font-semibold underline">Retry workbook history</button></div>}
    {loading&&<p role="status" className="mt-4 text-sm text-slate-600">Loading workbook history…</p>}
    {!loading&&data&&!data.available&&<p className="mt-4 text-sm text-slate-600">The workbook archive has not been imported yet.</p>}
    {!loading&&!error&&data?.available&&<><p className="mt-4 text-xs text-slate-500">{`${data.total.toLocaleString("en-IN")} ${view==="records"?"records":"rows"}`}</p><div className="mt-2 space-y-2">
      {data.items.map((item,index)=>view==="records"?<RecordCard key={(item as RecordItem).id} item={item as RecordItem}/>:<RowCard key={`${(item as SourceRow).bookId}-${(item as SourceRow).sheet}-${(item as SourceRow).row.n}-${index}`} item={item as SourceRow}/>)}
      {!loading&&!data.items.length&&<p className="rounded-lg border border-dashed border-slate-300 p-5 text-sm text-slate-500">No matching history.</p>}
    </div><div className="mt-4 flex items-center justify-between text-sm"><button disabled={page<=1||loading} onClick={()=>setPage(current=>current-1)} className="rounded-lg border border-slate-300 px-3 py-2 disabled:opacity-40">Previous</button><span>Page {page} of {pages}</span><button disabled={page>=pages||loading} onClick={()=>setPage(current=>current+1)} className="rounded-lg border border-slate-300 px-3 py-2 disabled:opacity-40">Next</button></div></>}
  </section>;
}

function RecordCard({item}:{item:RecordItem}){return <article className="rounded-xl border border-slate-200 p-4 text-sm"><div className="flex flex-wrap items-start justify-between gap-2"><div className="font-semibold">{item.asset||"Unlabelled asset"}</div><span className="text-xs text-slate-500">{item.dateLabel||"Date not recorded"}</span></div><p className="mt-1 text-xs text-slate-500">{item.portfolio} · {item.assetType||"Asset"} · {item.sheet}, row {item.row}</p><div className="mt-2 flex flex-wrap gap-4"><span>RP: {item.rp==null?"—":`₹${item.rp.toLocaleString("en-IN")}`}</span><span>Previous: {item.previousValue==null?"—":`₹${item.previousValue.toLocaleString("en-IN")}`}</span></div>{item.justification&&<p className="mt-2 whitespace-pre-wrap text-slate-700">{item.justification}</p>}{item.outcomeText&&<p className="mt-2 text-slate-600">{item.outcomeText}</p>}</article>}
function RowCard({item}:{item:SourceRow}){return <article className="rounded-xl border border-slate-200 p-4 text-sm"><div className="font-semibold">{item.file} · {item.sheet} · row {item.row.n}</div><div className="mt-2 flex flex-wrap gap-2">{item.row.v.map((value,index)=>value===null||value===""?null:<span key={index} className="rounded-md bg-slate-50 px-2 py-1"><b className="mr-1 text-slate-500">{index+1}</b>{String(value)}{item.row.f[String(index+1)]&&<span className="block text-xs text-slate-500">{item.row.f[String(index+1)]}</span>}</span>)}</div></article>}
