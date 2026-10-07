const HOME='https://www.ireps.gov.in/epsn/home/showHome.do';
const CATEGORIES=['Advertising','Misc-Static-Services','Misc-Mobile-Services','ATM/DBU/Banking e-Lobby','PMBJK','Parking','Hybrid NFR'];
let running=false;
const key=v=>String(v||'').replace(/\s+/g,'').toUpperCase();
function day(v) {
  if(typeof v==='number') return Math.round(v);
  const m=String(v).match(/^(\d{4})-(\d{2})-(\d{2})|^(\d{1,2})[/-](\d{1,2})[/-](\d{4})/);
  if(!m) throw new Error('IREPS returned an invalid date: '+v);
  return Math.round((Date.UTC(Number(m[1]||m[6]),Number(m[2]||m[5])-1,Number(m[3]||m[4]))-Date.UTC(1899,11,30))/86400000);
}
function relevant(v) {const s=key(v);return s.startsWith('PARKING')?s.includes('RADIOTAXI'):['ADVERTISING','MISC-STATIC','MISC-MOBILE','ATM','PMBJK','HYBRIDNFR'].some(p=>s.startsWith(p));}
async function irepsTab(open=false) {
  const tabs=await chrome.tabs.query({url:'https://www.ireps.gov.in/*'});
  if(tabs.length) {if(open)await chrome.tabs.update(tabs[0].id,{active:true});return tabs[0].id;}
  if(!open)throw new Error('Open IREPS and complete digital-token sign-in first.');
  return (await chrome.tabs.create({url:HOME,active:true})).id;
}
async function read(tab, func, args=[]) {
  const target=await chrome.tabs.get(tab);
  if(new URL(target.url).origin!=='https://www.ireps.gov.in')throw new Error('IREPS navigated outside its approved origin.');
  const result=await chrome.scripting.executeScript({target:{tabId:tab},world:'MAIN',func,args});
  if(result[0].result?.error)throw new Error(result[0].result.error);
  return result[0].result;
}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function loaded(tab, previous=null) {
  for(let i=0;i<120;i++) {
    try {
      const state=await read(tab,()=>({ready:document.readyState,stamp:performance.timeOrigin,body:document.body?.innerText||''}));
      if(state.ready==='complete' && (previous===null||state.stamp!==previous)) {
        if(/Your session has expired/.test(state.body))throw new Error('IREPS session expired. Sign in and start a fresh check.');
        return state;
      }
    } catch(e) {if(/session expired|approved origin/.test(e.message))throw e;}
    await pause(500);
  }
  throw new Error('IREPS page did not finish loading; no sheet changes were made.');
}
async function click(tab,label) {
  const stamp=await read(tab, label=>{
    const matches=[...document.querySelectorAll('a,button,input[type=button],input[type=submit]')].filter(e=>e.getClientRects().length&&(e.innerText||e.value||'').trim()===label);
    if(matches.length!==1)return {error:'Expected one IREPS '+label+' control; found '+matches.length};
    const stamp=performance.timeOrigin;matches[0].click();return stamp;
  },[label]);
  return loaded(tab,stamp);
}
async function navigate(tab,mode) {
  await chrome.tabs.update(tab,{url:HOME});await loaded(tab);
  const authenticated=await read(tab,()=>[...document.querySelectorAll('a')].some(a=>a.innerText.trim()==='Payments'));
  if(!authenticated)throw new Error('Complete IREPS digital-token sign-in, then click Check IREPS.');
  await click(tab,mode);
  await click(tab,mode==='Payments'?'Payments Received':'View Contracts');
}
async function search(tab,category,kind,start,end,contract='') {
  const stamp=await read(tab,(category,kind,start,end,contract)=>{
    const select=(id,label)=>{
      const e=document.getElementById(id);const opt=e&&[...e.options].find(o=>o.text.trim()===label);
      if(!opt)throw new Error('IREPS '+id+' option missing: '+label);
      e.value=opt.value;e.dispatchEvent(new Event('change',{bubbles:true}));
    };
    try {
      select('regCat',category);select('regSubCat','---All---');select(kind?'status':'tdStatus',kind||'All');
      for(const [id,value] of [['tenderNumber',contract],['bidderName',''],['ddmmyyDateformat1',start],['ddmmyyDateformat2',end]]) {
        if(value===null)continue;const el=document.getElementById(id);
        if(!el)throw new Error('IREPS field missing: '+id);el.value=value;el.dispatchEvent(new Event('change',{bubbles:true}));
      }
      const buttons=[...document.querySelectorAll('button,input[type=submit],input[type=button]')].filter(e=>(e.innerText||e.value||'').trim()==='Search');
      if(buttons.length!==1)throw new Error('IREPS Search control changed.');
      const stamp=performance.timeOrigin;buttons[0].click();return stamp;
    }catch(e){return {error:e.message};}
  },[category,kind,start,end,contract]);
  await loaded(tab,stamp);
  if(start!==null) {
    const filters=await read(tab,()=>['ddmmyyDateformat1','ddmmyyDateformat2'].map(id=>document.getElementById(id)?.value));
    if(filters[0]!==start||filters[1]!==end)throw new Error('IREPS changed the requested dates.');
  }
}
async function allRows(tab,mode,warnings) {
  const first=await read(tab,()=>document.body.innerText.match(/(\d+)\s*Records Found/)?.[1]);
  if(first===undefined)throw new Error('IREPS result count missing.');
  const total=Number(first),rows=[],seen=new Set();let page=1;
  while(true) {
    const batch=await read(tab,mode=>{
      let result=[];
      for(const table of document.querySelectorAll('table')) {
        const wanted=mode==='paid'?'Payment date':'Contract No';
        const header=[...table.rows].find(r=>[...r.cells].some(c=>[wanted,wanted+'.'].includes(c.innerText.trim())));
        if(!header)continue;
        const matched=[...table.rows].filter(r=>r!==header&&r.cells.length===(mode==='failed'?8:9)&&(mode!=='paid'||/^\d{4}-\d{2}-\d{2}/.test(r.cells[0]?.innerText.trim())));
        if(matched.length)result=matched.map(r=>({cells:[...r.cells].map(c=>c.innerText.trim()),links:[...r.querySelectorAll('a')].map(a=>({text:a.innerText.trim(),onclick:a.getAttribute('onclick'),href:a.getAttribute('href')}))}));
      }
      return result;
    },[mode]);
    const signature=JSON.stringify(batch);if(seen.has(signature))throw new Error('IREPS repeated a result page.');seen.add(signature);rows.push(...batch);
    if(rows.length===total)return rows;
    if(rows.length>total)throw new Error('IREPS result count changed during the scan.');
    const stamp=await read(tab,next=>{
      const pages=[...document.querySelectorAll('a[onclick*="menuexpand("]')];
      let links=pages.filter(a=>a.innerText.trim()===String(next));if(links.length!==1)links=pages.filter(a=>/^next$/i.test(a.innerText.trim()));
      if(links.length!==1)return null;
      const stamp=performance.timeOrigin;links[0].click();return stamp;
    },[page+1]);
    if(stamp===null) {
      if(mode==='contracts' && page===Math.max(1,Math.ceil(total/10)) && total-rows.length>0 && total-rows.length<10) {
        warnings.push(`IREPS displays ${total} contracts but all visible pages contain ${rows.length}; only listed contracts will be updated.`);return rows;
      }
      throw new Error(`IREPS pagination stopped at ${rows.length} of ${total}.`);
    }
    page++;await loaded(tab,stamp);
  }
}
async function pdf(tab,url) {
  if(new URL(url).origin!=='https://www.ireps.gov.in'||!url.toLowerCase().endsWith('.pdf'))throw new Error('Unexpected invoice PDF destination.');
  return read(tab,async url=>{
    try {
      const response=await fetch(url,{credentials:'include',signal:AbortSignal.timeout(60000)});
      if(!response.ok)throw new Error('Invoice download failed.');
      const bytes=new Uint8Array(await response.arrayBuffer());
      if(bytes.length>8*1024*1024||String.fromCharCode(...bytes.slice(0,4))!=='%PDF')throw new Error('Invalid invoice PDF.');
      let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(binary);
    }catch(e){return {error:e.message};}
  },[url]);
}
async function terms(tab,contract,end) {
  await navigate(tab,'Contracts');await search(tab,'---All---',null,'01/01/2020',end,contract);
  const rows=await allRows(tab,'contracts',[]);
  if(rows.length!==1||key(rows[0].cells[0])!==key(contract))throw new Error('Exact contract agreement lookup did not match '+contract);
  await click(tab,'Contract');
  const text=await read(tab,()=>document.body.innerText);
  const existing=new Set((await chrome.tabs.query({})).map(t=>t.id));
  await read(tab,()=>{
    const buttons=[...document.querySelectorAll('button,input[type=button],input[type=submit]')].filter(e=>(e.innerText||e.value||'').trim()==='Payment Schedule');
    if(buttons.length!==1)return {error:'Payment Schedule button missing.'};buttons[0].click();return true;
  });
  let popup;
  for(let i=0;i<60&&!popup;i++) {popup=(await chrome.tabs.query({url:'https://www.ireps.gov.in/*'})).find(t=>!existing.has(t.id)&&t.openerTabId===tab);if(!popup)await pause(500);}
  if(!popup)throw new Error('IREPS payment schedule did not open. Allow the IREPS popup and retry.');
  try {
    await loaded(popup.id);
    const schedule=await read(popup.id,contract=>{
      if(!document.body.innerText.includes(contract))return {error:'Wrong IREPS payment schedule.'};
      return [...document.querySelectorAll('tr[id^="row-"]')].map(r=>[...r.cells].map(c=>c.innerText.trim()));
    },[contract]);
    if(!schedule.length)throw new Error('IREPS payment schedule is empty.');return {text,schedule};
  } finally {await chrome.tabs.remove(popup.id);}
}
async function collect(tab,config,notify) {
  const {start,end}=config;if(!/\d{2}\/\d{2}\/\d{4}/.test(start)||!/^\d{2}\/\d{2}\/\d{4}$/.test(end))throw new Error('Invalid sync date range.');
  const evidence={run_id:config.run_id,start,end,completed_categories:[],contracts:[],payments:[],failures:[],terms:{},pdfs:{},warnings:[]};
  const existing=new Set(config.existing_invoices||[]),wanted=new Set(),known=config.known_due||{};
  await navigate(tab,'Contracts');
  for(const cat of CATEGORIES) {
    notify('Checking official contract status: '+cat);
    await search(tab,cat,null,'01/01/2020',end);
    for(const {cells:c} of await allRows(tab,'contracts',evidence.warnings))if(relevant(c[3]))evidence.contracts.push({contract:c[0],contract_date:c[1],firm:c[2],category:c[3],asset:c[4],start:c[5],end:c[6],status:c[7]});
  }
  await navigate(tab,'Payments');
  for(const cat of CATEGORIES) {
    notify('Reading collected payments: '+cat);
    await search(tab,cat,'Previous Payments Made','01/01/1900','31/12/2099');
    for(const row of await allRows(tab,'paid',evidence.warnings)) {
      const c=row.cells;if(!relevant(c[4]))continue;
      const links=row.links.filter(a=>/^ES\w+$/.test(a.text));
      if(links.length!==1)throw new Error('Missing unique invoice link.');
      const path=links[0].onclick?.match(/window\.open\(\s*['"]([^'"]+)/)?.[1];
      if(!path)throw new Error('IREPS invoice link format changed.');
      const item={invoice:links[0].text,url:new URL(path,HOME).href,paid:c[0],total:Number(c[1].replaceAll(',','')),contract:c[2],contract_date:c[3],category:c[4],asset:c[5],firm:c[6],due:c[7]};
      if(!Number.isFinite(item.total))throw new Error('IREPS collection amount is invalid.');
      evidence.payments.push(item);
      const inRange=day(start)<=day(item.paid)&&day(item.paid)<=day(end);
      const dueSettled=known[key(item.contract)]!==undefined&&day(known[key(item.contract)])===day(item.due)&&item.total>0;
      if(inRange&&(!existing.has(item.invoice)||dueSettled)) {
        notify('Verifying invoice '+item.invoice);evidence.pdfs[item.invoice]=await pdf(tab,item.url);wanted.add(item.contract);
      }
      if(dueSettled)wanted.add(item.contract);
    }
    notify('Checking overdue payment failures: '+cat);
    await search(tab,cat,'Payment Failures (Beyond grace period)',null,null);
    for(const {cells:c} of await allRows(tab,'failed',evidence.warnings))if(relevant(c[2]))evidence.failures.push({contract:c[0],category:c[2],amount:c[5],due:c[6],status:'Payment failed / beyond grace period'});
    evidence.completed_categories.push(cat);
  }
  for(const contract of wanted) {notify('Verifying agreement and schedule: '+contract);evidence.terms[key(contract)]=await terms(tab,contract,end);}
  return evidence;
}
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  const origin=sender.url&&new URL(sender.url).origin;
  if(origin!=='https://sbcnav-38t2.vercel.app')return;
  if(message.action==='ping') {reply({ready:true,version:'1.0.0',running});return;}
  if(message.action==='open') {irepsTab(true).then(()=>reply({opened:true}),e=>reply({error:e.message}));return true;}
  if(message.action!=='collect')return;
  if(running) {reply({error:'An IREPS check is already running in this browser.'});return;}
  running=true;reply({started:true});
  const notify=progress=>chrome.tabs.sendMessage(sender.tab.id,{channel:'sbcnav-mcdo-response',nonce:message.nonce,progress}).catch(()=>{});
  irepsTab().then(tab=>collect(tab,message.config,notify)).then(evidence=>chrome.tabs.sendMessage(sender.tab.id,{channel:'sbcnav-mcdo-response',nonce:message.nonce,evidence})).catch(error=>chrome.tabs.sendMessage(sender.tab.id,{channel:'sbcnav-mcdo-response',nonce:message.nonce,error:error.message})).finally(()=>{running=false;});
});
