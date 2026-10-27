let busy=false,timer=null,nativeRetryAt=0;
const api=async(path,data)=>{const{token}=await chrome.storage.local.get('token');if(!token)throw Error('No connection key');const r=await fetch('http://127.0.0.1:8765/'+path,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(data)});if(!r.ok)throw Error('Windows app is not connected');return r.json();};
async function run(tab,func,args=[]){const result=await chrome.scripting.executeScript({target:{tabId:tab},func,args});if(!result[0])throw Error('IREPS page unavailable');return result[0].result;}
async function ready(tab,previousStamp=null,requireSigned=true){for(let n=0;n<100;n++){const t=await chrome.tabs.get(tab);if(t.status==='complete'){let info;try{info=await run(tab,()=>({stamp:performance.timeOrigin,complete:document.readyState==='complete',signed:!!document.querySelector('a[href*="/logout.do"]')}));}catch(e){if(!/Execution context was destroyed|frame.*removed/i.test(e.message))throw e;}if(info?.complete&&(previousStamp===null||info.stamp!==previousStamp)){if(requireSigned&&!info.signed)throw Error('IREPS session expired. Sign in in your browser and reconnect; collected records remain saved.');return;}}await new Promise(r=>setTimeout(r,250));}throw Error('IREPS page did not finish loading. Collection stopped rather than reading a stale page.');}
async function stamp(tab){return run(tab,()=>performance.timeOrigin);}
async function folder(tab,label,dates={}){
 await ready(tab);
 if(!await run(tab,label=>[...(document.querySelector('#status')?.options||[])].some(o=>o.text.trim()===label),[label])){
  const before=await stamp(tab);
  const moved=await run(tab,()=>{const home=[...document.querySelectorAll('a')].find(a=>a.href?.includes('/home/showHome.do')&&a.title==='IREPS Home Page');if(home){home.click();return true;}return false;});
  if(!moved)throw Error('Open your signed-in IREPS home page or Auctions / Catalogues listing first.');
  await ready(tab,before);
  await run(tab,()=>{const a=[...document.querySelectorAll('a')].find(a=>a.innerText.trim()==='Auctions');if(!a)throw Error('IREPS Auctions menu unavailable');a.click();});
  let menuReady=false;
  for(let n=0;n<100;n++){
   try{menuReady=await run(tab,()=>[...document.querySelectorAll('a')].some(a=>/^Scheduled Auctions \(Yet to start\)/.test(a.innerText.trim())&&a.getClientRects().length>0));}catch(e){if(!/Execution context was destroyed|frame.*removed/i.test(e.message))throw e;}
   if(menuReady)break;await new Promise(r=>setTimeout(r,250));
  }
  if(!menuReady)throw Error('IREPS Auctions menu did not load');
  const navStamp=await stamp(tab);
  await run(tab,()=>{const a=[...document.querySelectorAll('a')].find(a=>/^Scheduled Auctions \(Yet to start\)/.test(a.innerText.trim()));if(!a)throw Error('Scheduled Auctions link unavailable');a.click();});
  await ready(tab,navStamp);
 }
 const before=await stamp(tab);
 await run(tab,({label,dates})=>{const s=document.querySelector('#status');if(!s)throw Error('Open IREPS Auctions / Catalogues first.');const o=[...s.options].find(o=>o.text.trim()===label);if(!o)throw Error('Requested auction folder unavailable');s.value=o.value;if(dates.from_date){const from=document.querySelector('#ddmmyyDateformat1'),to=document.querySelector('#ddmmyyDateformat2');if(!from||!to)throw Error('Date search controls unavailable');from.value=dates.from_date.split('-').reverse().join('/');to.value=dates.to_date.split('-').reverse().join('/');}const b=[...document.querySelectorAll('button,input[type=button],input[type=submit]')].find(b=>(b.innerText||b.value).trim()==='Search');if(!b)throw Error('Search control unavailable');b.click();},[{label,dates}]);
 await ready(tab,before);
}
async function catalogue(tab){return run(tab,()=>{const clean=s=>String(s||'').replace(/\s+/g,' ').trim(),rows=[...document.querySelectorAll('tr')].filter(r=>!r.querySelector('table'));let catalogue='',start='';for(const r of rows){const c=[...r.children].map(c=>clean(c.innerText));if(c[0]==='Auction Catalogue No.')catalogue=c[1];if(c[0]?.startsWith('Auction Start'))start=c[1];}const h=rows.find(r=>r.innerText.includes('Lot Status')&&r.innerText.includes('Rate Unit'));if(!h)throw Error('Open an outside catalogue listing. Do not open a lot.');const labels=[...h.children].map(c=>clean(c.innerText).toLowerCase()),find=s=>labels.findIndex(x=>x.includes(s));return rows.filter(r=>r!==h&&r.querySelector('a[title*="View Lot"]')).map(r=>{const c=[...r.children],v=c.map(c=>clean(c.innerText));return{lot:v[find('lot no')].split('(')[0].trim(),catalogue,start,category:v[find('lot no')].split('(').slice(1).join('(').replace(/\)$/,''),description:c[find('description')]?.querySelector('img[title]')?.title||v[find('description')],rate_unit:v[find('rate unit')],trips_days:v[find('trips')],close:v[find('close date')],status:v[find('lot status')],source:location.href};});});}
async function ids(tab){return run(tab,()=>[...document.querySelectorAll('tr')].filter(r=>!r.querySelector('table')&&r.querySelector('a[title*="View Auction Catalogue"],img[alt*="View Auction Catalogue"],img[alt*="View Auction Catalugue"]')).map(r=>r.cells[0].innerText.trim()));}
async function openCatalogue(tab,id){const before=await stamp(tab);await run(tab,id=>{const r=[...document.querySelectorAll('tr')].find(r=>!r.querySelector('table')&&r.cells[0]?.innerText.trim()===id);if(!r)throw Error('Catalogue not found');const a=[...r.querySelectorAll('a')].find(a=>/View Auction Catal(ogue|ugue)/i.test(a.title+' '+a.innerText+' '+(a.querySelector('img')?.alt||'')));if(!a)throw Error('Read-only catalogue link unavailable');a.click();},[id]);await ready(tab,before);}
async function acceptedBid(tab,lot){
 const parentUrl=(await chrome.tabs.get(tab)).url;
 const captured=await chrome.scripting.executeScript({target:{tabId:tab},world:'MAIN',func:lot=>{
  const rows=[...document.querySelectorAll('tr')].filter(r=>!r.querySelector('table')),h=rows.find(r=>r.innerText.includes('Lot Status')&&r.innerText.includes('Rate Unit'));if(!h)throw Error('Outside lot listing unavailable');const labels=[...h.children].map(c=>c.innerText.trim().toLowerCase()),li=labels.findIndex(t=>t.includes('lot no')),si=labels.findIndex(t=>t.includes('lot status'));const row=rows.find(r=>r!==h&&r.children[li]?.innerText.split('(')[0].trim()===lot);if(!row||!/^Sold\b/i.test(row.children[si]?.innerText.trim()))throw Error('Only the exact sold lot may open bid-rate details');const link=[...row.querySelectorAll('a')].find(a=>/^[1-9]\d*$/.test(a.innerText.trim()));if(!link)throw Error('Sold bid link is unavailable');
  // Resolve the site's own bid-number action, keeping its window out of the foreground.
  const original=window.open;let url='';
  window.open=function(value){const resolved=new URL(String(value),location.href);if(resolved.origin!==location.origin||!resolved.pathname.endsWith('/viewBiddingDetail.do'))throw Error('Unexpected bidding viewer target');url=resolved.href;return{focus(){},closed:false};};
  try{link.click();if(!url)throw Error('The bid viewer target was not supplied by the site');return url;}finally{window.open=original;}
 },args:[lot]});
 const url=captured[0]?.result;if(!url)throw Error('Sold bid viewer unavailable');
 const parent=await chrome.tabs.get(tab);const popup=await chrome.tabs.create({url,active:false,windowId:parent.windowId});
 try{await ready(popup.id,null,false);return await run(popup.id,()=>{const rs=[...document.querySelectorAll('tr')].filter(r=>!r.querySelector('table')),h=rs.find(r=>r.innerText.includes('Bid Rate')&&r.innerText.includes('Bid Value'));if(!h)throw Error('Bid Rate / Bid Value columns were not found');const labels=[...h.cells].map(c=>c.innerText.trim()),ri=labels.indexOf('Bid Rate'),vi=labels.indexOf('Bid Value');if(ri<0||vi<0)throw Error('The accepted rate cannot be identified');const bids=rs.filter(r=>r!==h&&r.cells.length===labels.length).map(r=>({bid_rate:Number(r.cells[ri].innerText.replace(/[₹,\s]/g,'')),bid_value:r.cells[vi].innerText.trim(),bid_source:location.href})).filter(b=>Number.isFinite(b.bid_rate)&&b.bid_rate>0);if(!bids.length)throw Error('No positive BID RATE was found; total value will not be substituted');return bids.sort((a,b)=>b.bid_rate-a.bid_rate)[0];});}finally{await chrome.tabs.remove(popup.id);const after=(await chrome.tabs.get(tab)).url;if(after!==parentUrl&&after.split('#')[0]===parentUrl.split('#')[0]){await chrome.tabs.goBack(tab);await ready(tab);}}
}
async function contractListing(tab,job){
 await ready(tab);
 const hasTable=await run(tab,()=>[...document.querySelectorAll('tr')].some(r=>!r.querySelector('table')&&/Contract.*(No|Number)/i.test(r.innerText)&&/(Licensee|Licencee|Contractor)/i.test(r.innerText)));
 if(!hasTable){
  if(!await run(tab,()=>[...document.querySelectorAll('a')].some(a=>a.innerText.trim()==='Contracts'&&a.getClientRects().length))){
   const before=await stamp(tab);await run(tab,()=>{const a=[...document.querySelectorAll('a')].find(a=>a.href?.includes('/home/showHome.do'));if(!a)throw Error('Return to the signed-in IREPS home page to read contracts');a.click();});await ready(tab,before);
  }
  await run(tab,()=>{const a=[...document.querySelectorAll('a')].find(a=>a.innerText.trim()==='Contracts'&&a.getClientRects().length);if(!a)throw Error('Contracts menu unavailable');a.click();});
  let found=false;for(let n=0;n<100;n++){try{found=await run(tab,()=>[...document.querySelectorAll('a')].some(a=>a.innerText.trim()==='View Contracts'&&a.getClientRects().length));}catch(e){if(!/Execution context was destroyed|frame.*removed/i.test(e.message))throw e;}if(found)break;await new Promise(r=>setTimeout(r,250));}
  if(!found)throw Error('View Contracts menu did not load');
  const before=await stamp(tab);await run(tab,()=>{[...document.querySelectorAll('a')].find(a=>a.innerText.trim()==='View Contracts'&&a.getClientRects().length).click();});await ready(tab,before);
 }
 const before=await stamp(tab);
 await run(tab,dates=>{
  const select=[...document.querySelectorAll('select')].find(s=>[...s.options].some(o=>/^Draft$/i.test(o.text.trim()))&&[...s.options].some(o=>/^All$/i.test(o.text.trim())));
  if(!select)throw Error('The contract status filter could not be identified. No contract actions were used.');
  select.value=[...select.options].find(o=>/^All$/i.test(o.text.trim())).value;
  if(dates.from_date){const from=document.querySelector('#ddmmyyDateformat1'),to=document.querySelector('#ddmmyyDateformat2');if(!from||!to)throw Error('Contract date search controls unavailable');from.value=dates.from_date.split('-').reverse().join('/');to.value=dates.to_date.split('-').reverse().join('/');}
  const search=[...document.querySelectorAll('button,input[type=button],input[type=submit]')].find(b=>(b.innerText||b.value).trim()==='Search');if(!search)throw Error('Contract search unavailable');search.click();
 },[job]);await ready(tab,before);
 const range=await run(tab,()=>({from:document.querySelector('#ddmmyyDateformat1')?.value||'current search',to:document.querySelector('#ddmmyyDateformat2')?.value||'current search'}));
 await api('progress',{id:job.id,range,message:'Reading all contract statuses',complete:false});
 const rows=[],seen=new Set();
 for(let page=1;page<=100;page++){
  const current=await run(tab,()=>{const rs=[...document.querySelectorAll('tr')].filter(r=>!r.querySelector('table')),h=rs.find(r=>/Contract.*(No|Number)/i.test(r.innerText)&&/(Licensee|Licencee|Contractor)/i.test(r.innerText));if(!h)throw Error('Contract list columns were not found');const clean=s=>String(s||'').replace(/\s+/g,' ').trim(),labels=[...h.cells].map(c=>clean(c.innerText));return rs.filter(r=>r!==h&&r.cells.length===labels.length).map(r=>({...Object.fromEntries([...r.cells].map((c,i)=>[labels[i],clean(c.innerText)])),source:location.href}));});
  const marker=JSON.stringify(current);if(seen.has(marker))throw Error('Contract pagination repeated a page');seen.add(marker);rows.push(...current);
  const before=await stamp(tab),next=await run(tab,n=>{const a=[...document.querySelectorAll('a')].find(a=>a.innerText.trim()===String(n));if(!a)return false;a.click();return true;},[page+1]);if(!next){const total=await run(tab,()=>Number((document.body.innerText.match(/([0-9,]+)\s+Records Found/i)||[])[1]?.replace(/,/g,'')||0));if(total>rows.length)throw Error('Contract pagination stopped at '+rows.length+' of '+total+' records.');await api('progress',{id:job.id,range,rows:rows.length,message:'Contract scan finished',complete:true});return rows;}if(page===100)throw Error('Contract scan exceeded 100 pages');await ready(tab,before);
 }return rows;
}
async function execute(tab,job){
 if(job.action==='contracts')return contractListing(tab,job);
 if(!['scheduled','closed'].includes(job.action))throw Error('Unsupported read-only collection command');
 await folder(tab,job.action==='scheduled'?'Scheduled Auctions (Yet to start)':'Closed Auctions (No Action Pending)',job);const collected=[],seen=new Set(),visited=[];
 const range=await run(tab,()=>({from:document.querySelector('#ddmmyyDateformat1')?.value||'current search',to:document.querySelector('#ddmmyyDateformat2')?.value||'current search'}));
 const expected=await run(tab,()=>{const match=document.body.innerText.match(/(\d+)\s+Records Found/i);return match?Number(match[1]):null;});
 if(!Number.isInteger(expected)||expected<0)throw Error('IREPS catalogue count is unavailable. Collection stopped rather than claiming incomplete history.');
 const resume=job.action==='closed'&&job.resume?.expected===expected&&Array.isArray(job.resume?.visited)&&Array.isArray(job.resume?.records)?job.resume:null;
 if(resume){visited.push(...resume.visited);collected.push(...resume.records);}
 const completed=new Set(visited);
 for(let pn=1;pn<=1000;pn++){const list=await ids(tab),marker=list.join('|');if(!list.length){const count=await run(tab,()=>Number((document.body.innerText.match(/(\d+)\s+Records Found/i)||[])[1]||0));if(count>0)throw Error('IREPS shows catalogue records but no supported read-only catalogue links were found');break;}if(seen.has(marker))throw Error('IREPS pagination repeated a page. Collection stopped to avoid silently missing catalogues');seen.add(marker);
  for(const id of list){if((await api('status',{id:job.id})).cancelled)throw Error('Collection cancelled');if(completed.has(id))continue;await api('progress',{id:job.id,range,page:pn,current:id,visited,message:'Reading '+id+' ('+visited.length+' of '+expected+' checked)',complete:false});await openCatalogue(tab,id);const rows=await catalogue(tab);
   for(const x of rows){if(job.action==='scheduled'){if(/^RP\s*(Pending|yet to be fixed)$/i.test(x.status))collected.push({...x,status:'RP Pending'});}else if(job.metadata_only){collected.push({...x,outcome:x.status,date:x.start});}else if(!job.lots?.length||job.lots.includes(x.lot)){const outcome=/^Sold\b/i.test(x.status)?'Sold':/^Rejected\b/i.test(x.status)?'Rejected':/^No Bids\b/i.test(x.status)?'No Bids':/^Withdrawn\b/i.test(x.status)?'Withdrawn':null;if(outcome){const bid=outcome==='Sold'?await acceptedBid(tab,x.lot):{};collected.push({...x,...bid,outcome,date:x.start,awardee:''});}}}
   visited.push(id);completed.add(id);await api('progress',{id:job.id,range,page:pn,current:id,visited,rows:collected.length,checkpoint:job.action==='closed'&&visited.length%10===0?{expected,visited,records:collected}:undefined,message:visited.length+' catalogues checked; '+collected.length+' matching lots',complete:false});const backStamp=await stamp(tab);await chrome.tabs.goBack(tab);await ready(tab,backStamp);}
  const nextStamp=await stamp(tab);const next=await run(tab,n=>{const links=[...document.querySelectorAll('a')];const a=links.find(a=>{const match=(a.getAttribute('onclick')||'').match(/menuexpand\(\s*['"][^'"]+['"]\s*,\s*(\d+)\s*\)/);return match&&Number(match[1])===n;})||links.find(a=>a.innerText.trim()===String(n));if(!a)return false;a.click();return true;},[pn+1]);if(!next)break;if(pn===1000)throw Error('More than 1000 pages found. Remaining catalogues have not been checked.');await ready(tab,nextStamp);
 }if(Number.isInteger(expected)&&expected>=0&&new Set(visited).size!==expected)throw Error('Incomplete catalogue scan: checked '+new Set(visited).size+' of '+expected+'. Saved evidence is retained.');await api('progress',{id:job.id,range,visited,expected,rows:collected.length,message:'Collection finished: '+visited.length+' catalogues checked',complete:true});return collected;
}
async function discover(){
 let saved=await chrome.storage.local.get(['tab','token']),authenticated=false;
 if(saved.token){try{authenticated=(await api('state',{})).version==='1.4';}catch{}}
 if(!authenticated){
  if(Date.now()<nativeRetryAt)throw Error('Waiting for DeskFlow to open.');
  nativeRetryAt=Date.now()+15000;
  const pairing=await chrome.runtime.sendNativeMessage('com.deskflow.reader',{action:'get-session'});
  if(pairing.error||!pairing.token)throw Error(pairing.error||'Keep DeskFlow open to start automatically.');
  await chrome.storage.local.set({token:pairing.token});saved={...saved,token:pairing.token};nativeRetryAt=0;
 }
 const tabs=(await chrome.tabs.query({})).filter(t=>{try{const u=new URL(t.url);return u.protocol==='https:'&&['ireps.gov.in','www.ireps.gov.in'].includes(u.hostname);}catch{return false;}});
 const signed=[];for(const t of tabs){try{if(await run(t.id,()=>!!document.querySelector('a[href*="/logout.do"]')))signed.push(t);}catch{}}
 const selected=(signed.find(t=>t.id===saved.tab)||signed.find(t=>t.active)||signed.sort((a,b)=>(b.lastAccessed||0)-(a.lastAccessed||0))[0])?.id??null;
 if(selected===null){await api('disconnect',{});await chrome.storage.local.set({connectionStatus:'Sign in to IREPS'});return null;}
 await api('connect',{tab:selected});await chrome.storage.local.set({tab:selected,connectionStatus:'Connected automatically'});return selected;
}
async function poll(){if(busy)return;busy=true;let job;try{const tab=await discover();if(tab===null)return;job=await api('poll',{tab});if(!job.id)return;const rows=await execute(tab,job);await api('result',{id:job.id,rows});}catch(e){await chrome.storage.local.set({connectionStatus:e.message});if(job?.id)try{await api('result',{id:job.id,error:e.message});}catch{}}finally{busy=false;}}
chrome.runtime.onMessage.addListener((m,s,reply)=>{if(m.action==='start'){if(!timer)timer=setInterval(poll,1500);chrome.alarms.create('rp-poll',{periodInMinutes:.5});poll();reply({ok:true});}});chrome.alarms.onAlarm.addListener(()=>{if(!timer)timer=setInterval(poll,1500);poll();});
// Service-worker restart and browser restart both resume the saved pairing.
chrome.alarms.create('rp-poll',{periodInMinutes:.5});
if(!timer)timer=setInterval(poll,5000);
