// Run the established read-only catalogue reader without a browser extension.
import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
// An all-status future scan must not inherit the preceding closed-auction dates.
if(input.job.all_scheduled){
  input.job.from_date ||= new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'});
  input.job.to_date ||= '2099-12-31';
}
const {chromium}=createRequire(import.meta.url)(input.playwright_module);
const browser=await chromium.connectOverCDP(input.endpoint);
const context=browser.contexts()[0], pages=new Map();let sequence=0;
const register=p=>{const id=++sequence;pages.set(id,p);return id;};
let page,lastReport={};
for(let attempt=0;attempt<12&&!page;attempt++){
 for(const candidate of context.pages()){
  if(!/^https:\/\/www\.ireps\.gov\.in\//.test(candidate.url()))continue;
  try{if(await candidate.evaluate(()=>window.name)===input.marker){page=candidate;break;}}
  catch(error){if(!/Execution context was destroyed|frame.*detached/i.test(error.message))throw error;}
 }
 if(!page)await new Promise(resolve=>setTimeout(resolve,250));
}
if(!page)throw Error('The signed-in collection page is no longer open.');
const tab=register(page);
function get(id){const p=pages.get(id);if(!p||!/^https:\/\/www\.ireps\.gov\.in\//.test(p.url()))throw Error('Only IREPS pages can be read.');return p;}
const chrome={scripting:{executeScript:async({target,func,args})=>[{result:await get(target.tabId).evaluate(`(${func.toString()})(...${JSON.stringify(args)})`)}]},tabs:{
  get:async id=>({id,url:get(id).url(),status:'complete',windowId:1}),
  create:async({url})=>{if(!/^https:\/\/www\.ireps\.gov\.in\//.test(url))throw Error('Unexpected bid source.');const p=await context.newPage();await p.goto(url);return{id:register(p)};},
  remove:async id=>{await get(id).close();pages.delete(id);},
  goBack:async id=>{await get(id).goBack({waitUntil:'load'});}
}};
let source=fs.readFileSync(new URL('./reader.js',import.meta.url),'utf8');
source=source.slice(source.indexOf('async function run('),source.indexOf('async function discover('));
const sandbox={chrome,setTimeout,URL,console,api:async(path,data)=>{if(path==='progress')lastReport=data;if(path==='progress')process.stdout.write(JSON.stringify({type:'progress',message:data.message,report:data,checkpoint:data.checkpoint})+'\n');if(path==='catalogue')process.stdout.write(JSON.stringify({type:'catalogue',...data})+'\n');return{cancelled:false};}};
vm.createContext(sandbox);vm.runInContext(source,sandbox);
// The IREPS viewer submits a form into a popup. A real locator click preserves
// that form submission; intercepting window.open loses its POST payload.
sandbox.acceptedBid=async(tab,lot)=>{
  const parent=get(tab),row=parent.locator('tr').filter({hasText:lot}).last();
  const valid=await row.evaluate((r,lot)=>r.children[1]?.innerText.split('(')[0].trim()===lot&&[...r.children].some(c=>/^Sold\b/i.test(c.innerText.trim())),lot);
  if(!valid)throw Error('The exact sold lot could not be verified.');
  const viewer=/^https:\/\/www\.ireps\.gov\.in\/epsn\/commAuction\/viewBiddingDetail\.do/;
  const before=new Map();
  for(const candidate of context.pages())if(viewer.test(candidate.url()))before.set(candidate,await candidate.evaluate(()=>performance.timeOrigin));
  const bidLink=row.locator('a[title="View Bid Details"]');
  const linkCount=await bidLink.count();
  if(linkCount===0)return {bid_details_unavailable:'IREPS catalogue shows Sold but exposes no bid-detail link. Verify the accepted rate and awardee separately.'};
  if(linkCount!==1)throw Error('The exact sold lot has ambiguous bid-detail links.');
  await bidLink.click();
  let popup;
  for(let n=0;n<120&&!popup;n++){
    for(const candidate of context.pages())if(viewer.test(candidate.url())){
      try{const info=await candidate.evaluate(()=>({stamp:performance.timeOrigin,ready:document.readyState==='complete'}));if(info.ready&&info.stamp!==before.get(candidate)){popup=candidate;break;}}catch{}
    }
    if(!popup)await new Promise(resolve=>setTimeout(resolve,250));
  }
  if(!popup)throw Error('The bid viewer did not load a fresh result. Close an old bid viewer and retry.');
  try{
    await popup.waitForLoadState('load');
    if(!/^https:\/\/www\.ireps\.gov\.in\/epsn\/commAuction\/viewBiddingDetail\.do/.test(popup.url()))throw Error('Unexpected bid viewer.');
    return await popup.evaluate(lot=>{
      if(document.querySelector('input[type="password"]'))throw Error('IREPS session expired. Sign in again before continuing.');
      if(![...document.querySelectorAll('select option:checked')].some(o=>o.textContent.trim()===lot))throw Error('Bid viewer belongs to another lot.');
      const rows=[...document.querySelectorAll('tr')].filter(r=>!r.querySelector('table'));
      const clean=value=>String(value||'').replace(/\s+/g,' ').trim();
      const header=rows.find(r=>[...r.cells].some(c=>/^Bid\s*Rate(?:\s*\(.*\))?$/i.test(clean(c.innerText))));
      if(!header)throw Error('Bid Rate column was not found.');
      const labels=[...header.cells].map(c=>clean(c.innerText)),ri=labels.findIndex(v=>/^Bid\s*Rate(?:\s*\(.*\))?$/i.test(v)),vi=labels.findIndex(v=>/^Bid\s*Value$/i.test(v));
      const bids=rows.filter(r=>r!==header&&r.cells.length===labels.length).map(r=>({bid_rate:Number(r.cells[ri].innerText.replace(/[₹,\s]/g,'')),bid_value:vi>=0?r.cells[vi].innerText.trim():'',bid_source:location.href})).filter(b=>Number.isFinite(b.bid_rate)&&b.bid_rate>0);
      if(!bids.length)throw Error('No positive bid rate was found.');
      const bid_rows=rows.filter(r=>r!==header&&r.cells.length===labels.length).map(r=>Object.fromEntries([...r.cells].map((cell,index)=>[labels[index],clean(cell.innerText)])));
      return {...bids.sort((a,b)=>b.bid_rate-a.bid_rate)[0],bid_rows,bid_rate_basis:'Highest displayed Bid Rate for an explicitly Sold lot; agreement LAR must be confirmed separately'};
    },lot);
  }catch(error){
    if(/Bid Rate column was not found|No positive bid rate was found/.test(error.message)){
      const raw=await popup.evaluate(()=>({bid_viewer_text:document.body.innerText,bid_viewer_rows:[...document.querySelectorAll('tr')].filter(r=>!r.querySelector('table')).map(r=>[...r.cells].map(c=>c.innerText.trim())),bid_captured_at:new Date().toISOString()}));
      return {...raw,bid_details_unavailable:'IREPS shows Sold; its bid viewer does not expose a readable accepted Bid Rate. Verify the rate and awardee separately.',bid_source:popup.url()};
    }
    throw error;
  }finally{if(!before.has(popup))await popup.close();}
};
try{const rows=await sandbox.execute(tab,input.job);
 if(input.job.all_scheduled){
  const scheduledReport={...lastReport};
  const folder_options=(await page.locator('#status option').allTextContents()).map(label=>label.trim());
  const additional_closed_folders=[];
  for(const label of folder_options.filter(label=>/^Closed Auctions\b/i.test(label)&&label!=='Closed Auctions (No Action Pending)')){
   const extra=await sandbox.execute(tab,{id:input.job.id+'-ended',action:'closed',folder_label:label,metadata_only:true,stable_ids:true,from_date:'2000-01-01',to_date:input.job.from_date});
   additional_closed_folders.push({folder:label,coverage:{...lastReport},rows:extra});
  }
  process.stdout.write(JSON.stringify({type:'progress',message:'Scheduled auctions and all listed closed-auction folders checked',report:{...scheduledReport,folder_options,additional_closed_folders}})+'\n');
 }
 process.stdout.write(JSON.stringify({type:'result',rows})+'\n');}
catch(error){process.stdout.write(JSON.stringify({type:'error',message:error.message.split('Call log:')[0].slice(0,1200)})+'\n');process.exitCode=1;}
finally{try{await browser.close();}catch{/* Collection result is already reported; a lost cleanup connection is harmless. */}}
