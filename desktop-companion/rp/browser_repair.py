"""Explicit repair of stalled read-only catalogue-list tabs in the app profile."""
import json
from pathlib import Path
from urllib.parse import quote,urlparse
from urllib.request import Request,urlopen

def repair_catalogue_tabs(state_dir,opener=urlopen):
    port=int(json.loads((Path(state_dir)/'browser.json').read_text())['port'])
    if not 1<=port<=65535:raise ValueError('Invalid app browser port.')
    endpoint=f'http://127.0.0.1:{port}'
    with opener(endpoint+'/json/list',timeout=8) as response:targets=json.load(response)
    def listing(target):
        parsed=urlparse(target.get('url',''))
        return target.get('type')=='page' and parsed.scheme=='https' and parsed.hostname in ('ireps.gov.in','www.ireps.gov.in') and parsed.path=='/epsn/laBuyerInboxLink.do' and target.get('title','').strip()=='Folder Details'
    selected=[target for target in targets if listing(target)]
    if not selected:return {'closed':0,'message':'No stale read-only catalogue-list tabs found.'}
    remaining=[target for target in targets if target.get('type')=='page' and not listing(target)]
    if not remaining:
        with opener(Request(endpoint+'/json/new?about:blank',method='PUT'),timeout=8) as response:remaining=[json.load(response)]
    for target in selected:
        with opener(endpoint+'/json/close/'+quote(str(target['id']),safe=''),timeout=8) as response:response.read()
    neutral=next((t for t in remaining if t.get('url','')=='about:blank' or urlparse(t.get('url','')).hostname in ('myaccount.google.com','accounts.google.com')),None)
    if neutral:
        with opener(endpoint+'/json/activate/'+quote(str(neutral['id']),safe=''),timeout=8) as response:response.read()
    return {'closed':len(selected),'message':f"Cleared {len(selected)} stalled read-only catalogue-list tabs. The app browser profile is retained."}
