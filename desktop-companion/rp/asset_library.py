"""Compact, source-separated asset evidence for the search panel.

This is a read model, never a pricing authority or workbook writer. Codes group
records for inspection; area/compartment differences remain explicit variants.
"""
import base64,hashlib,json,re,zlib,time
from pathlib import Path
from .history_library import day
from .direct_evidence import in_scope
from .identifiers import references

VERSION=3
def code(value):return re.sub(r'[^A-Z0-9]','',str(value or '').upper())
def identity(lot,description,category=''):
    text=str(description or '').upper();label=str(lot or '').upper()
    areas=sorted({float(n.replace(',','')) for n in re.findall(r'(\d[\d,]*(?:\.\d+)?)\s*(?:SQ\.?\s*M(?:T(?:R)?)?S?\.?|SQUARE\s*MET(?:ER|RE)S?|M[²2])\b',text)})
    named=set(re.findall(r'\b(?:FSLR|RSLR|VP)\b',text+' '+label))
    if re.search(r'SLR[- ]F\d',label):named.add('FSLR')
    if re.search(r'SLR[- ]R\d',label):named.add('RSLR')
    if re.search(r'\bVP\d*\b',label):named.add('VP')
    train=re.search(r'(?<!\d)[1-9]\d{4}(?!\d)',label+' '+text)
    station=references({'lot':lot}).get('station','')
    parking=bool(re.search(r'\b(?:PARKING|PRK)\b',text+' '+label+' '+str(category).upper()))
    return {'areas':areas,'parcel_types':sorted(named),'train':train[0] if train else '','station':station,'parking':parking,
            'scope_conflict':len(named)>1,'description':description or ''}

def workbook_record(row):
    cells=row['cells'];book=row['book'];sheet=row['sheet']
    def at(c):return cells.get(c,{}).get('value','')
    date=cells.get('A',{}).get('date') or day(at('A'))
    if not date:return None
    if book=='commercial':
        if sheet not in ('Table1','29.12.23'):return None
        modern=sheet=='Table1'
        lot=at('L') if modern else at('C')
        desc=at('D');cat=at('B');value='E' if modern else 'H';note='F' if modern else 'I';catalogue=at('N') if modern else ''
        unit=at('G') if modern else ''
    elif book=='parcel' and sheet=='Sheet1 (2)':
        lot=at('Q') or at('F') or at('C');desc=at('V') or at('F') or at('C');cat=at('W') or 'Parcel';value='M';note='P';catalogue=at('R');unit=at('S')
    elif book=='catering' and sheet=='Sheet1':
        lot=at('N') or ' '.join(str(at(c)) for c in ('D','C'));desc=at('I') or at('C');cat=at('U') or at('F');value='L';note='M';catalogue=at('P');unit=at('Q')
    else:return None
    if not code(lot):return None
    raw=at(value)
    try:amount=float(str(raw).replace(',','')) if raw not in ('',None) else None
    except ValueError:amount=None
    return {'id':f"{book}:{sheet}:{row['row']}",'lot':str(lot),'date':date[:10],'description':str(desc),
            'category':str(cat),'catalogue':str(catalogue),'rate_unit':str(unit),'value':amount,
            'justification':str(at(note)),'formula':cells.get(value,{}).get('formula',''),
            'file':Path(row['file']).name,'sheet':sheet,'row':row['row'],'cell':f"{value}{row['row']}"}

