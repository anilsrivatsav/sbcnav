"""Read-only source collection for the categories represented in the three books.

Workbook numbers, dates, rates and outcomes are never imported by this workflow.
Every source catalogue/contract detail is committed before continuing.
"""
import hashlib,json,re,subprocess,tempfile,threading,uuid,traceback
from datetime import date,datetime,timedelta
from pathlib import Path
from urllib.parse import urlparse

EXCLUDED_CATEGORIES={
 'Misc-Static-Services - Nursing pods',
 'Misc-Static-Services - Sleeping pods at station',
 'Misc-Static-Services - Gaming Zone',
 'Misc-Static-Services - Rail Coach Restaurant',
}
PREFIXES=('Parking','Pay and Use','Advertising','ATM','Parcel','Catering','MPS','PMBJK')
MISC_WORDS=('two wheeler and other parcel packing','digital lockers','relaxation chair',
 'promotional kiosk','water vending','ev charging','medical facilities','battery operated carts',
 'health kiosk','travel help desk','audio advertising','vertical garden','textile stores',
 'mobiles and accessories','static general','premium stores','mobile general')

def in_scope(category):
    category=str(category or '').strip()
    if category in EXCLUDED_CATEGORIES:return False
    return category.startswith(PREFIXES) or any(word in category.casefold() for word in MISC_WORDS)

def official(url):
    parsed=urlparse(str(url or ''))
    return parsed.scheme=='https' and parsed.hostname in ('ireps.gov.in','www.ireps.gov.in')

def mark_reader(page,marker,check,wait):
    for attempt in range(8):
        check()
        try:
            page.wait_for_load_state('load')
            page.evaluate('(value)=>window.name=value',marker)
            return
        except Exception as exc:
            if 'execution context was destroyed' not in str(exc).casefold() or attempt==7:raise
            wait(.25)

def agreement_fields(text,contract):
    """Extract explicit agreement labels. Planned expiry never proves closure."""
    lines=[line.strip() for line in str(text).splitlines() if line.strip()]
    normalized=lambda value:re.sub(r'\s+','',str(value)).casefold()
    joined='\n'.join(lines)
    match=re.search(r'(?:^|[\t\n])\s*Contract No\.?\s*[:\t ]*([^\t\n]+)',joined,re.I)
    if not match or normalized(match[1])!=normalized(contract):
        raise ValueError('Agreement does not identify the exact requested contract.')
    fields={}
    patterns={
      'agreement_rate':r'Rate \(Rs\.?\)\s*[:\t ]*([0-9][0-9,.]*)',
      'explicit_lar':r'(?:Last Accepted Rate|\bLAR\b)\s*[:\t ]*(?:Rs\.?\s*)?([0-9][0-9,.]*)',
      'contract_value':r'Contract Value\s*[:\t ]*(?:Rs\.?\s*)?([0-9][0-9,.]*)',
      'rate_unit':r'Rate Unit\s*[:\t ]*([^\t\n]+)',
      'lot':r'Lot No\.?\s*[:\t ]*([^\t\n]+)',
      'catalogue':r'(?:Auction )?Catalogue No\.?\s*[:\t ]*([^\t\n]+)',
      'contract_start':r'Contract Start Date\s*[:\t ]*([^\t\n]+)',
      'planned_contract_end':r'Contract End Date\s*[:\t ]*([^\t\n]+)',
      'actual_closure_date':r'(?:Actual (?:Contract )?Closure Date|(?:Contract )?Closure Date|Date of (?:Contract )?Closure|Foreclosure Date|Termination Date|Actual Completion Date)\s*[:\t ]*([^\t\n]+)',
      'closure_reason':r'(?:Reason for (?:Closure|Termination|Foreclosure)|(?:Closure|Termination|Foreclosure) Reason)\s*[:\t ]*([^\t\n]+)',
    }
    for name,pattern in patterns.items():
        found=re.search(r'(?:^|[\t\n])\s*'+pattern,joined,re.I)
        if found:
            value=found[1].strip()
            if name in ('contract_start','planned_contract_end','actual_closure_date'):
                parsed=None
                for candidate in (value,value.split(' ')[0],value[:10]):
                    for fmt in ('%d/%m/%Y','%d-%m-%Y','%Y-%m-%d','%d.%m.%Y','%d-%m-%y','%d-%b-%Y','%d %b %Y'):
                        try:parsed=datetime.strptime(candidate,fmt).date();break
                        except ValueError:pass
                    if parsed:break
                if not parsed:continue
                fields[name+'_iso']=parsed.isoformat()
            fields[name]=value
    allocation=re.search(r'Mode of allotment:\s*e-Auction\s*\(Auction date-\s*([^,\n]+),\s*Catalogue No-\s*([^,\n]+),\s*Lot No-\s*([^\)\n]+)\)',joined,re.I)
    if allocation:
        fields.update(auction_date=allocation[1].strip(),catalogue=allocation[2].strip(),lot=allocation[3].strip())
    rate_line=re.search(r'(?:^|\n)Rate \(Rs\.?\)\s*[:\t ]*([0-9][0-9,.]*)\t([^\t\n]+)',joined,re.I)
    if rate_line and ('licensing fee' in rate_line[2].casefold() or rate_line[2].casefold().strip()=='full contract value'):
        fields['rate_unit']=rate_line[2].strip()
    asset_code=re.search(r'(?:^|\n)Asset Code\s*[:\t ]*([^\t\n]+)',joined,re.I)
    if asset_code:fields['asset_code']=asset_code[1].strip()
    decision=re.search(r'^(Contract (cancelled|terminated|foreclosed|closed|completed)\s+(?:w\.?e\.?f\.?|with effect from|effective from|on)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})[^\n]*)$',joined,re.I|re.M)
    if decision:
        for fmt in ('%d/%m/%Y','%d-%m-%Y'):
            try:
                actual=datetime.strptime(decision[3],fmt).date().isoformat()
                fields.update(actual_closure_date=decision[3],actual_closure_date_iso=actual,
                              decision_type=decision[2].capitalize(),decision_text=decision[1].strip())
                break
            except ValueError:pass
    fields['parser_version']=2
    return fields

