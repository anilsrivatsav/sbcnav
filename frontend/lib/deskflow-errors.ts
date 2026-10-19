export function deskflowError(reason:unknown, fallback:string):string {
  if(reason instanceof Error){
    if(reason.name==="TimeoutError"||reason.name==="AbortError")return `${fallback} The request timed out. Check your connection and try again.`;
    if(reason instanceof TypeError)return `${fallback} Could not connect to Deskflow. Check your connection and try again.`;
    return reason.message||fallback;
  }
  return fallback;
}

export async function deskflowResponse<T>(response:Response, fallback:string):Promise<T> {
  const data=await response.json().catch(()=>null);
  if(!response.ok){
    const detail=data?.detail||data?.error;
    const message=typeof detail==="string"?detail:Array.isArray(detail)?detail.map(item=>item.msg).filter(Boolean).join("; "):"";
    throw Error(message||(response.status===401?"Session expired. Unlock Deskflow again.":`${fallback} (HTTP ${response.status}). Try again shortly.`));
  }
  if(!data)throw Error(`${fallback} Deskflow returned an unreadable response. Try again shortly.`);
  return data as T;
}