def build(store):
    with store.connect() as c:
        events=[json.loads(r[0]) for r in c.execute('SELECT data FROM df_auctions WHERE active=1')]
        raw_workbooks=[json.loads(r[0]) for r in c.execute('SELECT r.data FROM df_workbook_rows r JOIN df_workbooks w ON w.book=r.book AND w.revision=r.revision WHERE w.active=1')]
        workbooks=[workbook_record(r) for r in raw_workbooks]
        saved=[json.loads(r[0]) for r in c.execute('SELECT data FROM df_direct_contract_details')]
        reviewed=[(key,json.loads(raw)) for key,raw in c.execute("SELECT lot_id,data FROM evidence WHERE kind='contract'")]
    assets={}
    def asset(lot,description='',category=''):
        key=code(lot)
        if key not in assets:assets[key]={'id':key,'lot':lot,'description':description,'category':category,'events':[],'workings':[],'contracts':[],'scheduled':[],'references':[]}
        return assets[key]
    keep=('date','lot','catalogue','description','category','outcome','bid_rate','bid_value','rate_unit','awardee','bid_source','source','bid_rate_basis','bid_details_unavailable')
    for row in events:
        if not in_scope(row.get('category')):continue
        item={k:row[k] for k in keep if k in row};item['scope']=identity(row['lot'],row.get('description'),row.get('category'))
        asset(row['lot'],row.get('description',''),row.get('category',''))['events'].append(item)
    for row in workbooks:
        if row:
            row['scope']=identity(row['lot'],row['description'],row['category'])
            asset(row['lot'],row['description'],row['category'])['workings'].append(row)
    for raw,normalized in zip(raw_workbooks,workbooks):
        if normalized:continue
        if (raw['book']=='commercial' and raw['sheet'] in ('Table1','29.12.23')) or (raw['book']=='parcel' and raw['sheet']=='Sheet1 (2)') or raw['book']=='catering':continue
        values={k:str(v.get('value','')) for k,v in raw['cells'].items() if v.get('value') not in ('',None)}
        if len(values)<2:continue
        joined=' · '.join(values.values())
        # Attach only an explicit complete lot code; a station/train-only note
        # stays a separate reference rather than acquiring a fictitious identity.
        exact=list(dict.fromkeys(code(v) for v in values.values() if len(code(v))>8 and code(v) in assets))
        reference={'id':f"{raw['book']}:{raw['sheet']}:{raw['row']}",'file':Path(raw['file']).name,
                   'sheet':raw['sheet'],'row':raw['row'],'values':values,
                   'formulas':{k:v['formula'] for k,v in raw['cells'].items() if v.get('formula')},
                   'date':raw['cells'].get('A',{}).get('date') or day(values.get('A'))}
        if len(exact)==1:assets[exact[0]]['references'].append(reference)
        else:
            train=re.search(r'(?<!\d)[1-9]\d{4}(?!\d)',joined)
            label=' · '.join(values.get(k,'') for k in (('C','F') if raw['book']=='parcel' else ('B','C','D'))).strip(' ·')
            if not label:continue
            if re.search(r'\bColumn\d+\b',label,re.I) or label in ('Train','T/No','T/No ·','Sl No'):continue
            key='REF:'+reference['id'];assets[key]={'id':key,'lot':label,'description':joined[:600],
                'category':'Workbook reference · scope unverified','events':[],'workings':[],'contracts':[],'scheduled':[],
                'references':[reference],'scope':identity(label,joined)}
    schedules=store.evidence('__workspace__','direct_scheduled_snapshot')
    for row in (schedules[-1].get('rows',[]) if schedules else []):
        item={k:row[k] for k in ('lot','catalogue','start','close','description','category','rate_unit','status','source') if k in row}
        item['date']=day(row.get('start')) or str(row.get('date',''))[:10];item['scope']=identity(row['lot'],row.get('description'))
        asset(row['lot'],row.get('description',''),row.get('category',''))['scheduled'].append(item)
    listings=store.evidence('__workspace__','direct_contract_snapshot')
    fresh=listings[-1] if listings else {}
    details={r['contract']:r for r in saved}
    old=store.evidence('__workspace__','web_contract_candidates')
    old_rows=[r.get('raw',r) for r in old[-1].get('rows',[])] if old else []
    fresh_ids={r.get('Contract No.') for r in fresh.get('rows',[])}
    combined={r.get('Contract No.'):r for r in old_rows}
    combined.update({r.get('Contract No.'):r for r in fresh.get('rows',[])})
    source_rows=list(combined.values())
    for raw in source_rows:
        number=raw.get('Contract No.','');lot=raw.get('Asset Id','')
        if not lot:continue
        detail=details.get(number,{})
        if detail and not detail.get('unavailable'):raw=detail.get('listing',raw)
        # The agreement explicitly names the auction lot; the listing's Asset
        # Id can be a persistent asset code with an internal #id instead.
        lot=detail.get('fields',{}).get('lot') or lot
        item={'number':number,'lot':lot,'date':raw.get('Contract Date',''),'contractor':raw.get('Contractor',''),
              'start':raw.get('CP Start',''),'end':raw.get('CP End',''),'status':raw.get('Status',''),
              'fields':detail.get('fields',{}),'source':detail.get('source') or raw.get('source',''),
              'captured_at':detail.get('captured_at') or fresh.get('collected_at',''),
              'detail_issue':detail.get('unavailable','') if detail else 'Agreement details have not yet been collected.',
              'listing_fresh':number in fresh_ids and not raw.get('listing_requires_refresh')}
        asset(lot,category=raw.get('Category',''))['contracts'].append(item)
    lot_keys=dict(store.lots())
    for key,r in reviewed:
        lot=lot_keys.get(key,{}).get('lot')
        if not lot or not r.get('source') or not r.get('status'):continue
        item={'number':r.get('contract') or r.get('contract_no') or 'Reviewed contract evidence',
              'lot':lot,'date':r.get('award_date',''),'contractor':r.get('awardee',''),
              'start':r.get('start',''),'end':r.get('end',''),'status':r['status'],
              'fields':{'explicit_lar':r.get('lar',''),'rate_unit':r.get('rate_unit',''),
                        'actual_closure_date':r.get('closed',''),'closure_reason':r.get('closure_reason','')},
              'source':r['source'],'captured_at':r.get('captured_at',''),'listing_fresh':False,
              'reviewed_evidence':True,'detail_issue':''}
        dest=asset(lot)['contracts']
        if not any(c['number']==item['number'] and c['status']==item['status'] for c in dest):dest.append(item)
    for a in assets.values():
        for k in ('events','workings','scheduled'):a[k].sort(key=lambda r:(r.get('date',''),r.get('catalogue','')),reverse=True)
        latest=(a['scheduled'] or a['events'] or a['workings'])
        if latest:
            a['description']=latest[0].get('description') or a['description'];a['category']=latest[0].get('category') or a['category'];a['scope']=latest[0].get('scope')
        if not a.get('scope'):a['scope']=identity(a['lot'],a['description'],a['category'])
        a['search']=' '.join([a['lot'],a['description'],a['category'],*[r.get('description','') for r in a['events']],*[r.get('description','') for r in a['workings']],*[' '.join(r['values'].values()) for r in a['references']]]).casefold()
    history=store.evidence('__workspace__','direct_history_stage')
    return {'version':VERSION,'assets':list(assets.values()),'coverage':{'history':history[-1] if history else {},
            'contracts':{k:fresh.get(k) for k in ('collected_at','complete','warnings')},'agreement_count':len(saved)}}

def snapshot(store):
    """Compress once per evidence change; never parse Excel on UI polling."""
    cached=getattr(store,'_analysis_library_cache',None)
    if cached and time.monotonic()-getattr(store,'_analysis_library_checked',0)<30:return cached
    store._analysis_library_checked=time.monotonic()
    with store.connect() as c:
        signature=[tuple(c.execute(sql).fetchone()) for sql in (
            'SELECT count(*),max(revision) FROM df_auctions WHERE active=1',
            'SELECT count(*),max(captured_at) FROM df_direct_contract_details',
            'SELECT count(*),max(imported_at) FROM df_workbooks WHERE active=1',
            "SELECT count(*),max(rowid) FROM audit")]
    revision=hashlib.sha256(json.dumps([VERSION,signature]).encode()).hexdigest()
    if cached and cached['revision']==revision:return cached
    raw=json.dumps(build(store),ensure_ascii=False,separators=(',',':')).encode()
    result={'revision':revision,'encoding':'deflate-base64','data':base64.b64encode(zlib.compress(raw,6)).decode()}
    store._analysis_library_cache=result
    return result
