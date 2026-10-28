"""Persistent RP review workspace served by the existing desktop connection."""
import json, os, subprocess, threading, uuid, hashlib, tempfile
from pathlib import Path
from datetime import datetime, date, timedelta
from dataclasses import asdict
from rp.store import Store
from rp.rules import calculate, number, FAMILIES, UNITS, CONTRACT_STATES, reviewed_continuation_matches
from rp.standard_conditions import review, annual_fee
from rp.contract_fields import candidate_fields
from rp.rules import Result
from rp.workbooks import WorkbookSelection, family_group, SPECS
from rp.review import WorkbookPreview, digest
from rp.verifier import verify
from rp.history_refresh import refresh_start, retry_connection
from rp.workbook_sync import read_rows, preserve_excel_value
from rp.history_library import HistoryLibrary, POLICY_VERSION, fingerprint
import re, base64
from decimal import Decimal

def public_text(value):
    if isinstance(value,str):
        return re.sub(r'\bRP\b','value',re.sub(r'reserve[- ]price','proposed value',value,flags=re.I),flags=re.I).replace('RPAssistant','Deskflow')
    if isinstance(value,(list,tuple)):return [public_text(v) for v in value]
    if isinstance(value,dict):return {k:v if k in ('file','workbook','path','backup','source','bid_source','justification','calculation_notes','review','workbook_candidates') else public_text(v) for k,v in value.items()}
    return value

def parse_day(value):
    text=str(value or '').strip().split(' ')[0]
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%d.%m.%Y','%d-%m-%y'):
        try:return datetime.strptime(text,fmt).date().isoformat()
        except ValueError:pass
    raise ValueError('Unrecognised date: '+text)


def short_justification(result, inputs=None):
    continuation = (inputs or {}).get('continuation') or {}
    if result.get('ready') and continuation.get('mode') == 'parcel_previous':
        dates = ' & '.join(datetime.fromisoformat(day).strftime('%d.%m.%Y') for day in continuation['failed_dates'])
        return f"No bids received on {dates}. Previous RP Rs {Decimal(continuation['base']):,.2f} reduced by 10% to Rs {Decimal(result['rp']):,.2f}."
    if result.get('ready') and result.get('rule') == 'workbook_continuation':
        factor = Decimal(result['multiplier']) * 100
        percent = format(factor.normalize(), 'f')
        base = Decimal(result['base'])
        return f'Continue the reviewed working at {percent}% of Rs {base:,.2f}; withdrawn auctions excluded.'
    if not result.get('ready'):return result.get('missing', '')
    amount=lambda value:format(Decimal(str(value or 0)), ',.2f')
    base=amount(result.get('base'));value=amount(result.get('rp'))
    descriptions={
        'running_lar':f'Running contract LAR Rs {base} retained.',
        'completed_lar':f'Completed contract LAR Rs {base} increased by 10%.',
        'foreclosed_lar':f'Reviewed foreclosure basis: LAR Rs {base} retained.',
        'withdrawn_retry':f'Previous approved RP Rs {base} retained; withdrawal is not a failed auction.',
        'first_two_attempts':f'Initial approved RP Rs {base} retained for the first two attempts.',
        'successive_reduction':f'Two or more failed auctions. Previous RP Rs {base} reduced by 10%.',
        'publicity_failure':f'Failed publicity auction. Previous RP Rs {base} reduced by 10%.',
        'parcel_reduction':f'Original parcel benchmark Rs {base} multiplied by {result.get("multiplier")}.',
        'non_commencement':'Non-commencement: higher of previous RP and verified distinct second-bidder rate adopted.',
        'shop_market':f'Reviewed market bid Rs {base} adopted.',
        'new_publicity':f'Sourced publicity benchmark Rs {base} adopted.',
        'food_truck':f'Reviewed food-truck benchmark adopted subject to the recorded minimum.'}
    return descriptions.get(result.get('rule'),result.get('justification',''))+f' Proposed RP Rs {value}.'

