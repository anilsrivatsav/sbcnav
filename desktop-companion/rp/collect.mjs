// Run the established read-only catalogue reader without a browser extension.
import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const {chromium}=createRequire(input.modules+'/package.json')('playwright');
const browser=await chromium.connectOverCDP(input.endpoint);
const context=browser.contexts()[0], pages=new Map();let sequence=0;
const register=p=>{const id=++sequence;pages.set(id,p);return id;};
let page;
for(const candidate of context.pages())if(/^https:\/\/www\.ireps\.gov\.in\//.test(candidate.url())&&await candidate.evaluate(()=>window.name)===input.marker){page=candidate;break;}
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
const sandbox={chrome,setTimeout,URL,console,api:async(path,data)=>{if(path==='progress')process.stdout.write(JSON.stringify({type:'progress',message:data.message})+'\n');return{cancelled:false};}};
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
  await row.getByRole('link',{name:/^[1-9]\d*$/}).click();
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
      if(![...document.querySelectorAll('select option:checked')].some(o=>o.textContent.trim()===lot))throw Error('Bid viewer belongs to another lot.');
      const rows=[...document.querySelectorAll('tr')].filter(r=>!r.querySelector('table'));
      const header=rows.find(r=>[...r.cells].some(c=>c.innerText.trim()==='Bid Rate'));
      if(!header)throw Error('Bid Rate column was not found.');
      const labels=[...header.cells].map(c=>c.innerText.trim()),ri=labels.indexOf('Bid Rate'),vi=labels.indexOf('Bid Value');
      if(vi<0)throw Error('Bid Value column was not found.');
      const bids=rows.filter(r=>r!==header&&r.cells.length===labels.length).map(r=>({bid_rate:Number(r.cells[ri].innerText.replace(/[₹,\s]/g,'')),bid_value:r.cells[vi].innerText.trim(),bid_source:location.href})).filter(b=>Number.isFinite(b.bid_rate)&&b.bid_rate>0);
      if(!bids.length)throw Error('No positive bid rate was found.');
      return bids.sort((a,b)=>b.bid_rate-a.bid_rate)[0];
    },lot);
  }finally{if(!before.has(popup))await popup.close();}
};
try{const rows=await sandbox.execute(tab,input.job);process.stdout.write(JSON.stringify({type:'result',rows})+'\n');}
catch(error){process.stdout.write(JSON.stringify({type:'error',message:error.message.split('Call log:')[0].slice(0,1200)})+'\n');process.exitCode=1;}
finally{await browser.close();}
