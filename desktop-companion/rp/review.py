"""Stage exact workbook bytes for a review, then commit only that reviewed version."""
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime
import hashlib, shutil, zipfile, os, uuid
from lxml import etree as E
from .excel_io import append_existing, _sheet_path, _strings, _text, Q
from .workbooks import SPECS

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def cells(path,sheet):
    from openpyxl.formula.translate import Translator
    with zipfile.ZipFile(path)as z:
        ss=_strings(z);root=E.fromstring(z.read(_sheet_path(z,sheet)));out={}
        entries=root.findall('.//'+Q('sheetData')+'/'+Q('row')+'/'+Q('c'))
        shared={}
        for c in entries:
            f=c.find(Q('f'))
            if f is not None and f.get('t')=='shared'and f.text:shared[f.get('si')]=(c.get('r'),'='+f.text)
        for c in entries:
            f=c.find(Q('f'));address=c.get('r')
            if f is None:out[address]=_text(c,ss)
            elif f.text:out[address]='='+f.text
            elif f.get('t')=='shared':
                if f.get('si')not in shared:raise ValueError('Shared formula has no master at '+address)
                origin,formula=shared[f.get('si')]
                out[address]=Translator(formula,origin=origin).translate_formula(address)
            else:out[address]='Excel formula '+str(dict(f.attrib))+'; cached value: '+str(_text(c,ss))
        return out

class WorkbookPreview:
    def __init__(self,path,group,records,allow_existing=False,preserve_pending=False):
        self.path=Path(path);self.sheet=SPECS[group]['sheet'];self.temp=TemporaryDirectory(prefix='deskflow-review-')
        try:
            self.original_hash=digest(self.path)
            self.staged=Path(self.temp.name)/self.path.name;shutil.copy2(self.path,self.staged)
            if digest(self.staged)!=self.original_hash:raise ValueError('Workbook changed while preparing the preview. Try again.')
            before=cells(self.staged,self.sheet)
            append_existing(self.staged,group,records,allow_existing=allow_existing,preserve_pending=preserve_pending)
            after=cells(self.staged,self.sheet)
            self.changes=[(address,before.get(address,''),after.get(address,''))for address in sorted(set(before)|set(after),key=lambda a:(int(''.join(filter(str.isdigit,a))),len(''.join(filter(str.isalpha,a))),a))if before.get(address,'')!=after.get(address,'')and not str(after.get(address,'')).startswith('RPAssistant:')]
            self.staged_hash=digest(self.staged)
        except Exception:self.close();raise
    def check_lock(self):
        if self.path.with_name('~$'+self.path.name).exists():raise ValueError('Close this workbook in Excel before preparing or saving changes: '+self.path.name)
    def commit(self):
        self.check_lock()
        if digest(self.path)!=self.original_hash:raise ValueError('Workbook changed after preview. Create a new preview before saving.')
        if digest(self.staged)!=self.staged_hash:raise ValueError('Preview contents changed. Create a new preview.')
        backup=self.path.parent/'Backups'/('DeskFlow-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))/self.path.name
        backup.parent.mkdir(parents=True);shutil.copy2(self.path,backup)
        candidate=self.path.with_name('.deskflow-'+uuid.uuid4().hex+'.xlsx')
        try:
            shutil.copy2(self.staged,candidate);self.check_lock()
            if digest(self.path)!=self.original_hash:raise ValueError('Workbook changed during save. No update applied.')
            os.replace(candidate,self.path)
        finally:
            if candidate.exists():candidate.unlink()
        return str(backup)
    def close(self):self.temp.cleanup()

def comparable_rows(lot,rows,term=''):
    """Rank suggestions only; a text match never verifies an asset's identity."""
    import re
    tokens=lambda s:set(re.findall(r'[A-Z0-9]+',str(s).upper()))
    lot_tokens=tokens(lot.get('lot',''));scope=tokens(lot.get('description',''))
    stop={'SBC','MSS','THE','AND','FOR','OF','AT','26','2026','27','2027','1','2'}
    keys=(lot_tokens|scope)-stop;ranked=[]
    for row in rows:
        text=row['text'];candidate=tokens(text)
        if term and term.casefold()not in text.casefold():continue
        score=len(keys&candidate)
        if lot.get('lot') and lot['lot'].casefold()in text.casefold():score+=100
        if score or term:ranked.append((score,row))
    return [dict(row,match_score=score)for score,row in sorted(ranked,key=lambda x:(-x[0],x[1]['file'],x[1]['row']))[:150]]
