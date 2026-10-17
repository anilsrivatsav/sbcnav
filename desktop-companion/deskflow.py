"""Persistent RP review workspace served by the existing desktop connection."""
import json, os, subprocess, threading, uuid, hashlib, tempfile
from pathlib import Path
from datetime import datetime, date, timedelta
from dataclasses import asdict
from rp.store import Store
from rp.rules import calculate, FAMILIES, UNITS, CONTRACT_STATES
from rp.standard_conditions import review, annual_fee
from rp.contract_fields import candidate_fields
from rp.rules import Result
from rp.workbooks import WorkbookSelection, family_group, SPECS
from rp.review import WorkbookPreview, digest
import re, base64

def public_text(value):
    if isinstance(value,str):
        return re.sub(r'\bRP\b','value',re.sub(r'reserve[- ]price','proposed value',value,flags=re.I),flags=re.I).replace('RPAssistant','Deskflow')
    if isinstance(value,(list,tuple)):return [public_text(v) for v in value]
    if isinstance(value,dict):return {k:public_text(v) for k,v in value.items()}
    return value

def parse_day(value):
    text=str(value or '').strip().split(' ')[0]
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%d.%m.%Y','%d-%m-%y'):
        try:return datetime.strptime(text,fmt).date().isoformat()
        except ValueError:pass
    raise ValueError('Unrecognised date: '+text)

