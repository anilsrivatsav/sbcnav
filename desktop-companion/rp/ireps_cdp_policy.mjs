export function allowedTarget(info){
  if(info.type==='browser')return true;
  if((info.type==='page'||info.type==='iframe')&&(info.url==='about:blank'||info.url===''))return true;
  try{const u=new URL(info.url);return u.protocol==='https:'&&['ireps.gov.in','www.ireps.gov.in'].includes(u.hostname);}catch{return false;}
}
