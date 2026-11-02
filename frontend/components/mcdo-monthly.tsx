"use client";
import {useCallback,useEffect,useRef,useState} from "react";
import {Download,FolderOpen,RefreshCw} from "lucide-react";
import {fetchJson} from "../lib/api";
import {Button,Panel} from "./ui";

type Counts={registered:number|string;leased:number|string;newly_created:number|string};
type Configuration={annual_target_crore:string|null;target_source:string;earnings_complete:boolean;earnings_checked_through:string|null;earnings_note:string;asset_position_date:string|null;asset_source:string;assets:Record<string,Counts>;assets_verified:boolean};
type Version={id:string;version:number;filename:string;created_at:string};
type Monthly={period:string;month_name:string;status:string;issues:string[];pending:string[];versions:Version[]};
type Overview={years:string[];selected_year:string;months:Monthly[]};
type Report=Monthly&{revision:number;configuration:Configuration;fingerprint:string;asset_categories:string[];earnings:Record<string,string|null>;policies_crore:Record<string,string>;row_count:number;source:{filename:string;imported_at:string}|null};
type FileHandle={createWritable:()=>Promise<{write:(blob:Blob)=>Promise<void>;close:()=>Promise<void>}>};
type Directory={name:string;getFileHandle:(name:string,options?:{create:boolean})=>Promise<FileHandle>;queryPermission:(options:{mode:string})=>Promise<string>;requestPermission:(options:{mode:string})=>Promise<string>};
const blank:Configuration={annual_target_crore:null,target_source:"",earnings_complete:false,earnings_checked_through:null,earnings_note:"",asset_position_date:null,asset_source:"",assets:{},assets_verified:false};
const api="/api/mcdo/monthly";
const input="soft-inset w-full rounded-lg border border-line p-2 text-sm text-ink";
const format=(v:string|null|undefined)=>v==null?"—":Number(v).toLocaleString("en-IN",{maximumFractionDigits:6});
const defaultFolder="D:\\ANIL\\Publicity files\\MCDO\\MCDO\\All Files";

async function folderStore(value?:Directory){
  return new Promise<Directory|undefined>((resolve,reject)=>{
    const open=indexedDB.open("sbcnav-mcdo-downloads",1);
    open.onupgradeneeded=()=>open.result.createObjectStore("preferences");
    open.onerror=()=>reject(open.error);
    open.onsuccess=()=>{
      const db=open.result,tx=db.transaction("preferences",value?"readwrite":"readonly"),store=tx.objectStore("preferences");
      const request=value?store.put(value,"folder"):store.get("folder");
      let saved:Directory|undefined;
      request.onsuccess=()=>{saved=value||request.result;};
      tx.oncomplete=()=>{db.close();resolve(saved);};
      tx.onerror=()=>{db.close();reject(tx.error);};
    };
  });
}

