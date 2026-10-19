import {NextRequest,NextResponse} from "next/server";

export const runtime="nodejs";
export const dynamic="force-dynamic";

async function proxy(request:NextRequest,{params}:{params:Promise<{path?:string[]}>}){
  const parts=(await params).path||[];
  if(parts.length!==1||!["unlock","overview","software-update","collect","history","workbook-history","sync-workbooks","eauction","holidays"].includes(parts[0]))return NextResponse.json({error:"Unknown Deskflow route."},{status:404});
  if(request.method!=="GET"&&request.headers.get("origin")!==new URL(request.url).origin)return NextResponse.json({error:"Untrusted request."},{status:403});
  const body=request.method==="POST"?await request.text():undefined;
  if(body&&new TextEncoder().encode(body).length>100000)return NextResponse.json({error:"Request is too large."},{status:413});
  const authorization=request.headers.get("authorization");
  const base=process.env.DESKFLOW_API_URL||"https://sbcnav.137-23-58-53.sslip.io";
  try{
    const query=["workbook-history","holidays"].includes(parts[0])?request.nextUrl.search:"";
    const upstream=await fetch(`${base.replace(/\/$/,"")}/api/deskflow/${parts[0]}${query}`,{method:request.method,headers:{"Content-Type":"application/json",...(authorization?{Authorization:authorization}:{})},body,cache:"no-store",signal:AbortSignal.timeout(20000)});
    const data=await upstream.json();
    return NextResponse.json(data,{status:upstream.status,headers:{"Cache-Control":"no-store"}});
  }catch{
    return NextResponse.json({error:"Deskflow service is unavailable."},{status:502});
  }
}
export const GET=proxy;
export const POST=proxy;
export const DELETE=proxy;
