import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=fs.readFileSync(new URL('./rp/reader.js',import.meta.url),'utf8');
async function scan(known={},fail=false){
  const sandbox={};vm.createContext(sandbox);
  vm.runInContext(source.slice(source.indexOf('async function run('),source.indexOf('async function discover(')),sandbox);
  const events=[];let current='',opened=[];
  Object.assign(sandbox,{
    folder:async()=>{},ready:async()=>{},stamp:async()=>0,ids:async()=>['A','B'],
    listingIdentity:async(_,id)=>({fingerprint:id+'-v1',date:'2023-01-01'}),
    openCatalogue:async(_,id)=>{current=id;opened.push(id);return {start:'01-01-23'};},
    catalogue:async()=>{if(fail&&current==='B')throw Error('Connection interrupted');return ['Sold','Rejected','No Bids','Withdrawn'].map((status,i)=>({catalogue:current,lot:current+'-'+i,start:'01-01-23',status,source:'IREPS'}));},
    acceptedBid:async()=>({bid_rate:123,bid_source:'IREPS viewer'}),
    api:async(path,data)=>{events.push({path,data:JSON.parse(JSON.stringify(data||{}))});return {cancelled:false};},
    run:async(_,fn)=>fn.toString().includes('Records Found')?2:false,
    chrome:{tabs:{goBack:async()=>{}}}
  });
  const job={id:'test',action:'closed',library:true,known_catalogues:known,refresh_after:'2026-09-28'};
  let result,error;try{result=await sandbox.execute(1,job);}catch(e){error=e;}
  return {result,error,events,opened};
}
let run=await scan();
assert.equal(run.result.length,8);
assert.deepEqual(run.events.filter(e=>e.path==='catalogue').map(e=>e.data.catalogue),['A','B']);
assert.equal(run.result[0].bid_rate,123);assert.equal(run.result[1].outcome,'Rejected');
run=await scan({'A':'A-v1'});
assert.deepEqual(run.opened,['B']);
assert.equal(run.events.filter(e=>e.path==='catalogue').length,1);
assert.equal(run.events.at(-1).data.visited.length,2);
run=await scan({},true);
assert.match(run.error.message,/interrupted/);
assert.equal(run.events.filter(e=>e.path==='catalogue').length,1,'First catalogue must be emitted before the second fails');
run=await scan({'A':'A-old'});assert.deepEqual(run.opened,['A','B'],'Changed listings must be rescanned');
console.log('Library reader passed: all outcomes, catalogue checkpoints, stable resume, changed-source refresh.');
