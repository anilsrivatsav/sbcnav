import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const source=fs.readFileSync(new URL('./rp/reader.js',import.meta.url),'utf8');
async function runJob(job){
 const sandbox={};vm.createContext(sandbox);vm.runInContext(source.slice(source.indexOf('async function run('),source.indexOf('async function discover(')),sandbox);
 const bids=[];const events=[];
 Object.assign(sandbox,{folder:async()=>{},ready:async()=>{},stamp:async()=>0,ids:async()=>[{catalogue:'CAT',id:'ireps:1'}],
 listingIdentity:async()=>({fingerprint:'fp',date:'2026-10-01'}),openCatalogue:async()=>({start:'01-10-26'}),
 catalogue:async()=>[{catalogue:'CAT',lot:'1',category:'Parking - Mixed',status:'Sold',start:'01-10-26'},
 {catalogue:'CAT',lot:'2',category:'Misc-Static-Services - Nursing pods',status:'Sold',start:'01-10-26'},
 {catalogue:'CAT',lot:'3',category:'Parking - Mixed',status:'RP Pending',start:'01-10-26'}],
 acceptedBid:async(_,lot)=>{bids.push(lot);return {bid_rate:100}},api:async(path,data)=>{events.push({path,data});return {cancelled:false}},
 run:async(_,fn)=>fn.toString().includes('Records Found')?1:false,chrome:{tabs:{goBack:async()=>{}}}});
 const rows=await sandbox.execute(1,{id:'fixture',...job});return {rows,bids,events};
}
const scoped=await runJob({action:'closed',library:true,known_catalogues:{},detail_categories:['Parking - Mixed']});
assert.deepEqual(scoped.bids,['1']);assert.equal(scoped.rows.length,3);
assert.equal(scoped.rows.find(r=>r.lot==='2').bid_details_pending,true);
const all=await runJob({action:'scheduled',all_scheduled:true,stable_ids:true});assert.equal(all.rows.length,3);
assert.equal(all.rows[0].status,'Sold');assert.deepEqual(all.bids,[]);
const normal=await runJob({action:'scheduled'});assert.equal(normal.rows.length,1);assert.equal(normal.rows[0].status,'RP Pending');
console.log('PASS: direct bid scope excludes unrelated categories; full scheduled statuses retained; existing RP-only collection unchanged.');
