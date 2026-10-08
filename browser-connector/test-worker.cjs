const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const test=require('node:test');
function worker(pages,controls=[],tabs=[]) {
  let page=0,stamp=1;
  const context={URL,AbortSignal,Uint8Array,Set,Map,console,setTimeout,clearTimeout,setInterval,clearInterval,chrome:{runtime:{onMessage:{addListener(){}}},tabs:{async get(){return {url:'https://www.ireps.gov.in/epsn/home/showHome.do'};}},scripting:{async executeScript({func,args}){return [{result:await func(...args)}];}}}};
  context.performance={get timeOrigin(){return stamp;}};
  context.chrome.tabs.query=async()=>tabs;
  context.chrome.tabs.create=async()=>({id:999});
  context.chrome.tabs.update=async id=>({id});
  const cell=t=>({innerText:t});
  for(const control of controls){control.getAttribute??=()=>null;control.querySelectorAll??=()=>[];}
  context.document={readyState:'complete',getElementById(){return null;},body:{get innerText(){return `${pages[page].total} Records Found`;}},querySelectorAll(selector){
    if(selector==='a,button,input[type=button],input[type=submit]')return controls;
    if(selector==='table')return [{rows:[{cells:[cell('Contract No'),...Array.from({length:8},()=>cell(''))]},...pages[page].rows.map(cells=>({cells:cells.map(cell),querySelectorAll(){return [];}}))]}];
    if(selector.startsWith('a[onclick'))return page+1<pages.length?[{innerText:String(page+2),click(){page++;stamp++;}}]:[];
    return [];
  }};
  vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/worker.js','utf8'),context);
  return vm.runInContext('({allRows,relevant,day,pdf,click,irepsTab,scanCheckpoint,setScan(value){scan=value;}})',context);
}
const contract=n=>['SBC-'+n,'01/01/2026','Firm','Advertising','SBC','01/01/2026','31/12/2026','Running',''];

test('paused scan blocks at checkpoint until explicitly resumed',async()=>{
  const w=worker([{total:0,rows:[]}]);const notices=[];
  const scan={pauseRequested:true,notify:data=>notices.push(data),resume:null};w.setScan(scan);
  let continued=false;const waiting=w.scanCheckpoint().then(()=>{continued=true;});
  await new Promise(resolve=>setTimeout(resolve,10));
  assert.equal(continued,false);assert.equal(notices[0].paused,true);
  scan.pauseRequested=false;scan.resume();await waiting;assert.equal(continued,true);
});

test('never reuses an unrelated IREPS tender draft tab',async()=>{
  const w=worker([{total:0,rows:[]}],[],[{id:42,url:'https://www.ireps.gov.in/epsn/works/rfq/nitPublish.do'}]);
  assert.equal(await w.irepsTab(true),999);
});

test('reuses the lease-auction home rather than a tender draft',async()=>{
  const w=worker([{total:0,rows:[]}],[],[{id:42,url:'https://www.ireps.gov.in/epsn/works/rfq/nitPublish.do'},{id:43,url:'https://www.ireps.gov.in/epsn/home/showHome.do'}]);
  assert.equal(await w.irepsTab(true),43);
});
test('reads every contract page',async()=>{
  const w=worker([{total:12,rows:Array.from({length:10},(_,n)=>contract(n))},{total:12,rows:[contract(10),contract(11)]}]);
  assert.equal((await w.allRows(1,'contracts',[])).length,12);
});
test('rejects repeated pages before evidence submission',async()=>{
  const rows=Array.from({length:10},(_,n)=>contract(n));
  const w=worker([{total:20,rows},{total:20,rows}]);
  await assert.rejects(()=>w.allRows(1,'contracts',[]),/repeated/);
});
test('records the known contract count discrepancy without inventing contracts',async()=>{
  const warnings=[];const w=worker([{total:8,rows:[contract(1),contract(2),contract(3),contract(4),contract(5)]}]);
  assert.equal((await w.allRows(1,'contracts',warnings)).length,5);assert.equal(warnings.length,1);
});
test('rejects incomplete payment counts',async()=>{
  const w=worker([{total:12,rows:[contract(1)]}]);await assert.rejects(()=>w.allRows(1,'failed',[]),/pagination stopped/);
});
test('excludes ordinary parking and accepts Radio Taxi',()=>{
  const w=worker([{total:0,rows:[]}]);assert.equal(w.relevant('Parking - car park'),false);assert.equal(w.relevant('Parking - Radio Taxi'),true);
  assert.equal(w.day('06/10/2026'),46301);assert.equal(w.day('2026-10-06 14:10:00'),46301);
});
test('never fetches invoice PDFs from another origin',async()=>{
  const w=worker([{total:0,rows:[]}]);await assert.rejects(()=>w.pdf(1,'https://example.com/invoice.pdf'),/Unexpected/);
});

test('waits for a same-document Contracts submenu without requiring a reload',async()=>{
  let visible=false;
  const controls=[
    {innerText:'Contracts',getClientRects:()=>[{}],click(){visible=true;}},
    {innerText:'View Contracts',getClientRects:()=>visible?[{}]:[]}
  ];
  await worker([{total:0,rows:[]}],controls).click(1,'Contracts','View Contracts');
  assert.equal(visible,true);
});

test('opens an icon-only Contract action and excludes Modify Contract',async()=>{
  let selected='';
  const action=name=>({innerText:'',getClientRects:()=>[{}],querySelectorAll:()=>[{getAttribute:attr=>attr==='alt'?name:null}],click(){selected=name;}});
  const controls=[action('Contract'),action('Modify Contract'),{innerText:'View Contracts',getClientRects:()=>[{}]}];
  await worker([{total:0,rows:[]}],controls).click(1,'Contract','View Contracts');
  assert.equal(selected,'Contract');
});