class Deskflow:
    def library(self):
        if not hasattr(self,'_history_library'):self._history_library=HistoryLibrary(self.store)
        return self._history_library

    def import_baseline(self):
        self.state.update(phase='importing',message='Importing the three workbooks into the local history library…',error=None)
        paths=WorkbookSelection(self.userdir/'workbooks.json').paths('D:/ANIL/UK')
        reports=self.library().import_workbooks(paths)
        self.library().migrate_evidence()
        return reports

    def __init__(self, updater, engine, playwright, reader):
        self.updater,self.engine,self.playwright,self.reader=updater,engine,playwright,reader
        self.store=Store(Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'RPAssistant'/'rpassistant.sqlite')
        self.lock=threading.RLock();self.thread=None
        self.cancelled=threading.Event();self.process=None
        self.previews={}
        self._workbook_digests={}
        self.userdir=self.store.path.parent
        self.state={'phase':'ready','message':'Ready to update local workbooks.','error':None}
        previous=self.store.evidence('__workspace__','workbook_update')
        if previous:
            report=previous[-1]
            self.state.update(phase='ready',message=f"Last workbook save: {len(report.get('saved',[]))} files. See each row for current calculations and missing evidence.")

    def result(self,lot,auctions,contract,inputs):
        if inputs.get('review_issue'):
            return {'ready':False,'missing':inputs['review_issue']}
        if not inputs.get('conditions_reviewed'):
            return {'ready':False,'missing':'Review SCC v2.0 and the applicable catalogue/special conditions.'}
        if contract.get('status') in ('Foreclosed','Not signed','Not commenced','Cancelled (reason unknown)') and not contract.get('termination_source'):
            return {'ready':False,'missing':'Record the cancellation/termination decision and reason. A deadline or a cancelled label alone does not establish the cause.'}
        return asdict(calculate(lot,auctions,contract,inputs))

    def detail(self,key):
        lot=dict(self.store.current_lots()).get(key)
        if lot is None:raise ValueError('Collect or select a current pending lot.')
        auctions=self.store.evidence(key,'auction');c=self.store.evidence(key,'contract');i=self.store.evidence(key,'inputs')
        merged={(a.get('date'),a.get('catalogue'),a.get('previous_lot',a.get('lot',lot['lot']))):a for a in auctions}
        for row in self.library().auctions_for(lot):
            identity=(row['date'],row['catalogue'],row['previous_lot'])
            prior=merged.get(identity,{})
            if prior.get('outcome')==row.get('outcome') and prior.get('rate_unit')==row.get('rate_unit'):
                for field in ('bid_rate','bid_value','bid_source','awardee','awardee_source'):
                    if row.get(field) in (None,'') and prior.get(field) not in (None,''):row[field]=prior[field]
            merged[identity]=row
        auctions=sorted(merged.values(),key=lambda a:(a.get('date',''),a.get('catalogue','')))
        contract=c[-1] if c else {};inputs=i[-1] if i else {}
        revision=hashlib.sha256(json.dumps([lot,auctions,contract,inputs],sort_keys=True).encode()).hexdigest()
        record={'key':key,'revision':revision,'lot':lot,'auctions':auctions,'contract':contract,'inputs':inputs,
                'result':self.result(lot,auctions,contract,inputs),'conditions':review(contract)}
        record['proposal']=self.library().proposal(key,revision,record['result'])
        scheduled=self.store.evidence('__workspace__','scheduled_snapshot')
        history=self.store.evidence('__workspace__','history_snapshot')
        written=self.store.evidence(key,'workbook_write')
        workbook=dict(written[-1]) if written else None
        if workbook and workbook.get('workbook'):
            try:
                path=Path(workbook['workbook']);stat=path.stat()
                identity=(stat.st_mtime_ns,stat.st_size)
                cache=self.__dict__.setdefault('_workbook_digests',{})
                cached=cache.get(path)
                if not cached or cached[0]!=identity:
                    cached=(identity,digest(path));cache[path]=cached
                workbook['current_digest']=cached[1]
            except OSError:
                workbook['current_digest']=None
        record['verification']=verify(record,scheduled[-1] if scheduled else None,
                                      history[-1] if history else None,workbook)
        return record

    def snapshot(self):
        updater_busy=self.updater.snapshot()['busy']
        with self.lock:
            records=[self.detail(key) for key,_ in self.store.current_lots()]
            candidates=self.store.evidence('__workspace__','web_contract_candidates')
            return {**self.state,'busy':bool(self.thread and self.thread.is_alive()),
                    'updater_busy':updater_busy,'records':records,
                    'candidates':candidates[-1]['rows'] if candidates else [],
                    'collection_warning':('IREPS counts include rows it does not display. '+str(len(candidates[-1]['rows']))+' visible contracts were saved. Verify any unmatched contract in IREPS.' if candidates and candidates[-1].get('warnings') else ''),
                    'families':FAMILIES,'units':UNITS,'states':CONTRACT_STATES,
                    'conditions_by_state':{state:review({'status':state}) for state in CONTRACT_STATES}}

    def overview(self):
        """Small, read-only view of the latest collected IREPS scheduled catalogue."""
        snapshot=self.store.evidence('__workspace__','scheduled_snapshot')
        if not snapshot:
            return {'collected_at':None,'categories':[],'lots':[],'progress':self.progress()}
        try:workbook_rows=self.workbook_rows()
        except (OSError,ValueError):workbook_rows={}
        rows=[]
        for key,lot in self.store.current_lots():
            record=self.detail(key);contract=record['contract'];result=record['result']
            history=[]
            for auction in sorted(record['auctions'],key=lambda item:item.get('date',''),reverse=True):
                if auction.get('date','')>=lot.get('start',''):
                    continue
                # These rows were collected under the same IREPS lot number. Keep
                # the scope visible; a human still verifies exact comparability.
                status=auction.get('outcome','Unknown')
                status_date=auction.get('date','')
                same_rate=False
                if contract.get('lar') not in (None,'') and auction.get('bid_rate') not in (None,''):
                    try:same_rate=number(contract['lar'])==number(auction['bid_rate'])
                    except ValueError:pass
                if status=='Sold' and contract.get('status') in ('Running','Completed','Foreclosed') and same_rate:
                    status=contract['status']
                    status_date=contract.get('closed') if status=='Foreclosed' else contract.get('end') if status=='Completed' else contract.get('start')
                elif status=='No Bids':
                    status='Failed'
                history.append({'date':auction.get('date',''),'status':status,'status_date':status_date or auction.get('date',''),
                                'outcome':auction.get('outcome',''),
                                'lot':auction.get('previous_lot') or auction.get('lot',''),'category':auction.get('category',''),
                                'description':auction.get('description',''),'accepted_rate':auction.get('bid_rate','') if auction.get('outcome')=='Sold' else '',
                                'rate_unit':auction.get('rate_unit',''),'source':auction.get('source','')})
            workbook=workbook_rows.get((lot['lot'],lot.get('catalogue','')))
            if workbook and workbook.get('ambiguous'):workbook=None
            rows.append({'key':key,'asset':lot.get('description') or lot.get('asset') or lot.get('lot',''),
                         'lot':lot.get('lot',''),'category':lot.get('category',''),'subcategory':lot.get('subcategory',''),
                         'date':lot.get('start',''),'station':lot.get('station',''),'train':lot.get('train',''),
                         'catalogue':lot.get('catalogue',''),'details':lot.get('description',''),
                         'rate_unit':lot.get('rate_unit',''),'value':workbook['value'] if workbook else result.get('rp') if result.get('ready') else None,
                         'justification':(workbook['notes'] or short_justification(result,record['inputs'])) if workbook else short_justification(result,record['inputs']),
                         'workbook_source':workbook,
                         'calculation_notes':public_text(result.get('justification','')),
                         'rule':result.get('rule',''),'history':history,'verification':record['verification'],
                         'proposal':{**record['proposal'],'value':result.get('rp') if result.get('ready') else None,'formula':result.get('formula',''),'base':result.get('base',''),'factor':result.get('multiplier',''),'justification':short_justification(result,record['inputs'])},'review':{name:record[name] for name in ('revision','inputs','contract','auctions')},
                         'workbook_candidates':self.library().search_workbooks(lot['lot'],3)})
        rows.sort(key=lambda item:(item['date'],item['catalogue'],item['lot']),reverse=True)
        return {'collected_at':snapshot[-1].get('collected_at'),'categories':sorted({r['category'] for r in rows if r['category']}),
                'lots':rows,'progress':self.progress(),'history_library':self.library().status()}

    def progress(self):
        # The page receives only progress, never the collected commercial records.
        return {**self.state,'busy':bool(self.thread and self.thread.is_alive()),
                'updater_busy':self.updater.snapshot()['busy']}

    def workbook_rows(self):
        paths=WorkbookSelection(self.userdir/'workbooks.json').paths('D:/ANIL/UK')
        signature=tuple((group,str(path),path.stat().st_mtime_ns,path.stat().st_size) for group,path in paths.items())
        cached=self.__dict__.get('_workbook_rows_cache')
        if not cached or cached[0]!=signature:
            cached=(signature,read_rows(paths));self._workbook_rows_cache=cached
        return cached[1]

    def update_workbooks(self):
        try:
            while self.updater.snapshot()['busy']:
                self.state.update(phase='waiting',message='Waiting for the earnings updater to finish…',error=None)
                if self.cancelled.wait(1):raise ValueError('Update stopped.')
            self.import_baseline()
            end=date.today().isoformat()
            first=self.library().earliest_date()
            for action in ('collect','history','contracts'):
                start=first;history_base=None
                if action=='history':start=self.library().history_plan(end)['from_date']
                if action=='contracts':
                    previous=self.store.evidence('__workspace__','web_contract_candidates')
                    if previous and previous[-1].get('complete') and previous[-1].get('from_date','9999')<=first:
                        start=max(first,(date.fromisoformat(previous[-1]['to_date'])-timedelta(days=30)).isoformat())
                self.work(action,start,end,history_base)
                if self.state.get('error'):return
            report=self.write_workbooks(ready_only=False)
            self.import_baseline()
            self.state.update(phase='needs_evidence' if report['pending'] else 'complete',message=f"Update saved. {len(report['pending'])} lots need evidence or proposal review.",error=None)
            return report
        except Exception as exc:
            self.state.update(phase='error',message='Workbook update stopped. Backups and saved evidence are retained.',error=str(exc)[:1400])

    def write_workbooks(self,ready_only=False,dry_run=False):
        from rp.excel_io import _sheet_path,_strings,_text,Q
        from lxml import etree as E
        import zipfile
        self.state.update(phase='writing',message='Calculating supported values and saving the local workbooks…',error=None)
        selection=WorkbookSelection(self.userdir/'workbooks.json')
        targets={group:selection.target('D:/ANIL/UK',group) for group in SPECS}
        existing_rows=read_rows(targets)
        current_digests={group:digest(path) for group,path in targets.items()}
        identities={}
        for group,path in targets.items():
            lotcol,catcol={'commercial':('L','N'),'parcel':('Q','R'),'catering':('N','P')}[group]
            with zipfile.ZipFile(path) as z:
                ss=_strings(z);root=E.fromstring(z.read(_sheet_path(z,SPECS[group]['sheet'])))
                for row in root.find(Q('sheetData')):
                    cs={re.match('[A-Z]+',c.get('r'))[0]:c for c in row}
                    identity=(_text(cs.get(lotcol),ss),_text(cs.get(catcol),ss))
                    if identity[0]:identities.setdefault(identity,set()).add(group)
        batches={g:[] for g in SPECS};keys_by_group={g:[] for g in SPECS};ready_keys=set();ready=0;pending=[];revisions={}
        for key,lot in self.store.current_lots():
            record=self.detail(key);revisions[key]=record['revision'];inputs=dict(record['inputs'])
            family=inputs.get('family') or ('Parcel' if lot.get('category','').startswith('Parcel') else 'Catering / MPS' if any(v in lot.get('category','') for v in ('Catering','Multipurpose')) else 'Food truck' if 'food truck' in lot.get('description','').lower() else 'Parking / Pay & Use')
            inputs['family']=family
            matches=identities.get((lot['lot'],lot.get('catalogue','')),set())
            if len(matches)>1:raise ValueError('The same lot and catalogue appear in multiple workbooks; resolve the duplicate before updating.')
            group=next(iter(matches)) if matches else family_group(family)
            result=Result(**record['result'])
            if result.ready and record['proposal']['status'] not in ('reviewed','saved'):
                result=Result(False,missing='Proposed value is calculated. Review its working and justification before replacing the workbook value.')
            existing=existing_rows.get((lot['lot'],lot.get('catalogue','')))
            if existing and existing.get('ambiguous'):raise ValueError('Multiple workbook rows match this current lot and catalogue: '+lot['lot'])
            saved=self.store.evidence(key,'workbook_write')
            saved_digest=saved[-1].get('digest') if saved and saved[-1].get('ready') else None
            reviewed_digest=record['proposal'].get('workbook_digests',{}).get(group)
            explicit_review=record['proposal']['status']=='reviewed' and reviewed_digest==current_digests[group]
            if preserve_excel_value(existing,result,saved_digest,current_digests[group]) and not explicit_review:
                result=Result(False,missing='Existing Excel value and working retained. Review the website proposal before replacing a manually saved workbook value.')
            if result.ready:
                ready+=1;ready_keys.add(key);result.justification=short_justification(asdict(result),inputs)
            else:
                pending.append({'lot':lot['lot'],'reason':public_text(result.missing)})
                if ready_only:continue
                result.missing=public_text(result.missing)
            keys_by_group[group].append(key)
            events=record['auctions']
            batches[group].append({'lot':lot,'inputs':inputs,'contract':record['contract'],'last':max(events,key=lambda a:a['date']) if events else {},'result':result})
        if not revisions:raise ValueError('No current pending lots were collected. No workbook was changed.')
        staged=[];saved=[]
        try:
            for group,items in batches.items():
                if items:staged.append(WorkbookPreview(targets[group],group,items,allow_existing=True,preserve_pending=True))
            for key,revision in revisions.items():
                if self.detail(key)['revision']!=revision:raise ValueError('Evidence changed during calculation; retry the workbook update.')
            if dry_run:
                return {'preview':[{'workbook':str(preview.path),'sheet':preview.sheet,'changes':preview.changes} for preview in staged],
                        'calculated':ready,'pending':pending,'current_lots':len(revisions),
                        'new_lots':sum((lot['lot'],lot.get('catalogue','')) not in existing_rows for _,lot in self.store.current_lots())}
            for preview in staged:
                preview.check_lock()
                if digest(preview.path)!=preview.original_hash:raise ValueError('A workbook changed during calculation; retry the update.')
            for preview in staged:
                if not preview.changes:continue
                backup=preview.commit();saved.append({'workbook':str(preview.path),'backup':backup,'changes':len(preview.changes)})
                self._workbook_digests.pop(preview.path,None)
                with self.store.connect() as c:self.store.log(c,'excel_saved',saved[-1])
                group=next(group for group,path in targets.items() if path==preview.path)
                saved_digest=digest(preview.path)
                for key in keys_by_group[group]:
                    self.store.save_evidence(key,'workbook_write',{'revision':revisions[key],
                        'ready':key in ready_keys,'workbook':str(preview.path),'digest':saved_digest})
                    if key in ready_keys:
                        proposal=self.detail(key)['proposal']
                        self.library().mark_saved(key,proposal['revision'])
            report={'saved':saved,'calculated':ready,'pending':pending,'at':datetime.now().isoformat()}
            self.store.save_evidence('__workspace__','workbook_update',report)
            message=f'{len(saved)} local workbooks saved with backups. {ready} values calculated.'
            if pending:message+=f' {len(pending)} rows need evidence; existing values and notes were preserved. See the reasons in Deskflow.'
            self.state.update(phase='needs_evidence' if pending else 'complete',message=message,error=None)
            return report
        except Exception as exc:
            message=str(exc)
            if saved:message=f'{len(saved)} workbook(s) saved before stopping. '+message
            self.state.update(phase='error',message='Workbook update stopped.',error=message)
            raise
        finally:
            for preview in staged:preview.close()

    def save(self,data):
        with self.lock:
            if self.thread and self.thread.is_alive():raise ValueError('Wait for collection before editing evidence.')
            key=data['key'];current=self.detail(key)
            if data.get('revision')!=current['revision']:raise ValueError('Evidence changed since this review opened. Discard edits and reopen the lot before saving.')
            auctions=data.get('auctions',[]);contract=data.get('contract',{});inputs=data.get('inputs',{})
            if not isinstance(auctions,list) or not isinstance(contract,dict) or not isinstance(inputs,dict):raise ValueError('Invalid evidence.')
            if len(auctions)>500:raise ValueError('Too many auction records.')
            for a in auctions:
                if not isinstance(a,dict):raise ValueError('Invalid auction row.')
                a['date']=parse_day(a['date'])
                if a['date']>=current['lot']['start']:raise ValueError('History must precede the announced auction.')
            identities=[(a['date'],a.get('catalogue',''),a.get('previous_lot',a.get('lot',''))) for a in auctions]
            if len(identities)!=len(set(identities)):raise ValueError('Duplicate auction evidence would double-count failures.')
            for field in ('award_date','start','end','closed'):
                if contract.get(field):contract[field]=parse_day(contract[field])
            result=self.result(current['lot'],auctions,contract,inputs)
            # Replace evidence as one transaction so removed/edited rows cannot survive silently.
            with self.store.connect() as c:
                c.execute("DELETE FROM evidence WHERE lot_id=? AND kind IN ('auction','contract','inputs','proposal')",(key,))
                for kind,items in [('auction',auctions),('contract',[contract]),('inputs',[inputs]),('proposal',[result])]:
                    for n,item in enumerate(items):
                        evidence_key=(item['date']+'|'+item.get('catalogue','')+'|'+item.get('previous_lot',item.get('lot',''))) if kind=='auction' else 'current'
                        c.execute('INSERT INTO evidence VALUES(?,?,?,?)',(key,kind,evidence_key,json.dumps(item)))
                self.store.log(c,'web_review_saved',{'key':key,'auctions':auctions,'contract':contract,'inputs':inputs,'result':result})
            return self.detail(key)

    def command(self,action,data):
        if action in ('link-asset','save-review','review-proposal'):
            with self.lock:
                if self.thread and self.thread.is_alive():raise ValueError('Wait for the current collection or save to finish.')
                record=self.detail(data.get('key'))
                if data.get('revision')!=record['revision']:raise ValueError('Evidence changed. Refresh this lot before reviewing it.')
                if action=='link-asset':
                    if data.get('confirmed') is not True:raise ValueError('Confirm that the previous lot belongs to this exact asset and scope.')
                    self.library().link_asset(record['lot'],data.get('previous_lot'),data.get('source'))
                elif action=='review-proposal':
                    if not self.library().coverage()['complete']:
                        raise ValueError('Finish and verify the one-time outcome backfill before reviewing proposals.')
                    blocked=[check['message'] for check in record['verification']['checks'] if check['state']=='fail']
                    if blocked:raise ValueError(blocked[0])
                    if not any(check['code']=='history_coverage' and check['state']=='pass' for check in record['verification']['checks']):
                        raise ValueError('Complete the historical coverage before reviewing this proposal.')
                    paths=WorkbookSelection(self.userdir/'workbooks.json').paths('D:/ANIL/UK')
                    self.library().review_proposal(record['key'],data.get('proposal_revision'),{group:digest(path) for group,path in paths.items()})
                else:
                    if not isinstance(data.get('inputs'),dict) or not isinstance(data.get('contract'),dict):raise ValueError('Invalid review inputs.')
                    allowed={'family','benchmark_source','identity_verified','conditions_reviewed','new_asset','previous_rp','initial_rp','finance_fee','earlier_failures','reductions','important_amenity','use_market_bid'}
                    contract_fields={'status','source','awardee','lar','rate_unit','award_date','start','end','closed','termination_source','second_bidder_verified','second_bidder_rate'}
                    if set(data['inputs'])-allowed or set(data['contract'])-contract_fields:raise ValueError('Unsupported review field.')
                    patches=data.get('auctions',[])
                    if not isinstance(patches,list) or len(patches)>500:raise ValueError('Invalid auction review.')
                    evidence={a.get('date','')+'|'+a.get('catalogue','')+'|'+a.get('previous_lot',a.get('lot',record['lot']['lot'])):dict(a) for a in record['auctions']}
                    edited=set()
                    for patch in patches:
                        if not isinstance(patch,dict) or set(patch)-{'identity','bid_rate','bid_source','awardee','awardee_source'}:raise ValueError('Unsupported auction review field.')
                        identity=patch.get('identity')
                        if identity not in evidence or identity in edited:raise ValueError('Auction evidence changed or is duplicated. Refresh this lot.')
                        edited.add(identity)
                        evidence[identity].update({k:v for k,v in patch.items() if k!='identity'})
                    self.save({**record,'auctions':list(evidence.values()),'inputs':{**record['inputs'],**data['inputs']},'contract':{**record['contract'],**data['contract']}})
                self.state.update(phase='ready',message='Review saved. Use Save reviewed proposals to update the workbooks and website.',error=None)
                return self.progress()
        if action=='save-reviewed':
            with self.lock,self.updater.lock:
                if self.updater.snapshot()['busy'] or (self.thread and self.thread.is_alive()):raise ValueError('Wait for the current collection or save to finish.')
                self.cancelled.clear()
                self.thread=threading.Thread(target=self.write_workbooks,kwargs={'ready_only':True},daemon=True);self.thread.start()
            return self.progress()
        if action=='update':
            with self.lock,self.updater.lock:
                if self.thread and self.thread.is_alive():return self.progress()
                self.cancelled.clear()
                self.state.update(phase='starting',message='Starting the local workbook update…',error=None)
                self.thread=threading.Thread(target=self.update_workbooks,daemon=True);self.thread.start()
            return self.progress()
        if action in ('excel-preview','excel-save','excel-export'):
            return self.excel(action,data)
        if action=='cancel':
            self.cancelled.set()
            if self.process and self.process.poll() is None:self.process.kill()
            self.state.update(message='Stopping collection. Saved evidence is retained.')
            return self.snapshot()
        if action=='save':return self.save(data)
        if action=='fee':return {'fee':annual_fee(**data)}
        if action not in ('collect','history','contracts','workbook-history'):raise ValueError('Unknown Deskflow action.')
        # Serialize browser ownership with MCDO without changing its payment pipeline.
        with self.updater.lock, self.lock:
            if self.updater.snapshot()['busy'] or (self.thread and self.thread.is_alive()):raise ValueError('A collection is already running. Wait for it to finish.')
            start=parse_day(data.get('from_date') or '2023-01-01');end=parse_day(data.get('to_date') or date.today().isoformat())
            history_base=None
            if action=='history' and not data.get('from_date') and not data.get('to_date'):
                start=self.library().history_plan(end)['from_date']
            if start>end:raise ValueError('History start must not follow its end.')
            self.cancelled.clear()
            self.state.update(phase='login',message='Sign in with your digital token in the updater Chrome window.',error=None)
            self.thread=threading.Thread(target=self.work,args=(action,start,end,history_base),daemon=True);self.thread.start()
        return self.snapshot()

    def work(self,action,start,end,history_base=None,attempt=0):
        page=None;library_scan=None;collection_report={}
        try:
            with self.playwright() as pw:
                browser=self.engine.browser(pw,{},lambda message:self.state.update(message=message))
                reader=self.reader(browser.contexts[0],lambda message:self.state.update(message=message),self.cancelled.is_set)
                page=reader.page;page.bring_to_front();reader.login()
                self.state.update(phase='collecting',message='Reading IREPS catalogues. Keep the updater Chrome window open.')
                if action=='contracts':
                    reader.navigate('Contracts')
                    def window(first,last):
                        self.state.update(message=f'Reading contracts dated {first} to {last}…')
                        reader.search('---All---',start=first.strftime('%d/%m/%Y'),end=last.strftime('%d/%m/%Y'))
                        try:return reader.all_rows('contracts')
                        except RuntimeError as exc:
                            if last<=first or not any(text in str(exc) for text in ('repeated a page','pagination stopped','row count mismatch')):raise
                            middle=first+(last-first)//2
                            return window(first,middle)+window(middle+timedelta(days=1),last)
                    first,last=date.fromisoformat(start),date.fromisoformat(end);entries=[]
                    while first<=last:
                        until=min(first+timedelta(days=59),last)
                        entries.extend(window(first,until));first=until+timedelta(days=1)
                    rows=[];seen=set()
                    for entry in entries:
                        c=entry['cells']
                        if len(c)!=9:raise ValueError('Contract list columns changed. No candidates imported.')
                        identity=tuple(c[:8])
                        if identity in seen:continue
                        seen.add(identity)
                        raw=dict(zip(['Contract No.','Contract Date','Contractor','Category','Asset Id','CP Start','CP End','Status','Actions'],c));raw['source']=page.url
                        fields=candidate_fields(raw)
                        for field in ('start','end'):
                            if fields.get(field):
                                try:fields[field]=parse_day(fields[field])
                                except ValueError:fields[field]=''
                        rows.append({'raw':raw,'fields':fields})
                    previous=self.store.evidence('__workspace__','web_contract_candidates')
                    old=previous[-1] if previous else {}
                    merged={r['raw'].get('Contract No.'):r for r in old.get('rows',[])}
                    merged.update({r['raw'].get('Contract No.'):r for r in rows})
                    self.store.save_evidence('__workspace__','web_contract_candidates',{'rows':list(merged.values()),'from_date':min(start,old.get('from_date',start)),'to_date':end,'warnings':reader.warnings,'complete':not reader.warnings})
                    self.state.update(phase='complete',message=f'{len(rows)} contract candidates collected. Verify the exact asset before using a candidate.',error=None)
                    try:page.close()
                    except Exception:pass
                    return
                endpoint=json.loads((self.engine.STATE/'browser.json').read_text())['port']
                from rp.browser_runtime import browser_reader_runtime
                node, playwright_module = browser_reader_runtime()
                job={'id':uuid.uuid4().hex,'action':{'collect':'scheduled','history':'closed','contracts':'contracts','workbook-history':'closed'}[action]}
                if action!='collect':job.update(from_date=start,to_date=end)
                if action=='workbook-history':job['metadata_only']=True
                if action=='history':
                    plan=self.library().history_plan(end)
                    enrichment=self.library().bid_enrichment_plan([lot for _,lot in self.store.current_lots()])
                    start=min(start,enrichment['from_date'] or start)
                    library_scan=self.library().start_scan(start,end)
                    job.update(library=True,known_catalogues=plan['known_catalogues'],refresh_after=plan['refresh_after'],
                               from_date=start,detail_lots=enrichment['detail_lots'],
                               force_catalogues=sorted(set(plan['force_catalogues']+enrichment['force_catalogues'])))
                checkpoint_path=None
                if action=='history' and not job.get('library'):
                    identity={k:v for k,v in job.items() if k!='id'}
                    checkpoint_path=self.userdir/'history-checkpoints'/(hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()+'.json')
                    try:
                        if datetime.now().timestamp()-checkpoint_path.stat().st_mtime<86400:
                            job['resume']=json.loads(checkpoint_path.read_text(encoding='utf-8'))
                    except (OSError,ValueError):pass
                marker='deskflow-'+uuid.uuid4().hex
                page.evaluate('(value) => {window.name=value}',marker)
                payload={'playwright_module':str(playwright_module),'endpoint':f'http://127.0.0.1:{endpoint}','marker':marker,'job':job}
                rows=None;failure='';collection_report={}
                if self.cancelled.is_set():raise ValueError('Collection cancelled before reading further catalogues.')
                with tempfile.TemporaryFile(mode='w+',encoding='utf-8') as diagnostics:
                    self.process=subprocess.Popen([str(node),str(Path(__file__).parent/'rp/collect.mjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=diagnostics,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    timer=threading.Timer(7200 if action=='history' else 1800,self.process.kill);timer.start()
                    try:
                        self.process.stdin.write(json.dumps(payload));self.process.stdin.close()
                        for line in self.process.stdout:
                            event=json.loads(line)
                            if event.get('type')=='progress':
                                self.state.update(message=event['message'])
                                if event.get('report'):collection_report=event['report']
                                if library_scan and event.get('report'):self.library().scan_progress(library_scan,event['report'])
                                if checkpoint_path and event.get('checkpoint'):
                                    checkpoint_path.parent.mkdir(parents=True,exist_ok=True)
                                    temporary=checkpoint_path.with_suffix('.tmp')
                                    temporary.write_text(json.dumps(event['checkpoint']),encoding='utf-8');temporary.replace(checkpoint_path)
                            elif event.get('type')=='catalogue' and library_scan:
                                self.library().save_catalogue(library_scan,event['catalogue'],event['fingerprint'],event['rows'])
                            elif event.get('type')=='result':rows=event['rows']
                            elif event.get('type')=='error':failure=event['message']
                        code=self.process.wait()
                    finally:
                        timer.cancel()
                        if self.process.poll() is None:self.process.kill();self.process.wait()
                        self.process=None
                if self.cancelled.is_set():raise ValueError('Collection stopped. Completed history catalogues are saved; resume to continue.' if library_scan else 'Collection cancelled. No partial results were imported.')
                if code or rows is None:raise ValueError(failure or 'Collection stopped or timed out. Retry the scan; saved evidence is retained.')
                if action=='collect':
                    for row in rows:row['start']=parse_day(row['start'])
                    ids=[self.store.save_lot(row) for row in rows]
                    self.store.save_evidence('__workspace__','scheduled_snapshot',{'ids':ids,'complete':True,'count':len(rows),'collected_at':datetime.now().isoformat(),'scope':{'source':'IREPS scheduled catalogues'}})
                elif action=='workbook-history':
                    valid=[];undated=[]
                    for row in rows:
                        try:valid.append({**row,'date':parse_day(row['date'])})
                        except ValueError:undated.append(row)
                    self.store.save_evidence('__workspace__','workbook_ireps_history',{
                        'from_date':start,'to_date':end,'complete':not undated,'rows':valid,'undated_rows':undated,
                        'collected_at':datetime.now().isoformat(),
                        'scope':'All visible closed catalogue lot metadata; RP registers not decrypted; bid viewers not opened.'
                    },start+'|'+end)
                    if undated:
                        self.state.update(phase='needs_evidence',message=f'{len(valid)} dated catalogue records saved; {len(undated)} records retained separately because IREPS did not show their auction start date.',error=None)
                        page.close();page=None;return
                elif action=='history':
                    self.library().finish_scan(library_scan,collection_report)
                    for row in rows:row['date']=parse_day(row['date'])
                    for key,lot in self.store.current_lots():
                        for row in self.library().auctions_for(lot):
                            if row['outcome'] in ('Sold','Rejected','No Bids','Withdrawn'):
                                existing=self.store.evidence(key,'auction')
                                changed=not any(all(a.get(field)==row.get(field) for field in ('date','catalogue','lot','outcome','bid_rate','rate_unit')) for a in existing)
                                self.store.save_evidence(key,'auction',{**row,'captured':True,'previous_lot':row['lot']},row['date']+'|'+row.get('catalogue','')+'|'+row['lot'])
                                previous=self.store.evidence(key,'inputs')
                                if previous and changed:
                                    inputs=previous[-1]
                                    same=reviewed_continuation_matches(lot,self.store.evidence(key,'auction'),inputs)
                                    self.store.save_evidence(key,'inputs',{**inputs,'identity_verified':same})
                    prior=self.store.evidence('__workspace__','history_snapshot')
                    first=min(start,prior[-1]['from_date']) if prior and prior[-1].get('library_version')==1 else start
                    self.store.save_evidence('__workspace__','history_snapshot',{'from_date':first,'to_date':end,'complete':True,'count':self.library().status()['auction_records'],'collected_at':datetime.now().isoformat(),'reader_version':2,'library_version':1,'coverage':collection_report,'lot_codes':[lot['lot'] for _,lot in self.store.current_lots()],'scanned_from':start})
                else:
                    self.store.save_evidence('__workspace__','web_contract_candidates',{'rows':[{'raw':r,'fields':candidate_fields(r)} for r in rows]})
                checked=len(collection_report['visited']) if collection_report else None
                scope=f' from {checked} catalogues' if checked is not None else ''
                missing=sum(bool(row.get('bid_details_unavailable')) for row in rows)
                warning=f' {missing} sold outcome(s) need accepted rate and awardee verified separately.' if missing else ''
                if history_base:warning+=f' Older verified history retained; refreshed since {start}.'
                self.state.update(phase='complete',message=f'{len(rows)} records collected{scope}. Review the exact asset, dates and sources before calculating.'+warning,error=None)
                if checkpoint_path:checkpoint_path.unlink(missing_ok=True)
                try:page.close()
                except Exception:pass
                page=None
        except Exception as exc:
            if library_scan:self.library().scan_progress(library_scan,collection_report or {},interrupted=True)
            if action=='history' and retry_connection(exc,attempt,self.cancelled.is_set()):
                self.state.update(phase='reconnecting',message='Browser connection interrupted. Reconnecting to resume the saved history checkpoint…',error=None)
                if not self.cancelled.wait(2):return self.work(action,start,end,history_base,attempt+1)
            self.state.update(phase='error',error=str(exc).split('Call log:')[0][:1400],message='Collection stopped. Previously saved evidence is retained.')

    def excel(self,action,data):
        with self.lock:
            if self.thread and self.thread.is_alive():raise ValueError('Finish collection before preparing Excel changes.')
            if action=='excel-save':
                token=data.get('preview_id');entry=self.previews.get(token)
                if not entry:raise ValueError('Prepare a fresh workbook preview.')
                key,revision,preview=entry
                if self.detail(key)['revision']!=revision:raise ValueError('Evidence changed after preview. Prepare a fresh workbook preview.')
                backup=preview.commit()
                self._workbook_digests.pop(preview.path,None)
                with self.store.connect() as c:self.store.log(c,'excel_saved',{'key':key,'workbook':str(preview.path),'backup':backup})
                self.store.save_evidence(key,'workbook_write',{'revision':revision,'ready':True,'workbook':str(preview.path),'digest':digest(preview.path)})
                preview.close();del self.previews[token]
                return {'message':'Workbook saved and verified. A backup of the original is retained.','backup':public_text(backup)}
            record=self.detail(data['key']) if action=='excel-preview' else None
            if record:
                if record.get('revision')!=data.get('revision'):raise ValueError('Evidence changed. Reopen the lot before preparing Excel.')
                group=family_group(record['inputs'].get('family'))
                target=WorkbookSelection(self.userdir/'workbooks.json').target('D:/ANIL/UK',group)
                previous=self.store.evidence(record['key'],'auction')
                result=calculate(record['lot'],previous,record['contract'],record['inputs'])
                if not record['result'].get('ready'):raise ValueError('Complete the missing evidence and save the calculation before writing this row.')
                result.justification=public_text(result.justification)
                item={'lot':record['lot'],'inputs':record['inputs'],'contract':record['contract'],'last':max(previous,key=lambda a:a['date']) if previous else {},'result':result}
                for old in self.previews.values():old[2].close()
                self.previews.clear()
                preview=WorkbookPreview(target,group,[item],allow_existing=True);token=uuid.uuid4().hex
                self.previews[token]=(record['key'],record['revision'],preview)
                return {'preview_id':token,'workbook':SPECS[group]['name'],'sheet':preview.sheet,'changes':public_text(preview.changes),'message':'Review these cell changes, then save the workbook. A backup is created automatically.'}
            rows=[]
            for key,_ in self.store.current_lots():
                r=self.detail(key);lot,c,events,inputs=r['lot'],r['contract'],r['auctions'],r['inputs'];result=r['result'];ready=result.get('ready')
                last=max(events,key=lambda a:a['date']) if events else {};sold=[a for a in events if a['outcome']=='Sold'];s=max(sold,key=lambda a:a['date']) if sold else {}
                values=[lot.get('start'),inputs.get('family',''),lot['lot'],lot.get('station',''),lot.get('rate_unit',''),float(result['rp']) if ready else None,public_text(result.get('justification') or result.get('missing')),float(result['base']) if ready else None,float(result['multiplier']) if ready else None,'Proposed value ready' if ready else 'Pending evidence',last.get('date',''),last.get('outcome',''),s.get('bid_rate',''),s.get('awardee',''),c.get('status',''),c.get('award_date',''),c.get('start',''),c.get('end',''),c.get('closed',''),lot.get('catalogue',''),public_text(inputs.get('benchmark_source','')+'; '+lot.get('source','')),'2026-10-17']
                rows.append({'values':values,'formula':result.get('formula','') if ready else '', 'expected':result.get('rp','')})
            folder=self.userdir/'Reviews';folder.mkdir(exist_ok=True)
            output=folder/('Deskflow-value-review-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.xlsx')
            from rp.export_review import export_review
            export_review(output, rows)
            return {'filename':output.name,'content':base64.b64encode(output.read_bytes()).decode(),'message':'Excel review created. Missing evidence remains visible and uncalculated.'}
