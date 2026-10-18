"""Read history and append application-owned rows without re-exporting old workbooks."""
import json, zipfile, shutil, copy, re, posixpath, hashlib, time
from datetime import datetime, date
from pathlib import Path
from lxml import etree as E
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main';REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships';Q=lambda n:f'{{{NS}}}{n}'

def history_rows(folder,paths=None):
    import openpyxl
    out=[]
    for group,file,sheet in [('commercial','Prk PnU.xlsx','RP history source'),('catering','E_AUCTION CATG JUn 2025 EA.xlsx','Sheet1'),('parcel','RP Parcles Temp.xlsx','Sheet1 (2)')]:
        p=Path(paths[group])if paths else Path(folder)/file
        if not p.exists():raise ValueError('History workbook not found: '+str(p))
        w=openpyxl.load_workbook(p,read_only=True,data_only=True)
        if sheet not in w.sheetnames:sheet='Table1' if 'Table1'in w.sheetnames else w.sheetnames[0]
        for i,r in enumerate(w[sheet].values,1):
            if any(x is not None for x in r):out.append({'file':str(p),'sheet':sheet,'row':i,'group':group,'cells':{openpyxl.utils.get_column_letter(j):str(x) for j,x in enumerate(r,1)if x is not None},'text':' | '.join(str(x)for x in r[:26]if x is not None)})
        w.close()
    return out

def _sheet_path(z,name):
    wb=E.fromstring(z.read('xl/workbook.xml'));rid=next(s.get(f'{{{REL}}}id')for s in wb.find(Q('sheets'))if s.get('name')==name)
    rs=E.fromstring(z.read('xl/_rels/workbook.xml.rels'));t=next(r.get('Target')for r in rs if r.get('Id')==rid)
    return t.lstrip('/')if t.startswith('/')else posixpath.normpath('xl/'+t)

def _strings(z):
    if'xl/sharedStrings.xml'not in z.namelist():return[]
    return [''.join(t.itertext())for t in E.fromstring(z.read('xl/sharedStrings.xml'))]

def _text(c,ss):
    if c is None:return''
    if c.get('t')=='s':return ss[int(c.find(Q('v')).text)]
    if c.get('t')=='inlineStr':return''.join(c.find(Q('is')).itertext())
    v=c.find(Q('v'));return v.text if v is not None else''

