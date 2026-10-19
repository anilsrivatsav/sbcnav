import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source=fs.readFileSync(new URL('./rp/reader.js',import.meta.url),'utf8');
const sandbox={};vm.createContext(sandbox);
vm.runInContext(source.slice(source.indexOf('async function run('),source.indexOf('async function discover(')),sandbox);
let lists=0,bids=0;
Object.assign(sandbox,{
  folder:async()=>{},ready:async()=>{},stamp:async()=>0,
  ids:async()=>lists++===0?['C']:[],openCatalogue:async()=>{},
  catalogue:async()=>[
    {lot:'workbook-asset',start:'19/10/2026',status:'Sold',rate_unit:'Annual'},
    {lot:'second-asset',start:'19/10/2026',status:'Withdrawn',rate_unit:'Annual'},
  ],
  acceptedBid:async()=>{bids++;return {bid_rate:100};},
  api:async()=>({cancelled:false}),run:async()=>false,
  chrome:{tabs:{goBack:async()=>{}}},
});
const metadata=await sandbox.execute(1,{id:'metadata',action:'closed',metadata_only:true,lots:['different-active-lot']});
assert.equal(metadata.length,2,'Workbook scan must include assets outside the current pending list');
assert.equal(metadata[0].outcome,'Sold');
assert.equal(bids,0,'Workbook metadata scan must not open bid viewers or RP registers');
assert.equal(metadata[0].bid_rate,undefined);
lists=0;
const active=await sandbox.execute(1,{id:'active',action:'closed',lots:['workbook-asset']});
assert.equal(active.length,1);assert.equal(active[0].bid_rate,100);assert.equal(bids,1);
console.log('Workbook metadata collection and existing active-lot bid collection passed.');