class DirectCollector:
    def __init__(self,desk):
        self.desk=desk
        with desk.store.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS df_direct_contract_details(contract TEXT PRIMARY KEY,listing_revision TEXT,data TEXT,captured_at TEXT)')

    def message(self,text):self.desk.state.update(phase='collecting',message=text,error=None)
    def check(self):
        if self.desk.cancelled.is_set():raise RuntimeError('Direct collection stopped. Completed source records are retained.')

    def completed_history(self,first,last):
        saved=self.desk.store.evidence('__workspace__','history_snapshot')
        snapshot=saved[-1] if saved else {}
        coverage=snapshot.get('coverage',{})
        visited=coverage.get('visited',[]);expected=coverage.get('expected')
        if not(snapshot.get('complete') and snapshot.get('from_date','9999')<=first and snapshot.get('to_date','')>=last and
               coverage.get('complete') and type(expected) is int and len(set(visited))==len(visited)==expected):
            raise ValueError('Complete catalogue metadata is required before resuming the remaining stages.')
        if not set(visited).issubset(self.desk.library().known_catalogues(stable_only=True)):
            raise ValueError('A verified catalogue checkpoint is missing.')
        with self.desk.store.connect() as c:events=[json.loads(r[0]) for r in c.execute('SELECT data FROM df_auctions WHERE active=1')]
        sold=[r for r in events if in_scope(r.get('category')) and r.get('outcome')=='Sold']
        resolved=lambda r:official(r.get('source')) and ((r.get('bid_rows') and official(r.get('bid_source'))) or
            (r.get('bid_details_unavailable') and ('bid_viewer_rows' in r or not official(r.get('bid_source')))))
        if not all(resolved(r) for r in sold):raise ValueError('Some scoped sold lots still require a bid-viewer source capture.')
        return {'complete':True,'from_date':first,'to_date':last,'coverage':coverage,'sold_lots':len(sold),
                'bid_rate_tables':sum(bool(r.get('bid_rows')) for r in sold),'unavailable_rates':sum(bool(r.get('bid_details_unavailable')) for r in sold),
                'metadata_collected_at':snapshot.get('collected_at'),'verified_at':datetime.now().isoformat()}

    def completed_schedule(self,last):
        saved=self.desk.store.evidence('__workspace__','direct_scheduled_snapshot')
        data=saved[-1] if saved else {};coverage=data.get('coverage',{})
        expected=coverage.get('expected');visited=coverage.get('visited',[])
        wanted={'from':date.fromisoformat(last).strftime('%d/%m/%Y'),'to':'31/12/2099'}
        if not(data.get('complete') and coverage.get('complete') and coverage.get('range')==wanted and type(expected) is int and len(set(visited))==len(visited)==expected):
            raise ValueError('Verified complete scheduled-auction coverage is required before resuming contracts only.')
        for folder in coverage.get('additional_closed_folders',[]):
            proof=folder.get('coverage',{});count=proof.get('expected');ids=proof.get('visited',[])
            if not(proof.get('complete') and type(count) is int and len(set(ids))==len(ids)==count):raise ValueError('An additional closed-auction folder is incomplete.')
        return data

    def run(self,first,last,resume_after_history=False,resume_after_scheduled=False):
        from rp.history_refresh import retry_connection
        skip_history=resume_after_history
        for attempt in range(3):
            try:
                self._run(first,last,skip_history,resume_after_scheduled)
                return
            except Exception as exc:
                self.desk.store.save_evidence('__workspace__','direct_collection_error_trace',{'stage':getattr(self,'stage','starting'),
                    'error':str(exc).split('Call log:')[0][:1200],'trace':traceback.format_exc().split('Call log:')[0][-12000:],
                    'at':datetime.now().isoformat()},str(attempt))
                navigation_race='execution context was destroyed' in str(exc).casefold()
                if attempt<2 and (retry_connection(exc,attempt,self.desk.cancelled.is_set()) or (navigation_race and not self.desk.cancelled.is_set())):
                    self.desk.state.update(phase='reconnecting',message='Reconnecting the direct IREPS collection; source checkpoints are retained.',error=None)
                    try:self.completed_history(first,last);skip_history=True
                    except ValueError:skip_history=False
                    if not self.desk.cancelled.wait(2):continue
                self.desk.state.update(phase='error',message='Direct collection stopped. Saved source records are retained.',error=str(exc).split('Call log:')[0][:1200])
                self.desk.store.save_evidence('__workspace__','direct_collection_status',{'complete':False,'error':str(exc).split('Call log:')[0][:1200],'from_date':first,'to_date':last,'at':datetime.now().isoformat()})
                return

    def job(self,reader,job,scan=None):
        from rp.browser_runtime import browser_reader_runtime,ireps_browser_endpoint
        desk=self.desk
        endpoint=json.loads((desk.engine.STATE/'browser.json').read_text())['port']
        node,package=browser_reader_runtime()
        marker='direct-ireps-'+uuid.uuid4().hex
        mark_reader(reader.page,marker,self.check,desk.cancelled.wait)
        payload={'playwright_module':str(package),'endpoint':ireps_browser_endpoint(endpoint),'marker':marker,'job':{'id':uuid.uuid4().hex,**job}}
        report={};rows=None;failure=''
        with tempfile.TemporaryFile(mode='w+',encoding='utf8') as diagnostics:
            desk.process=subprocess.Popen([str(node),str(Path(__file__).with_name('collect.mjs'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=diagnostics,text=True,encoding='utf8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            timer=threading.Timer(14400,desk.process.kill);timer.start()
            try:
                desk.process.stdin.write(json.dumps(payload));desk.process.stdin.close()
                for line in desk.process.stdout:
                    event=json.loads(line)
                    self.check()
                    if event.get('type')=='progress':
                        self.message('Direct IREPS: '+event['message'])
                        report=event.get('report') or report
                        if scan:self.desk.library().scan_progress(scan,report)
                    elif event.get('type')=='catalogue' and scan:
                        library=desk.library()
                        if event.get('reuse'):library.adopt_catalogue(scan,event['catalogue'],event['source_id'],event['fingerprint'],event['date'])
                        else:library.save_catalogue(scan,event['catalogue'],event['fingerprint'],event['rows'],event.get('source_id'))
                    elif event.get('type')=='result':rows=event['rows']
                    elif event.get('type')=='error':failure=event['message']
                code=desk.process.wait()
            finally:
                timer.cancel()
                if desk.process.poll() is None:desk.process.kill();desk.process.wait()
                desk.process=None
        if code or rows is None:
            if scan:desk.library().scan_progress(scan,report,interrupted=True)
            raise RuntimeError(failure or 'Direct IREPS reader stopped before completing its displayed record count.')
        if scan:desk.library().finish_scan(scan,report)
        return rows,report

    def _run(self,first,last,skip_history=False,skip_schedule=False):
        from deskflow import reader_lifetime
        desk=self.desk;library=desk.library()
        with desk.store.connect() as c:events=[json.loads(r[0]) for r in c.execute('SELECT data FROM df_auctions WHERE active=1')]
        categories=sorted({r.get('category','') for r in events if in_scope(r.get('category'))})
        missing=[r for r in events if in_scope(r.get('category')) and r.get('outcome')=='Sold' and
                 ((not r.get('bid_rows') and not r.get('bid_details_unavailable')) or
                  (r.get('bid_details_unavailable') and official(r.get('bid_source')) and 'bid_viewer_rows' not in r))]
        force=sorted({r.get('source_catalogue_id') or r['catalogue'] for r in missing})
        self.message(f'Reading direct IREPS history for {len(categories)} workbook categories; {len(missing)} sold lots need bid-viewer details.')
        with desk.playwright() as pw,reader_lifetime() as owned:
            browser=desk.engine.browser(pw,{'ireps_only':True},self.message)
            def fresh_reader():
                if owned:
                    try:owned[-1].close()
                    except Exception:pass
                current=desk.reader(browser.contexts[0],self.message,desk.cancelled.is_set);owned.append(current.page)
                current.login();self.check();return current
            if not skip_history:
                self.stage='closed_history';reader=fresh_reader()
                scan=library.start_scan(first,last)
                _,coverage=self.job(reader,{'action':'closed','library':True,'from_date':first,'to_date':last,
                     'known_catalogues':library.known_catalogues(stable_only=True),'refresh_after':(date.fromisoformat(last)-timedelta(days=30)).isoformat(),
                     'force_catalogues':force,'detail_categories':categories},scan)
            verified=self.completed_history(first,last)
            coverage=verified['coverage']
            desk.store.save_evidence('__workspace__','direct_history_stage',verified)
            self.check()
            if skip_schedule:
                previous=self.completed_schedule(last);scheduled=previous['rows'];schedule_report=previous['coverage']
            else:
                self.stage='scheduled_and_other_closed_folders';reader=fresh_reader()
                scheduled,schedule_report=self.job(reader,{'action':'scheduled','all_scheduled':True,'stable_ids':True,'from_date':last,'to_date':'2099-12-31'})
                scheduled=[r for r in scheduled if in_scope(r.get('category'))]
                desk.store.save_evidence('__workspace__','direct_scheduled_snapshot',{'complete':True,'rows':scheduled,'coverage':schedule_report,'collected_at':datetime.now().isoformat(),'scope':'All scheduled statuses for categories represented by the three workbooks'})
            self.stage='contracts';reader=fresh_reader()
            self.contracts(reader,first,last)
            desk.store.save_evidence('__workspace__','direct_collection_status',{'complete':True,'from_date':first,'to_date':last,'at':datetime.now().isoformat(),'scope_categories':categories,'history_coverage':coverage,'scheduled_lots':len(scheduled)})
            desk.state.update(phase='complete',message='Direct IREPS collection completed for workbook categories. Missing portal fields remain explicitly unavailable; no Excel values were imported or written.',error=None)

    def contracts(self,reader,first,last):
        desk=self.desk
        reader.navigate('Contracts')
        labels=reader.page.locator('#regCat option').all_text_contents()
        groups=[label.strip() for label in labels if label.strip() and (any(label.strip().casefold().startswith(p.casefold()) for p in PREFIXES) or label.strip().casefold().startswith('misc'))]
        def read_group(category):
            self.check();self.message(f'Reading contract category: {category}')
            cached=desk.store.evidence('__workspace__','direct_contract_category_checkpoint')
            cached=next((r for r in cached if r.get('category')==category and r.get('from_date')==first and r.get('to_date')==last and r.get('at','')[:10]==date.today().isoformat()),None)
            if cached:return cached['rows'],cached['warnings']
            reader.search(category,start=date.fromisoformat(first).strftime('%d/%m/%Y'),end=date.fromisoformat(last).strftime('%d/%m/%Y'))
            observed={};original=reader.page_rows;reader.warnings.clear()
            def remember(mode):
                batch=original(mode)
                if mode=='contracts':
                    for row in batch:observed[tuple(row['cells'][:8])]=row
                return batch
            reader.page_rows=remember
            try:
                found=reader.all_rows('contracts')
            except Exception as exc:
                if not any(s in str(exc) for s in ('repeated a page','pagination stopped','row count mismatch','Page.wait_for_function: Timeout')):raise
                self.check()
                reader.warnings.append(str(exc));found=list(observed.values())
            finally:reader.page_rows=original
            notes=list(reader.warnings)
            desk.store.save_evidence('__workspace__','direct_contract_category_checkpoint',{'category':category,'from_date':first,'to_date':last,'at':datetime.now().isoformat(),'rows':found,'warnings':notes},category)
            if notes:
                debug=reader.page.locator('table').evaluate_all('''tables=>tables.map(t=>{const rows=[...t.rows];const header=rows.find(r=>[...r.cells].some(c=>/^Contract No\\.?$/i.test(c.innerText.trim())));return header?{headers:[...header.cells].map(c=>c.innerText.trim()),rows:rows.filter(r=>r!==header).map(r=>[...r.cells].map(c=>({text:c.innerText.trim(),span:c.colSpan,rows:c.rowSpan})))}:null}).filter(Boolean)''')
                desk.store.save_evidence('__workspace__','direct_contract_list_debug',{'category':category,'source':reader.page.url,'warnings':notes,'tables':debug},category)
            return found,notes
        entries,all_notes=read_group('---All---');issues=[];category_checks=[]
        if all_notes:
            combined={tuple(row['cells'][:8]):row for row in entries}
            scoped_all={row['cells'][0] for row in entries if len(row['cells'])==9 and in_scope(row['cells'][3])}
            category_ids=set()
            if not groups:issues.extend(all_notes)
            for category in groups:
                found,notes=read_group(category)
                category_checks.append({'category':category,'visible_rows':len(found),'warnings':notes,'complete':not notes})
                issues.extend(notes)
                for row in found:
                    combined[tuple(row['cells'][:8])]=row
                    if len(row['cells'])==9 and in_scope(row['cells'][3]):category_ids.add(row['cells'][0])
            if groups and not scoped_all.issubset(category_ids):issues.append('Some all-category source contracts were not returned by the category partitions; all visible rows were retained.')
            entries=list(combined.values())
        contracts={}
        for entry in entries:
            cells=entry['cells']
            if len(cells)!=9:raise RuntimeError('IREPS contract columns changed; collection stopped without altering workbooks.')
            raw=dict(zip(('Contract No.','Contract Date','Contractor','Category','Asset Id','CP Start','CP End','Status','Actions'),cells))
            if not in_scope(raw['Category']):continue
            raw['source']=reader.page.url
            raw['source_links']=entry.get('links',[])
            if raw['Contract No.'] in contracts and contracts[raw['Contract No.']]!=raw:
                previous=contracts[raw['Contract No.']]
                # Category partitions repeat the same contracts. Never nest a
                # previous record containing its own history (exponential JSON).
                fields=('Contract No.','Contract Date','Contractor','Category','Asset Id','CP Start','CP End','Status')
                variants={tuple(item.get(k,'') for k in fields):{k:item.get(k,'') for k in fields}
                          for item in previous.get('additional_source_rows',[])+[previous,raw]}
                if len(variants)>1:raw['additional_source_rows']=list(variants.values())
            contracts[raw['Contract No.']]=raw
        older=desk.store.evidence('__workspace__','web_contract_candidates')
        for entry in (older[-1].get('rows',[]) if older else []):
            raw=entry.get('raw',entry);number=raw.get('Contract No.','')
            if number and in_scope(raw.get('Category')) and number not in contracts:
                contracts[number]={**raw,'listing_requires_refresh':True}
        desk.store.save_evidence('__workspace__','direct_contract_snapshot',{'rows':list(contracts.values()),'complete':not issues,'warnings':issues,'all_category_counter_notes':all_notes,'category_checks':category_checks,'from_date':first,'to_date':last,'collected_at':datetime.now().isoformat()})
        for index,(number,raw) in enumerate(contracts.items(),1):
            self.check()
            revision=hashlib.sha256(json.dumps({'reader_version':3,'listing':{k:v for k,v in raw.items() if k not in ('Actions','source_links')}},sort_keys=True).encode()).hexdigest()
            with desk.store.connect() as c:prior=c.execute('SELECT listing_revision FROM df_direct_contract_details WHERE contract=?',(number,)).fetchone()
            if prior and prior[0]==revision:continue
            self.message(f'Reading agreement {index} of {len(contracts)}: {number}')
            try:
                reader.navigate('Contracts')
                reader.search('---All---',start='01/01/2000',end=date.fromisoformat(last).strftime('%d/%m/%Y'),contract=number)
                rows=reader.page_rows('contracts')
                exact=[r for r in rows if r['cells'][0].strip()==number]
                if len(exact)!=1:raise RuntimeError('Exact contract agreement search did not return one matching contract.')
                raw={**dict(zip(('Contract No.','Contract Date','Contractor','Category','Asset Id','CP Start','CP End','Status','Actions'),exact[0]['cells'])),
                     'source':reader.page.url,'source_links':exact[0].get('links',[])}
                # The rendered layout table does not consistently expose cell
                # roles. The exact result row was verified above; require its
                # sole read-only agreement link and validate the opened number.
                link=reader.page.locator('a[title="Contract"]')
                if link.count()!=1:raise RuntimeError('The exact read-only Contract agreement link is unavailable.')
                with reader.page.expect_navigation(wait_until='load'):link.click()
                text=reader.page.locator('body').inner_text()
                if not official(reader.page.url):raise RuntimeError('Contract agreement is outside IREPS.')
                try:fields=agreement_fields(text,number)
                except ValueError:
                    desk.store.save_evidence('__workspace__','direct_agreement_parse_debug',{'contract':number,'source':reader.page.url,'text':text},number)
                    raise
                tables=reader.page.locator('tr').evaluate_all('(rows)=>rows.filter(r=>!r.querySelector("table")).map(r=>[...r.cells].map(c=>c.innerText.trim())).filter(r=>r.some(Boolean))')
                detail={'contract':number,'listing':raw,'fields':fields,'source':reader.page.url,'text':text,'tables':tables,'captured_at':datetime.now().isoformat()}
            except Exception as exc:
                message=str(exc).split('Call log:')[0][:800]
                if any(word in message.casefold() for word in ('session expired','target page','browser has been closed','connection closed','cancelled','outside ireps')):raise
                self.check()
                detail={'contract':number,'listing':raw,'fields':{},'source':raw['source'],'unavailable':message,'captured_at':datetime.now().isoformat()}
            with desk.store.connect() as c:c.execute('INSERT OR REPLACE INTO df_direct_contract_details VALUES(?,?,?,?)',(number,revision,json.dumps(detail,ensure_ascii=False),datetime.now().isoformat()))
        if issues:raise RuntimeError('IREPS contract list did not reconcile its displayed count. All explicitly listed contracts and available agreements were retained; completeness remains unverified.')
