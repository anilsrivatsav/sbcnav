const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const test=require('node:test');
function worker(pages) {
  let page=0,stamp=1;
  const context={URL,AbortSignal,Uint8Array,Set,Map,console,setTimeout,clearTimeout,chrome:{runtime:{onMessage:{addListener(){}}},tabs:{async get(){return {url:'https://www.ireps.gov.in/epsn/home/showHome.do'};}},scripting:{async executeScript({func,args}){return [{result:await func(...args)}];}}}};
  context.performance={get timeOrigin(){return stamp;}};
  const cell=t=>({innerText:t});
  context.document={readyState:'complete',body:{get innerText(){return `${pages[page].total} Records Found`;}},querySelectorAll(selector){
    if(selector==='table')return [{rows:[{cells:[cell('Contract No'),...Array.from({length:8},()=>cell(''))]},...pages[page].rows.map(cells=>({cells:cells.map(cell),querySelectorAll(){return [];}}))]}];
    if(selector.startsWith('a[onclick'))return page+1<pages.length?[{innerText:String(page+2),click(){page++;stamp++;}}]:[];
    return [];
  }};
  vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/worker.js','utf8'),context);
  return vm.runInContext('({allRows,relevant,day,pdf})',context);
}
const contract=n=>['SBC-'+n,'01/01/2026','Firm','Advertising','SBC','01/01/2026','31/12/2026','Running',''];
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
