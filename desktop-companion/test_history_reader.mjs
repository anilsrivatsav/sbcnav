import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source=fs.readFileSync(new URL('./rp/reader.js',import.meta.url),'utf8');
async function scan(expected=11, last=11) {
  let page=1; const progress=[];
  const sandbox={}; vm.createContext(sandbox);
  vm.runInContext(source.slice(source.indexOf('async function run('),source.indexOf('async function discover(')),sandbox);
  Object.assign(sandbox,{
    folder:async()=>{}, ready:async()=>{}, stamp:async()=>0,
    ids:async()=>['C'+page], openCatalogue:async()=>{},
    catalogue:async()=>[{lot:'L',start:'01/10/2026',status:'No Bids'}],
    api:async(path,data)=>{if(path==='progress')progress.push(data);return {cancelled:false};},
    chrome:{tabs:{goBack:async()=>{}}},
    run:async(tab,fn,args=[])=>{
      if(fn.toString().includes('Records Found'))return expected;
      if(fn.toString().includes('querySelectorAll')){
        sandbox.document={querySelectorAll:()=>page<last?[{
          innerText:page===10?'next':String(page+1),
          getAttribute:()=>`return menuexpand('ClosedCatalogues',${page+1})`,
          click:()=>{page++;},
        }]:[]};
        return fn(...args);
      }
      return {from:'01/01/2023',to:'27/10/2026'};
    },
  });
  const rows=await sandbox.execute(1,{id:'test',action:'closed',lots:['L']});
  return {rows,progress};
}
const result=await scan();
assert.equal(result.rows.length,11,'Must follow the next link after the first ten pages');
assert.equal(result.progress.at(-1).visited.length,11);
assert.equal(result.progress.at(-1).expected,11);
await assert.rejects(()=>scan(12,11),/Incomplete catalogue scan/);

const collect=fs.readFileSync(new URL('./rp/collect.mjs',import.meta.url),'utf8');
let clicked=false;
const row={evaluate:async()=>true,locator:()=>({count:async()=>0,click:async()=>{clicked=true;}})};
const parent={locator:()=>({filter:()=>({last:()=>row})})};
const fixture={sandbox:{},get:()=>parent,context:{pages:()=>[]}};
vm.createContext(fixture);
vm.runInContext(collect.slice(collect.indexOf('sandbox.acceptedBid='),collect.indexOf('\ntry{const rows=')),fixture);
const bid=await fixture.sandbox.acceptedBid(1,'L');
assert.match(bid.bid_details_unavailable,/no bid-detail link/);
assert.equal(bid.bid_rate,undefined);
assert.equal(clicked,false,'Missing viewer must not cause a lot-entry fallback');
console.log('History regression checks passed: next link, incomplete count, missing sold viewer.');
