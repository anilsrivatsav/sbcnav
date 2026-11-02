import assert from 'node:assert/strict';
import {allowedTarget as allowed} from './rp/ireps_cdp_policy.mjs';
assert(allowed({type:'page',url:'https://www.ireps.gov.in/epsn/home/showHome.do'}));
assert(allowed({type:'page',url:'https://ireps.gov.in/epsn/commAuction/contractAgreement.do'}));
assert(allowed({type:'page',url:'about:blank'}));
assert(allowed({type:'worker',url:''}));
for(const url of ['chrome://downloads/','https://cloud.oracle.com/','https://www.ireps.gov.in.evil.example/','https://www.ireps.gov.in@evil.example/','http://www.ireps.gov.in/','https://www.canva.com/'])assert.equal(allowed({type:'page',url}),false,url);
assert.equal(allowed({type:'background_page',url:''}),false);
console.log('PASS: IREPS and owned blank reader pages are accepted; unrelated and deceptive hosts are excluded.');