export function McdoMonthly({refreshKey=""}:{refreshKey?:string}){
  const [overview,setOverview]=useState<Overview|null>(null),[year,setYear]=useState(""),[period,setPeriod]=useState("");
  const [report,setReport]=useState<Report|null>(null),[config,setConfig]=useState<Configuration>(blank);
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState("");
  const [authenticated,setAuthenticated]=useState(false),[key,setKey]=useState("");
  const [folder,setFolder]=useState<Directory|null>(null),[dirty,setDirty]=useState(false);
  const [selectedVersion,setSelectedVersion]=useState("");
  const sequence=useRef(0);
  const loadOverview=useCallback(async()=>{
    const result:Overview=await fetchJson(`${window.location.origin}${api}${year?`?year=${encodeURIComponent(year)}`:""}`);
    setOverview(result);
    return result;
  },[year]);
  useEffect(()=>{
    let active=true;setError("");
    loadOverview().then(result=>{if(active)setPeriod(old=>result.months.some(m=>m.period===old)?old:result.months.filter(m=>m.versions.length).at(-1)?.period||result.months.find(m=>m.period===new Date().toLocaleDateString("en-CA",{timeZone:"Asia/Kolkata"}).slice(0,7))?.period||result.months[0].period);}).catch(e=>{if(active)setError(e.message);});
    return()=>{active=false;};
  },[loadOverview,refreshKey]);
  useEffect(()=>{
    let active=true;
    fetchJson(`${window.location.origin}/api/mcdo/session`).then(()=>{if(active)setAuthenticated(true);}).catch(()=>{if(active)setAuthenticated(false);});
    folderStore().then(saved=>{if(saved&&active)setFolder(saved);}).catch(()=>{});
    return()=>{active=false;};
  },[]);
  const loadReport=useCallback(async()=>{
    if(!period)return;
    const request=++sequence.current;setLoading(true);setError("");setReport(null);setDirty(false);
    try{
      const data:Report=await fetchJson(`${window.location.origin}${api}/${period}`);
      if(request===sequence.current){setReport(data);setConfig(data.configuration);setSelectedVersion(data.versions[0]?.id||"");}
    }catch(e){if(request===sequence.current)setError(e instanceof Error?e.message:"Report could not load.");}
    finally{if(request===sequence.current)setLoading(false);}
  },[period]);
  useEffect(()=>{void loadReport();return()=>{sequence.current++;};},[loadReport,refreshKey]);
  function change<K extends keyof Configuration>(field:K,value:Configuration[K]){setConfig(old=>({...old,[field]:value}));setDirty(true);setMessage("");}
  async function signIn(){
    setBusy(true);setError("");
    try{await fetchJson(`${window.location.origin}/api/mcdo/session`,{method:"POST",headers:{Authorization:`Bearer ${key.trim()}`,"Content-Type":"application/json"},body:"{}"});setAuthenticated(true);setKey("");}
    catch(e){setError(e instanceof Error?e.message:"Operator sign-in failed.");}finally{setBusy(false);}
  }
  async function save(){
    if(!report)return;setBusy(true);setError("");setMessage("");
    try{
      const assets=Object.fromEntries(Object.entries(config.assets).map(([name,counts])=>[name,Object.fromEntries(Object.entries(counts).map(([k,v])=>{if(v===""||!Number.isInteger(Number(v)))throw new Error(`Enter whole-number counts for ${name}.`);return [k,Number(v)];}))]));
      const result:Report=await fetchJson(`${window.location.origin}${api}/${period}/draft`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({expected_revision:report.revision,configuration:{...config,assets}})});
      setReport(result);setConfig(result.configuration);setDirty(false);setMessage("Monthly inputs saved and validated.");await loadOverview();
    }catch(e){setError(e instanceof Error?e.message:"Monthly inputs could not save.");}finally{setBusy(false);}
  }
  async function complete(){
    if(!report)return;setBusy(true);setError("");
    try{
      await fetchJson(`${window.location.origin}${api}/${period}/complete`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({fingerprint:report.fingerprint})});
      await loadReport();await loadOverview();setMessage("Month completed. Its Excel report is saved and ready to download.");
    }catch(e){setError(e instanceof Error?e.message:"Month could not complete.");}finally{setBusy(false);}
  }
  async function chooseFolder(){
    setError("");
    const picker=(window as unknown as {showDirectoryPicker?: (options:{id:string;mode:string})=>Promise<Directory>}).showDirectoryPicker;
    if(!picker){setMessage(`This browser uses its normal download location. Use Save As to select ${defaultFolder}.`);return;}
    try{const chosen=await picker({id:"sbcnav-mcdo",mode:"readwrite"});setFolder(chosen);await folderStore(chosen);setMessage(`Reports will save in ${chosen.name}. Select the All Files folder at ${defaultFolder}.`);}
    catch(e){if((e as Error).name!=="AbortError")setError("Could not remember this folder. Allow folder access and try again.");}
  }
  async function download(){
    const version=report?.versions.find(v=>v.id===selectedVersion);if(!version)return;
    setBusy(true);setError("");setMessage("");
    try{
      // Request permission while this click still has browser user activation.
      if(folder&&await folder.queryPermission({mode:"readwrite"})!=="granted"&&await folder.requestPermission({mode:"readwrite"})!=="granted")throw new Error("Folder access was not granted. Choose a folder or use Browser downloads.");
      const response=await fetch(`${api}/${period}/download/${version.id}`,{cache:"no-store"});
      if(!response.ok){const data=await response.json();throw new Error(data.detail||"Report download failed.");}
      const blob=await response.blob();
      if(folder){
        let name=version.filename;
        try{await folder.getFileHandle(name);name=name.replace(/\.xlsx$/,`_copy_${Date.now()}.xlsx`);}catch(e){if((e as Error).name!=="NotFoundError")throw e;}
        const handle=await folder.getFileHandle(name,{create:true}),writer=await handle.createWritable();await writer.write(blob);await writer.close();
        setMessage(`Saved ${name} in ${folder.name}.`);
      }else{
        const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=version.filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
        setMessage(`Download started. To save in the MCDO folder, choose ${defaultFolder} in your browser's Save As dialog.`);
      }
    }catch(e){setError(e instanceof Error?e.message:"Could not save the report.");}finally{setBusy(false);}
  }
  return <Panel title="Monthly MCDO · SBC Division" subtitle="Complete the month once all earnings and the dated IREPS asset position have been reconciled.">
    <div className="flex flex-wrap items-end gap-3">
      <label className="grid gap-1 text-xs font-bold">Financial year<select className={input} value={year||overview?.selected_year||""} disabled={busy} onChange={e=>{setYear(e.target.value);setMessage("");}}>{overview?.years.map(y=><option key={y}>{y}</option>)}</select></label>
      <label className="grid gap-1 text-xs font-bold">Month<select className={input} value={period} disabled={busy} onChange={e=>{setPeriod(e.target.value);setMessage("");}}>{overview?.months.map(m=><option key={m.period} value={m.period}>{m.month_name} {m.period.slice(0,4)} · {m.status}{m.versions.length?` · ${m.versions.length} saved`:""}</option>)}</select></label>
      <Button variant="secondary" disabled={busy||loading} onClick={()=>{void loadOverview();void loadReport();}}><RefreshCw size={15}/>Refresh</Button>
    </div>
    {error&&<p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    {message&&<p role="status" className="mt-3 text-sm font-bold">{message}</p>}
    {loading&&<p role="status" className="mt-3 text-sm">Loading monthly data…</p>}
    {report&&<>
      <div className="my-4 flex flex-wrap gap-3 rounded-lg border border-line p-3 text-sm"><strong>{dirty?"Unsaved inputs":report.status}</strong><span>{report.row_count} financial-year receipts through this month</span><span>Source: {report.source?.filename||"Not imported"}</span></div>
      <div className="grid gap-3 sm:grid-cols-3">{[["Previous cumulative · ₹ crore",report.earnings.previous_crore],["Selected month · ₹ crore",report.earnings.current_crore],["Cumulative · ₹ crore",report.earnings.cumulative_crore]].map(([label,value])=><div key={label} className="soft-inset rounded-lg border border-line p-3"><p className="text-xs text-muted">{label}</p><p className="mt-1 text-lg font-bold">{format(value)}</p></div>)}</div>
      {(report.issues.length>0||report.pending.length>0)&&<div className="my-4 rounded-lg border border-amber-300 p-3"><p className="text-sm font-bold">Required before completion</p><ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{[...report.issues,...report.pending].map((issue,i)=><li key={i}>{issue}</li>)}</ul></div>}
      <details className="my-4 rounded-lg border border-line p-3"><summary className="cursor-pointer text-sm font-bold">Monthly inputs and completion</summary>
        {!authenticated&&<div className="my-4 flex flex-wrap items-end gap-2"><label className="grid gap-1 text-xs font-bold">Existing MCDO operator key<input type="password" autoComplete="off" className={input} value={key} onChange={e=>setKey(e.target.value)}/></label><Button disabled={busy||!key.trim()} onClick={signIn}>Sign in to save</Button><p className="w-full text-xs text-muted">The existing operator key authorises changes. Saved reports remain available for download.</p></div>}
        <fieldset disabled={!authenticated||busy} className="mt-4 space-y-4 disabled:opacity-60">
          <div className="grid gap-3 sm:grid-cols-2"><label className="grid gap-1 text-xs font-bold">Annual SBC target · ₹ crore<input type="number" min="0.000001" step="0.000001" className={input} value={config.annual_target_crore??""} onChange={e=>change("annual_target_crore",e.target.value||null)}/></label><label className="grid gap-1 text-xs font-bold">Target source / order reference<input className={input} value={config.target_source} onChange={e=>change("target_source",e.target.value)}/></label></div>
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={config.earnings_complete} onChange={e=>change("earnings_complete",e.target.checked)}/>All earnings from 1 April through this month are collected and reconciled, including any months with no earnings.</label>
          <div className="grid gap-3 sm:grid-cols-2"><label className="grid gap-1 text-xs font-bold">Earnings verified through<input type="date" className={input} value={config.earnings_checked_through||""} onChange={e=>change("earnings_checked_through",e.target.value||null)}/></label><label className="grid gap-1 text-xs font-bold">Reconciliation reference / remarks<input className={input} value={config.earnings_note} onChange={e=>change("earnings_note",e.target.value)}/></label></div>
          <p className="text-sm">Use IREPS <strong>Asset Utilization Report</strong> and <strong>Asset Utilization Count and Value Report</strong> for SBC. Record the report date and retain its reference. For a previous month, use its dated report or saved snapshot.</p>
          <a href="https://www.ireps.gov.in/epsn/home/showHome.do" target="_blank" rel="noreferrer" className="text-sm font-bold text-accentStrong underline">Open IREPS · E-Reports</a>
          <div className="grid gap-3 sm:grid-cols-2"><label className="grid gap-1 text-xs font-bold">Asset report position date<input type="date" className={input} value={config.asset_position_date||""} onChange={e=>change("asset_position_date",e.target.value||null)}/></label><label className="grid gap-1 text-xs font-bold">IREPS report / historical snapshot reference<input className={input} value={config.asset_source} onChange={e=>change("asset_source",e.target.value)}/></label></div>
          <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="mb-2 text-left text-xs text-muted">Enter all nine categories. Empty counts remain missing; zero must be entered explicitly.</caption><thead><tr>{["Asset category","Registered","Leased","New this month","Idle"].map(h=><th key={h} className="p-2">{h}</th>)}</tr></thead><tbody>{report.asset_categories.map(category=><tr key={category} className="border-t border-line"><th className="p-2 font-medium">{category}</th>{(["registered","leased","newly_created"] as const).map(field=><td className="p-2" key={field}><input aria-label={`${category} ${field}`} type="number" min="0" step="1" className={`${input} min-w-20`} value={config.assets[category]?.[field]??""} onChange={e=>change("assets",{...config.assets,[category]:{registered:"",leased:"",newly_created:"",...config.assets[category],[field]:e.target.value}})}/></td>)}<td className="p-2">{config.assets[category]?.registered!==undefined&&config.assets[category]?.registered!==""&&config.assets[category]?.leased!==undefined&&config.assets[category]?.leased!==""?Number(config.assets[category].registered)-Number(config.assets[category].leased):"—"}</td></tr>)}</tbody></table></div>
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={config.assets_verified} onChange={e=>change("assets_verified",e.target.checked)}/>I verified these asset counts against the dated SBC reports for this reporting month.</label>
          <div className="flex flex-wrap gap-2"><Button onClick={save} disabled={busy||!dirty}>Save and validate</Button><Button variant="secondary" onClick={complete} disabled={busy||dirty||report.issues.length>0||report.pending.length>0||report.status==="Ready to Download"}>{report.versions.length?"Complete revised version":"Complete month"}</Button></div>
        </fieldset>
      </details>
      <details className="my-4 text-sm"><summary className="cursor-pointer font-bold">Policy totals · ₹ crore</summary><div className="mt-2 grid grid-cols-3 gap-2">{Object.entries(report.policies_crore).map(([code,value])=><p key={code}>{code}: <strong>{format(value)}</strong></p>)}</div><p className="mt-2 text-xs text-muted">Uses NFR earnings excluding GST. PUB and NFR overlap and are not added. The Excel template's percentages show excess / shortfall against target.</p></details>
      <div className="flex flex-wrap items-end gap-3 border-t border-line pt-4">
        <label className="grid gap-1 text-xs font-bold">Completed report version<select className={input} value={selectedVersion} onChange={e=>setSelectedVersion(e.target.value)} disabled={busy||!report.versions.length}>{!report.versions.length&&<option value="">No completed version</option>}{report.versions.map(v=><option key={v.id} value={v.id}>Version {v.version} · {new Date(v.created_at).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"})}</option>)}</select></label>
        <Button onClick={download} disabled={busy||!selectedVersion}><Download size={15}/>Download MCDO Excel</Button>
        <Button variant="secondary" onClick={chooseFolder} disabled={busy}><FolderOpen size={15}/>{folder?`Folder: ${folder.name}`:"Choose MCDO folder"}</Button>
        {folder&&<Button variant="ghost" disabled={busy} onClick={()=>setFolder(null)}>Use browser downloads</Button>}
      </div>
      <p className="mt-3 break-words text-xs text-muted">Preferred folder: {defaultFolder}. Choose it once to remember it in this browser. Existing files and earlier report versions are preserved.</p>
      {report.versions.length>0&&report.status!=="Ready to Download"&&<p className="mt-2 text-xs text-muted">Saved versions remain available. Changed source data or inputs require completion of a revised version.</p>}
    </>}
  </Panel>;
}
