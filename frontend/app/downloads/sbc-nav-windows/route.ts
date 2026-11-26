import {NextResponse} from "next/server";

// Fixed, credential-free release asset. Private office setup comes from the local companion.
export function GET() {
  return NextResponse.redirect("https://github.com/anilsrivatsav/sbcnav/releases/download/windows-v2.2.1/SBC-NAV-Setup-2.2.1.exe",{
    status:307,headers:{"Cache-Control":"no-store","Referrer-Policy":"no-referrer"}
  });
}
