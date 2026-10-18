"use client";
import {useCallback,useEffect,useState} from "react";
import {Button,Panel} from "./ui";

type Progress={busy:boolean;updater_busy:boolean;phase:string;message:string;error?:string};
const LOCAL="http://127.0.0.1:48722/deskflow";
export function Deskflow(){
  const [status,setStatus]=useState<Progress|null>(null),[reachable,setReachable]=useState(false),[sending,setSending]=useState(false),[error,setError]=useState("");
  const refresh=useCallback(async()=>{try{const response=await fetch(LOCAL+"/progress",{cache:"no-store",signal:AbortSignal.timeout(5000)});if(!response.ok)throw Error();setStatus(await response.json());setReachable(true);}catch{setReachable(false);}},[]);
  useEffect(()=>{let active=false;const poll=async()=>{if(active)return;active=true;try{await refresh();}finally{active=false;}};void poll();const timer=setInterval(poll,3000);return()=>clearInterval(timer);},[refresh]);
  async function update(){setSending(true);setError("");try{
    if(!reachable){window.location.href="sbcnav-updater://open";return;}
    const response=await fetch(LOCAL+"/update",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}",signal:AbortSignal.timeout(15000)});
    const result=await response.json();if(!response.ok)throw Error(result.error||"Update could not start.");setStatus(result);
  }catch(e){setError(e instanceof Error?e.message:"Connection failed. Try again.");}finally{setSending(false);}}
  return <Panel title="Deskflow">
    <Button disabled={sending||!!status?.busy} onClick={update}>{!reachable?"Open desktop connection":status?.busy?"Updating local workbooks…":"Update local workbooks"}</Button>
    <p className="mt-4 text-sm" role="status" aria-live="polite">{reachable?status?.message:"Open the desktop connection to update the workbooks on this computer."}</p>
    {(error||status?.error)&&<p className="mt-3 text-sm text-red-700" role="alert">{error||status?.error}</p>}
  </Panel>;
}
