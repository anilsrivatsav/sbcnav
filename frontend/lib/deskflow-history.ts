export type WorkbookWorking={id:string;date:string;asset:string;rp:number|null;justification:string;sheet:string;row:number;portfolio:string};
let active=0;
const waiting:(()=>void)[]=[];
const cache=new Map<string,Promise<WorkbookWorking[]>>();

export function loadWorkbookWorkings(token:string,query:string,revision?:string){
  const key=`${token}|${revision||""}|${query}`;
  let request=cache.get(key);
  if(!request){
    request=(async()=>{
      if(active>=2)await new Promise<void>(resolve=>waiting.push(resolve));
      else active++;
      try{
        const params=new URLSearchParams({q:query,view:"records",limit:"100"});
        const response=await fetch(`/api/deskflow/workbook-history?${params}`,{headers:{Authorization:`Bearer ${token}`},cache:"no-store",signal:AbortSignal.timeout(15000)});
        if(!response.ok)throw Error("Previous RP and justification could not be loaded.");
        const data=await response.json();
        // A truncated search cannot establish a unique matching workbook row.
        if(data.total>100)throw Error("Too many workbook matches. Search the exact asset to compare previous RP.");
        return data.items as WorkbookWorking[];
      }finally{const next=waiting.shift();if(next)next();else active--;}
    })();
    cache.set(key,request);
    request.catch(()=>cache.delete(key));
    if(cache.size>100)cache.delete(cache.keys().next().value!);
  }
  return request;
}