class Deskflow:
    def __init__(self, updater, engine, playwright, reader):
        self.updater,self.engine,self.playwright,self.reader=updater,engine,playwright,reader
        self.store=Store(Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'RPAssistant'/'rpassistant.sqlite')
        self.lock=threading.RLock();self.thread=None
        self.cancelled=threading.Event();self.process=None
        self.previews={}
        self.userdir=self.store.path.parent
        self.state={'phase':'ready','message':'Collect pending lots, then review their evidence.','error':None}
        previous=self.store.evidence('__workspace__','workbook_update')
        if previous:
            report=previous[-1];pending=len(report.get('pending',[]))
            self.state.update(phase='needs_evidence' if pending else 'complete',message=f"Last update: {len(report.get('saved',[]))} local workbooks saved. {report.get('calculated',0)} values calculated; {pending} rows need evidence. See workbook notes.")

    def result(self,lot,auctions,contract,inputs):
        if not inputs.get('conditions_reviewed'):
            return {'ready':False,'missing':'Review SCC v2.0 and the applicable catalogue/special conditions.'}
        if contract.get('status') in ('Foreclosed','Not signed','Not commenced','Cancelled (reason unknown)') and not contract.get('termination_source'):
            return {'ready':False,'missing':'Record the cancellation/termination decision and reason. A deadline or a cancelled label alone does not establish the cause.'}
        return asdict(calculate(lot,auctions,contract,inputs))

    def detail(self,key):
        lot=dict(self.store.current_lots()).get(key)
        if lot is None:raise ValueError('Collect or select a current pending lot.')
        auctions=self.store.evidence(key,'auction');c=self.store.evidence(key,'contract');i=self.store.evidence(key,'inputs')
        contract=c[-1] if c else {};inputs=i[-1] if i else {}
        revision=hashlib.sha256(json.dumps([lot,auctions,contract,inputs],sort_keys=True).encode()).hexdigest()
        return {'key':key,'revision':revision,'lot':lot,'auctions':auctions,'contract':contract,'inputs':inputs,
                'result':self.result(lot,auctions,contract,inputs),'conditions':review(contract)}

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

    def progress(self):
        # The page receives only progress, never the collected commercial records.
        return {**self.state,'busy':bool(self.thread and self.thread.is_alive()),
                'updater_busy':self.updater.snapshot()['busy']}

    def update_workbooks(self):
        try:
            while self.updater.snapshot()['busy']:
                self.state.update(phase='waiting',message='Waiting for the earnings updater to finish…',error=None)
                if self.cancelled.wait(1):raise ValueError('Update stopped.')
            end=date.today().isoformat()
            for action in ('collect','history','contracts'):
                self.work(action,'2023-01-01',end)
                if self.state.get('error'):return
            self.write_workbooks()
        except Exception as exc:
            self.state.update(phase='error',message='Workbook update stopped. Backups and saved evidence are retained.',error=str(exc)[:1400])

    def write_workbooks(self):
        from rp.excel_io import _sheet_path,_strings,_text,Q
        from lxml import etree as E
        import zipfile
        self.state.update(phase='writing',message='Calculating supported values and saving the local workbooks…',error=None)
        selection=WorkbookSelection(self.userdir/'workbooks.json')
        targets={group:selection.target('D:/ANIL/UK',group) for group in SPECS}
        identities={}
        for group,path in targets.items():
            lotcol,catcol={'commercial':('L','N'),'parcel':('Q','R'),'catering':('N','P')}[group]
            with zipfile.ZipFile(path) as z:
                ss=_strings(z);root=E.fromstring(z.read(_sheet_path(z,SPECS[group]['sheet'])))
                for row in root.find(Q('sheetData')):
                    cs={re.match('[A-Z]+',c.get('r'))[0]:c for c in row}
                    identity=(_text(cs.get(lotcol),ss),_text(cs.get(catcol),ss))
                    if identity[0]:identities.setdefault(identity,set()).add(group)
        batches={g:[] for g in SPECS};ready=0;pending=[];revisions={}
        for key,lot in self.store.current_lots():
            record=self.detail(key);revisions[key]=record['revision'];inputs=dict(record['inputs'])
            family=inputs.get('family') or ('Parcel' if lot.get('category','').startswith('Parcel') else 'Catering / MPS' if any(v in lot.get('category','') for v in ('Catering','Multipurpose')) else 'Food truck' if 'food truck' in lot.get('description','').lower() else 'Parking / Pay & Use')
            inputs['family']=family
            matches=identities.get((lot['lot'],lot.get('catalogue','')),set())
            if len(matches)>1:raise ValueError('The same lot and catalogue appear in multiple workbooks; resolve the duplicate before updating.')
            group=next(iter(matches)) if matches else family_group(family)
            result=Result(**record['result'])
            if result.ready:ready+=1;result.justification=public_text(result.justification)
            else:
                pending.append({'lot':lot['lot'],'reason':public_text(result.missing)})
                result.missing=public_text(result.missing)
            events=record['auctions']
            batches[group].append({'lot':lot,'inputs':inputs,'contract':record['contract'],'last':max(events,key=lambda a:a['date']) if events else {},'result':result})
        staged=[];saved=[]
        try:
            for group,items in batches.items():
                if items:staged.append(WorkbookPreview(targets[group],group,items,allow_existing=True,preserve_pending=True))
            for key,revision in revisions.items():
                if self.detail(key)['revision']!=revision:raise ValueError('Evidence changed during calculation; retry the workbook update.')
            for preview in staged:
                preview.check_lock()
                if digest(preview.path)!=preview.original_hash:raise ValueError('A workbook changed during calculation; retry the update.')
            for preview in staged:
                backup=preview.commit();saved.append({'workbook':str(preview.path),'backup':backup,'changes':len(preview.changes)})
                with self.store.connect() as c:self.store.log(c,'excel_saved',saved[-1])
            report={'saved':saved,'calculated':ready,'pending':pending,'at':datetime.now().isoformat()}
            self.store.save_evidence('__workspace__','workbook_update',report)
            message=f'{len(saved)} local workbooks saved with backups. {ready} values calculated.'
            if pending:message+=f' {len(pending)} rows need evidence; existing values were preserved. Reasons are saved in the workbooks.'
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
        if action not in ('collect','history','contracts'):raise ValueError('Unknown Deskflow action.')
        # Serialize browser ownership with MCDO without changing its payment pipeline.
        with self.updater.lock, self.lock:
            if self.updater.snapshot()['busy'] or (self.thread and self.thread.is_alive()):raise ValueError('A collection is already running. Wait for it to finish.')
            start=parse_day(data.get('from_date') or '2023-01-01');end=parse_day(data.get('to_date') or date.today().isoformat())
            if start>end:raise ValueError('History start must not follow its end.')
            self.cancelled.clear()
            self.state.update(phase='login',message='Sign in with your digital token in the updater Chrome window.',error=None)
            self.thread=threading.Thread(target=self.work,args=(action,start,end),daemon=True);self.thread.start()
        return self.snapshot()

    def work(self,action,start,end):
        page=None
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
                    self.store.save_evidence('__workspace__','web_contract_candidates',{'rows':rows,'from_date':start,'to_date':end,'warnings':reader.warnings})
                    self.state.update(phase='complete',message=f'{len(rows)} contract candidates collected. Verify the exact asset before using a candidate.',error=None)
                    page.close();return
                endpoint=json.loads((self.engine.STATE/'browser.json').read_text())['port']
                runtime=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node'
                job={'id':uuid.uuid4().hex,'action':{'collect':'scheduled','history':'closed','contracts':'contracts'}[action]}
                if action!='collect':job.update(from_date=start,to_date=end)
                if action=='history':
                    job['lots']=list({lot['lot'] for _,lot in self.store.current_lots()})
                    if not job['lots']:raise ValueError('Collect pending lots first.')
                marker='deskflow-'+uuid.uuid4().hex
                page.evaluate('(value) => {window.name=value}',marker)
                payload={'modules':str(runtime/'node_modules'),'endpoint':f'http://127.0.0.1:{endpoint}','marker':marker,'job':job}
                rows=None;failure=''
                if self.cancelled.is_set():raise ValueError('Collection cancelled before reading further catalogues.')
                with tempfile.TemporaryFile(mode='w+',encoding='utf-8') as diagnostics:
                    self.process=subprocess.Popen([str(runtime/'bin/node.exe'),str(Path(__file__).parent/'rp/collect.mjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=diagnostics,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    timer=threading.Timer(1800,self.process.kill);timer.start()
                    try:
                        self.process.stdin.write(json.dumps(payload));self.process.stdin.close()
                        for line in self.process.stdout:
                            event=json.loads(line)
                            if event.get('type')=='progress':self.state.update(message=event['message'])
                            elif event.get('type')=='result':rows=event['rows']
                            elif event.get('type')=='error':failure=event['message']
                        code=self.process.wait()
                    finally:
                        timer.cancel()
                        if self.process.poll() is None:self.process.kill();self.process.wait()
                        self.process=None
                if self.cancelled.is_set():raise ValueError('Collection cancelled. No partial results were imported.')
                if code or rows is None:raise ValueError(failure or 'Collection stopped or timed out. Retry the scan; saved evidence is retained.')
                if action=='collect':
                    for row in rows:row['start']=parse_day(row['start'])
                    ids=[self.store.save_lot(row) for row in rows]
                    self.store.save_evidence('__workspace__','scheduled_snapshot',{'ids':ids,'collected_at':datetime.now().isoformat(),'scope':{'source':'IREPS scheduled catalogues'}})
                elif action=='history':
                    for row in rows:row['date']=parse_day(row['date'])
                    for key,lot in self.store.current_lots():
                        for row in rows:
                            if row['lot']==lot['lot']:
                                existing=self.store.evidence(key,'auction')
                                changed=not any(all(a.get(field)==row.get(field) for field in ('date','catalogue','lot','outcome','bid_rate','rate_unit')) for a in existing)
                                self.store.save_evidence(key,'auction',{**row,'captured':True,'previous_lot':row['lot']},row['date']+'|'+row.get('catalogue','')+'|'+row['lot'])
                                previous=self.store.evidence(key,'inputs')
                                if previous and changed:self.store.save_evidence(key,'inputs',{**previous[-1],'identity_verified':False})
                else:
                    self.store.save_evidence('__workspace__','web_contract_candidates',{'rows':[{'raw':r,'fields':candidate_fields(r)} for r in rows]})
                self.state.update(phase='complete',message=f'{len(rows)} records collected. Review the exact asset, dates and sources before calculating.',error=None)
                page.close();page=None
        except Exception as exc:
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
                with self.store.connect() as c:self.store.log(c,'excel_saved',{'key':key,'workbook':str(preview.path),'backup':backup})
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
            runtime=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node'
            folder=self.userdir/'Reviews';folder.mkdir(exist_ok=True)
            output=folder/('Deskflow-value-review-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.xlsx')
            with tempfile.TemporaryDirectory() as temp:
                request=Path(temp)/'export.json';request.write_text(json.dumps({'module_root':str(runtime/'node_modules'),'output':str(output),'rows':rows}),encoding='utf-8')
                proc=subprocess.run([str(runtime/'bin/node.exe'),str(Path(__file__).parent/'rp/excel_export.mjs'),str(request)],capture_output=True,text=True,timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if proc.returncode:raise ValueError('The Excel review could not be created: '+proc.stderr[-700:])
            return {'filename':output.name,'content':base64.b64encode(output.read_bytes()).decode(),'message':'Excel review created. Missing evidence remains visible and uncalculated.'}