def append_existing(path, group, records, allow_existing=False, preserve_pending=False):
    """Update only app-owned rows; refuse collisions with a user's prior records."""
    path=Path(path)
    from .identifiers import references
    from .workbooks import validate
    validate(path,group)
    lock=path.with_name('~$'+path.name)
    if lock.exists():raise ValueError('Close this workbook in Excel before updating it: '+path.name)
    sn='Table1'if group=='commercial'else'Sheet1 (2)'if group=='parcel'else'Sheet1'
    lotcol,catcol,rpcol,notecol,basecol,factorcol = (('L','N','E','F','R','S')if group=='commercial'else('Q','R','M','P','Y','Z')if group=='parcel'else('N','P','L','M','W','X'))
    with zipfile.ZipFile(path)as z:
        sp=_sheet_path(z,sn);tree=E.fromstring(z.read(sp));sd=tree.find(Q('sheetData'));ss=_strings(z)
        seen={};counts={};owned={};metadata_col=None;reviewed_existing=set()
        for row in sd:
            cs={re.match('[A-Z]+',c.get('r'))[0]:c for c in row};key=(_text(cs.get(lotcol),ss),_text(cs.get(catcol),ss));seen[key]=row
            counts[key]=counts.get(key,0)+1
            for col,c in cs.items():
                marker=_text(c,ss)
                if marker.startswith('RPAssistant:'):owned[marker]=row;metadata_col=col
        def record_marker(r):return 'RPAssistant:'+hashlib.sha256((r['lot'].get('catalogue','')+'|'+r['lot']['lot']).encode()).hexdigest()
        duplicate=[r['lot']['lot']for r in records if(r['lot']['lot'],r['lot'].get('catalogue',''))in seen and record_marker(r)not in owned]
        if duplicate and not allow_existing:raise ValueError('These lots already exist in '+sn+'; no rows overwritten: '+', '.join(duplicate[:5])+'. Export the review workbook to compare them.')
        if allow_existing:
            from .rules import canonical_unit
            for record in records:
                key=(record['lot']['lot'],record['lot'].get('catalogue',''));marker=record_marker(record)
                if key in seen and marker not in owned:
                    if counts[key]!=1:raise ValueError('Multiple existing rows match this exact lot and catalogue. Resolve the duplicate before saving.')
                    row=seen[key];cs={re.match('[A-Z]+',c.get('r'))[0]:c for c in row}
                    unit=_text(cs.get('G' if group=='commercial' else 'S' if group=='parcel' else 'Q'),ss)
                    if unit and canonical_unit(unit)!=canonical_unit(record['lot'].get('rate_unit')):raise ValueError('The existing row uses a different rate unit. No value was overwritten.')
                    owned[marker]=row;reviewed_existing.add(int(row.get('r')))
        if group=='commercial':
            header=next((r for r in sd if r.get('r')=='5'),None)
            if header is None or _text(next((c for c in header if c.get('r')=='E5'),None),ss)!='RP':raise ValueError('Commercial sheet layout has changed. Export a review workbook rather than guessing the target columns.')
        if len(tree.findall('.//'+Q('tablePart')))>1:raise ValueError('More than one table exists on this sheet. Review export is available; table extension needs a specific target.')
        def column_number(s):
            value=0
            for ch in s:value=value*26+ord(ch)-64
            return value
        def column_name(n):
            value=''
            while n:n,a=divmod(n-1,26);value=chr(65+a)+value
            return value
        original_end=re.match('[A-Z]+',tree.find(Q('dimension')).get('ref').split(':')[-1])[0]
        if metadata_col is None:
            metadata_col=column_name(max(column_number(original_end),column_number(factorcol))+1)
            cols=tree.find(Q('cols'))
            if cols is None:
                cols=E.Element(Q('cols'));tree.insert(list(tree).index(sd),cols)
            E.SubElement(cols,Q('col'),min=str(column_number(metadata_col)),max=str(column_number(metadata_col)),hidden='1',width='10',customWidth='1')
        last=max(int(r.get('r'))for r in sd);templates={}
        for row in reversed(list(sd)):
            for c in row:
                col=re.match('[A-Z]+',c.get('r'))[0]
                if col not in templates:templates[col]=c.get('s')
            if len(templates)>=26:break
        def cell(row,col,value,formula=None,style=None):
            c=E.SubElement(row,Q('c'),r=col+row.get('r'))
            if style or templates.get(col):c.set('s',style or templates[col])
            if formula:
                E.SubElement(c,Q('f')).text=formula.lstrip('=');E.SubElement(c,Q('v')).text=str(value);return
            if value is None or value=='':return
            if isinstance(value,(int,float)):E.SubElement(c,Q('v')).text=str(value)
            else:c.set('t','inlineStr');ins=E.SubElement(c,Q('is'));E.SubElement(ins,Q('t')).text=str(value)
        modified_rows=set()
        for record in records:
            lot=record['lot'];calc=record['result'];marker=record_marker(record)
            if marker in owned:row=owned[marker];rn=int(row.get('r'));modified_rows.add(rn);reviewed_existing.add(rn)
            else:last+=1;rn=last;row=E.SubElement(sd,Q('row'),r=str(rn))
            row.set('ht',str(max(90,(len(calc.justification or calc.missing)//70+1)*15)));row.set('customHeight','1')
            formula=calc.formula.replace('H{r}',basecol+str(rn)).replace('I{r}',factorcol+str(rn))if calc.ready else None
            d=lot.get('start','')[:10]
            try:day=(date.fromisoformat(d)-date(1899,12,30)).days
            except ValueError:day=d
            rate=float(calc.rp)if calc.ready else None
            if group=='commercial':
                fields={'A':day,'B':record['inputs']['family'],'C':lot.get('station',''),'D':lot.get('description',''),'E':rate,'F':calc.justification if calc.ready else'Value pending: '+calc.missing,'G':lot.get('rate_unit',''),'H':record.get('contract',{}).get('lar',''),'I':record.get('last',{}).get('outcome',''),'J':record.get('contract',{}).get('status',''),'K':record['inputs']['family'],'L':lot['lot'],'N':lot.get('catalogue',''),'P':'Proposed value (app)','Q':('Calculated from verified evidence' if calc.ready else 'Pending evidence; existing value is not reverified')+'; see Deskflow audit history','R':float(calc.base)if calc.ready else None,'S':float(calc.multiplier)if calc.ready else None}
            elif group=='parcel':fields={'A':day,'C':lot.get('train')or references(lot)['train'],'F':lot['lot'],'G':record.get('contract',{}).get('lar',''),'M':rate,'N':lot.get('trips_days',''),'P':calc.justification if calc.ready else'Value pending: '+calc.missing,'Q':lot['lot'],'R':lot.get('catalogue',''),'S':lot.get('rate_unit',''),'U':'Value pending','V':lot.get('description',''),'W':lot.get('category',''),'Y':float(calc.base)if calc.ready else None,'Z':float(calc.multiplier)if calc.ready else None}
            else:fields={'A':day,'C':lot['lot'],'D':lot.get('station',''),'F':record['inputs']['family'],'J':record['inputs'].get('finance_fee',''),'L':rate,'M':calc.justification if calc.ready else'Value pending: '+calc.missing,'N':lot['lot'],'O':'Value pending','P':lot.get('catalogue',''),'Q':lot.get('rate_unit',''),'R':lot.get('trips_days',''),'U':lot.get('category',''),'V':'DeskFlow proposal; not fixed on IREPS','W':float(calc.base)if calc.ready else None,'X':float(calc.multiplier)if calc.ready else None}
            fields[metadata_col]=marker
            if rn in reviewed_existing:
                fields={k:v for k,v in fields.items() if k in (rpcol,notecol,basecol,factorcol,metadata_col)}
                if preserve_pending and not calc.ready:
                    # An unresolved refresh must never erase the user's existing value or workings.
                    oldnote=_text(next((c for c in row if c.get('r')==notecol+str(rn)),None),ss)
                    original=oldnote.split('\nDeskflow update:')[0]
                    fields={notecol:original+'\nDeskflow update: '+calc.missing,metadata_col:marker}
            for c in list(row):
                if re.match('[A-Z]+',c.get('r'))[0]in fields:row.remove(c)
            for col,value in sorted(fields.items(),key=lambda x:(len(x[0]),x[0])):cell(row,col,value,formula if col==rpcol else None,templates.get(rpcol)if col in(basecol,factorcol)else None)
            row[:]=sorted(row,key=lambda c:column_number(re.match('[A-Z]+',c.get('r'))[0]))
        endcol=column_name(max(column_number(original_end),column_number(metadata_col)));tree.find(Q('dimension')).set('ref','A1:'+endcol+str(last))
        changes={sp:E.tostring(tree,encoding='utf-8',xml_declaration=True)}
        for tp in tree.findall('.//'+Q('tablePart')):
            rs=E.fromstring(z.read(posixpath.dirname(sp)+'/_rels/'+posixpath.basename(sp)+'.rels'));target=next(r.get('Target')for r in rs if r.get('Id')==tp.get(f'{{{REL}}}id'));p=target.lstrip('/')if target.startswith('/')else posixpath.normpath(posixpath.dirname(sp)+'/'+target);table=E.fromstring(z.read(p));ref=table.get('ref');endcol=re.match('[A-Z]+',ref.split(':')[-1])[0];table.set('ref',ref.split(':')[0]+':'+endcol+str(last));af=table.find(Q('autoFilter'))
            if af is not None:af.set('ref',table.get('ref'))
            changes[p]=E.tostring(table,encoding='utf-8',xml_declaration=True)
        backup=path.parent/'Backups'/('RPAssistant-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'));backup.mkdir(parents=True);shutil.copy2(path,backup/path.name)
        temp=path.with_name(path.stem+'.rpassistant-staged.xlsx')
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED)as out:
            for item in z.infolist():out.writestr(copy.copy(item),changes.get(item.filename,z.read(item.filename)))
    with zipfile.ZipFile(backup/path.name)as before,zipfile.ZipFile(temp)as after:
        for name in before.namelist():
            if name not in changes:assert before.read(name)==after.read(name),name
        old=list(E.fromstring(before.read(sp)).find(Q('sheetData')));new=list(E.fromstring(after.read(sp)).find(Q('sheetData')))
        for a,b in zip(old,new):
            if int(a.get('r'))not in modified_rows:assert E.tostring(a)==E.tostring(b)
    for attempt in range(6):
        try:temp.replace(path);break
        except PermissionError:
            if attempt==5:raise ValueError('Excel or another program is holding this workbook open. Close it and retry. The original and backup are retained.')
            time.sleep(.2*(attempt+1))
    return str(backup/path.name)
