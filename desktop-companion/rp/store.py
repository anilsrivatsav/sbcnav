import json, sqlite3
from contextlib import contextmanager
from decimal import Decimal
from datetime import datetime
from pathlib import Path

class Store:
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS lots(id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS evidence(lot_id TEXT, kind TEXT, evidence_key TEXT, data TEXT NOT NULL, PRIMARY KEY(lot_id,kind,evidence_key));
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at TEXT NOT NULL, action TEXT NOT NULL, data TEXT NOT NULL);''')
    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=10)
        try:
            with c:yield c
        finally:c.close()
    def log(self, c, action, data): c.execute('INSERT INTO audit(at,action,data) VALUES(?,?,?)',(datetime.now().isoformat(timespec='seconds'),action,json.dumps(data)))
    @staticmethod
    def lot_id(lot): return lot.get('catalogue','')+'|'+lot['lot']
    def save_lot(self, lot):
        key=self.lot_id(lot)
        with self.connect() as c:
            existing=c.execute('SELECT data FROM lots WHERE id=?',(key,)).fetchone()
            data=json.loads(existing[0]) if existing else {}; data.update(lot)
            if existing:
                old=json.loads(existing[0])
                if any(k in lot and old.get(k)!=lot.get(k)for k in('description','rate_unit','category','trips_days','start','station','train')):
                    row=c.execute("SELECT data FROM evidence WHERE lot_id=? AND kind='inputs' AND evidence_key='current'",(key,)).fetchone()
                    if row:
                        inputs=json.loads(row[0]);inputs['identity_verified']=False;c.execute("UPDATE evidence SET data=? WHERE lot_id=? AND kind='inputs' AND evidence_key='current'",(json.dumps(inputs),key));self.log(c,'identity_review_required',{'id':key})
            c.execute('INSERT OR REPLACE INTO lots VALUES(?,?)',(key,json.dumps(data))); self.log(c,'lot_saved',{'id':key})
        return key
    def lots(self):
        with self.connect() as c: return [(k,json.loads(v))for k,v in c.execute('SELECT id,data FROM lots ORDER BY id')]
    def current_lots(self):
        snapshot=self.evidence('__workspace__','scheduled_snapshot')
        if not snapshot:return self.lots()
        ids=set(snapshot[-1]['ids']);return[(k,l)for k,l in self.lots()if k in ids]
    def evidence(self, key, kind):
        with self.connect() as c: return [json.loads(v[0])for v in c.execute('SELECT data FROM evidence WHERE lot_id=? AND kind=? ORDER BY evidence_key',(key,kind))]
    def save_evidence(self, key, kind, data, evidence_key='current'):
        with self.connect() as c:
            if kind=='auction'and data.get('captured')and not data.get('awardee'):
                prior=c.execute('SELECT data FROM evidence WHERE lot_id=? AND kind=? AND evidence_key=?',(key,kind,evidence_key)).fetchone()
                if prior:
                    old=json.loads(prior[0])
                    if data.get('bid_details_unavailable') and old.get('outcome')==data.get('outcome')=='Sold' and old.get('rate_unit')==data.get('rate_unit'):
                        # An outcome-only refresh must not erase separately sourced bid evidence.
                        data={**data,**{field:old[field] for field in ('bid_rate','bid_value','bid_source','awardee','awardee_source') if old.get(field) not in (None,'')}}
                    try:same_rate=Decimal(str(old.get('bid_rate')).replace(',',''))==Decimal(str(data.get('bid_rate')).replace(',',''))
                    except Exception:same_rate=False
                    if same_rate and old.get('outcome')==data.get('outcome')=='Sold'and old.get('rate_unit')==data.get('rate_unit')and old.get('awardee'):
                        data={**data,'awardee':old['awardee'],'awardee_source':old.get('awardee_source',old.get('source',''))}
            c.execute('INSERT OR REPLACE INTO evidence VALUES(?,?,?,?)',(key,kind,evidence_key,json.dumps(data))); self.log(c,kind+'_saved',{'lot_id':key,'key':evidence_key,'data':data})
    def audit(self):
        with self.connect() as c: return c.execute('SELECT at,action,data FROM audit ORDER BY id DESC LIMIT 300').fetchall()
