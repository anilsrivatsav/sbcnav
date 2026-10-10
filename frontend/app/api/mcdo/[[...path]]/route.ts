import {NextRequest,NextResponse} from "next/server";

export const runtime="nodejs";
export const dynamic="force-dynamic";
const cookieName="sbcnav_mcdo_session";
async function proxy(request:NextRequest,{params}:{params:Promise<{path?:string[]}>}) {
  const parts=(await params).path||[];
  if(parts.some(p=>!/^[-a-zA-Z0-9]+$/.test(p)))return NextResponse.json({detail:"Invalid updater route."},{status:400});
  const path=parts.join("/");
  // A paired extension may renew a session using its existing operator key.
  // Writes still require a same-origin request and the verified HttpOnly session.
  const deviceLogin=path==="session"&&request.method==="POST"&&request.headers.get("authorization")?.startsWith("Bearer ");
  if(request.method!=="GET"&&!deviceLogin&&request.headers.get("origin")!==new URL(request.url).origin)return NextResponse.json({detail:"Untrusted updater request."},{status:403});
  if(request.method==="DELETE"&&path==="session"){
    const response=NextResponse.json({success:true,data:{authenticated:false}});response.cookies.set(cookieName,"",{path:"/api/mcdo",maxAge:0});return response;
  }
  const session=request.cookies.get(cookieName)?.value;
  const authorization=path==="session"&&request.method==="POST"?request.headers.get("authorization"):session?`Bearer ${session}`:null;
  if(path&&!authorization)return NextResponse.json({detail:"Sign in to SBC NAV updater."},{status:401});
  const base=process.env.NEXT_PUBLIC_API_URL;
  if(!base)return NextResponse.json({detail:"Oracle backend connection is not configured."},{status:503});
  const body=request.method==="POST"?await request.text():undefined;
  if(body&&new TextEncoder().encode(body).length>32*1024*1024)return NextResponse.json({detail:"IREPS evidence is too large."},{status:413});
  try {
    const upstream=await fetch(`${base.replace(/\/$/,"")}/api/mcdo${path?`/${path}`:""}${new URL(request.url).search}`,{method:request.method,headers:{"Content-Type":"application/json",...(authorization?{Authorization:authorization}:{})},body,cache:"no-store",signal:AbortSignal.timeout(120000)});
    const data=await upstream.json();
    if(upstream.status===404)return NextResponse.json({detail:"The Oracle updater backend has not been deployed yet."},{status:503});
    const sessionToken=data.data?.session_token;
    if(sessionToken)delete data.data.session_token;
    const response=NextResponse.json(data,{status:upstream.status});
    if(upstream.status===401)response.cookies.set(cookieName,"",{path:"/api/mcdo",maxAge:0});
    if(upstream.ok&&path==="session"&&request.method==="POST"&&sessionToken)response.cookies.set(cookieName,sessionToken,{httpOnly:true,secure:new URL(request.url).protocol==="https:",sameSite:"strict",path:"/api/mcdo",maxAge:8*3600});
    return response;
  }catch{return NextResponse.json({detail:"Oracle updater could not be reached. No successful update has been confirmed."},{status:502});}
}
export const GET=proxy;
export const POST=proxy;
export const DELETE=proxy;
