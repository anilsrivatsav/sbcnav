"""Durable source library. Coverage and reviewed proposals are separate from raw evidence."""
import hashlib
import json
import re
import sqlite3
import uuid
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from lxml import etree as E
from .excel_io import _strings, _text, _sheet_path, Q

VERSION = 1
POLICY_VERSION = 'workbook-rules-2026-10-17'

def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))

def fingerprint(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()

def code(value):
    return str(value or '').strip().casefold()

def scope(lot):
    return fingerprint([str(lot.get('description', '')).strip(), lot.get('rate_unit', '')])

def day(value):
    value = str(value or '').strip().split('T')[0].split(' ')[0]
    for fmt in ('%Y-%m-%d', '%d-%m-%y', '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y', '%d.%m.%y'):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return ''

class HistoryLibrary:
    def __init__(self, store):
        self.store = store
        with store.connect() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.executescript('''
            CREATE TABLE IF NOT EXISTS df_workbooks(book TEXT, revision TEXT, path TEXT, imported_at TEXT,
                active INTEGER, manifest TEXT, PRIMARY KEY(book,revision));
            CREATE TABLE IF NOT EXISTS df_workbook_rows(book TEXT, revision TEXT, sheet TEXT, row_number INTEGER,
                data TEXT, search TEXT, auction_date TEXT, PRIMARY KEY(book,revision,sheet,row_number));
            CREATE INDEX IF NOT EXISTS df_workbook_search ON df_workbook_rows(book,revision,auction_date);
            CREATE TABLE IF NOT EXISTS df_catalogues(catalogue TEXT PRIMARY KEY, fingerprint TEXT,
                checked_at TEXT, row_count INTEGER, detail_level TEXT);
            CREATE TABLE IF NOT EXISTS df_auctions(identity TEXT PRIMARY KEY, catalogue TEXT, lot TEXT,
                auction_date TEXT, data TEXT, revision TEXT, active INTEGER DEFAULT 1);
            CREATE INDEX IF NOT EXISTS df_auction_lot ON df_auctions(lot,auction_date);
            CREATE TABLE IF NOT EXISTS df_auction_versions(identity TEXT, revision TEXT, captured_at TEXT,
                data TEXT, PRIMARY KEY(identity,revision));
            CREATE TABLE IF NOT EXISTS df_scans(id TEXT PRIMARY KEY, from_date TEXT, to_date TEXT,
                status TEXT, expected INTEGER, visited TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS df_asset_links(current_code TEXT, previous_code TEXT, scope TEXT,
                source TEXT, verified_at TEXT, PRIMARY KEY(current_code,previous_code,scope));
            CREATE TABLE IF NOT EXISTS df_proposals(lot_key TEXT PRIMARY KEY, revision TEXT,
                result TEXT, status TEXT, reviewed_at TEXT, saved_at TEXT, workbook_digests TEXT);
            ''')

    def import_workbooks(self, paths):
        """Read every populated row, retaining formulas and original workbook coordinates."""
        reports = []
        for book, path in paths.items():
            path = Path(path)
            raw = path.read_bytes()
            revision = hashlib.sha256(raw).hexdigest()
            with self.store.connect() as c:
                prior = c.execute('SELECT manifest FROM df_workbooks WHERE book=? AND revision=?', (book, revision)).fetchone()
            if prior:
                with self.store.connect() as c:
                    c.execute('UPDATE df_workbooks SET active=(revision=?) WHERE book=?', (revision, book))
                reports.append(json.loads(prior[0]))
                continue
            rows = []
            with zipfile.ZipFile(path) as z:
                strings = _strings(z)
                workbook = E.fromstring(z.read('xl/workbook.xml'))
                styles = E.fromstring(z.read('xl/styles.xml'))
                formats = {int(n.get('numFmtId')): n.get('formatCode', '') for n in styles.findall('.//' + Q('numFmt'))}
                from openpyxl.styles.numbers import is_date_format, BUILTIN_FORMATS
                from openpyxl.utils.datetime import from_excel, WINDOWS_EPOCH, MAC_EPOCH
                properties = workbook.find(Q('workbookPr'))
                epoch = MAC_EPOCH if properties is not None and properties.get('date1904') in ('1', 'true') else WINDOWS_EPOCH
                cell_formats=styles.find(Q('cellXfs'))
                date_styles = {i for i, xf in enumerate(cell_formats if cell_formats is not None else [])
                    if is_date_format(formats.get(int(xf.get('numFmtId', '0')), BUILTIN_FORMATS.get(int(xf.get('numFmtId', '0')), '')))}
                for sheet in workbook.find(Q('sheets')):
                    name = sheet.get('name')
                    root = E.fromstring(z.read(_sheet_path(z, name)))
                    for row in root.find(Q('sheetData')):
                        cells = {}
                        for cell in row:
                            address = cell.get('r')
                            if not address:
                                continue
                            value = _text(cell, strings)
                            formula = cell.find(Q('f'))
                            if value == '' and formula is None and cell.find(Q('v')) is None and cell.find(Q('is')) is None:
                                continue
                            item = {'value': value, 'type': cell.get('t', 'n'), 'style': cell.get('s')}
                            if formula is not None:
                                item['formula'] = formula.text or ''
                                item['formula_attributes'] = dict(formula.attrib)
                            if value and int(cell.get('s', '0')) in date_styles:
                                try:
                                    item['date'] = from_excel(float(value), epoch).isoformat()[:10]
                                except (ValueError, TypeError, OverflowError, AttributeError):
                                    pass
                            cells[re.match('[A-Z]+', address)[0]] = item
                        if not cells:
                            continue
                        first = cells.get('A', {})
                        auction_date = first.get('date') or day(first.get('value'))
                        record = {'cells': cells, 'hidden': row.get('hidden') == '1',
                            'file': str(path), 'sheet': name, 'row': int(row.get('r')),
                            'revision': revision, 'book': book}
                        search = ' '.join(str(v.get('value') or '') for v in cells.values()).casefold()
                        rows.append((book, revision, name, record['row'], encoded(record), search, auction_date))
            if hashlib.sha256(path.read_bytes()).hexdigest() != revision:
                raise ValueError('Workbook changed during baseline import. Retry: ' + path.name)
            manifest = {'book': book, 'file': str(path), 'sha256': revision, 'rows': len(rows),
                'sheets': len({r[2] for r in rows}), 'imported_at': datetime.now().isoformat()}
            with self.store.connect() as c:
                c.execute('UPDATE df_workbooks SET active=0 WHERE book=?', (book,))
                c.execute('INSERT INTO df_workbooks VALUES(?,?,?,?,?,?)', (book, revision, str(path), manifest['imported_at'], 1, encoded(manifest)))
                c.executemany('INSERT INTO df_workbook_rows VALUES(?,?,?,?,?,?,?)', rows)
                self.store.log(c, 'workbook_baseline_imported', manifest)
            reports.append(manifest)
        return reports

    def migrate_evidence(self):
        """Seed reusable evidence without upgrading old partial scans to complete coverage."""
        with self.store.connect() as c:
            records = c.execute("SELECT kind,data FROM evidence WHERE kind IN ('auction','workbook_ireps_history')").fetchall()
        by_catalogue = {}
        for kind, raw in records:
            value = json.loads(raw)
            for row in value.get('rows', []) if kind == 'workbook_ireps_history' else [value]:
                if row.get('catalogue') and row.get('lot') and day(row.get('date') or row.get('start')):
                    by_catalogue.setdefault(row['catalogue'], []).append(row)
        with self.store.connect() as c:
            for catalogue, rows in by_catalogue.items():
                for row in rows:
                    identity=fingerprint([catalogue,code(row['lot']),day(row.get('date') or row.get('start'))])
                    if not c.execute('SELECT 1 FROM df_auctions WHERE identity=?',(identity,)).fetchone():
                        self._save_event(c, catalogue, row)

    def earliest_date(self):
        with self.store.connect() as c:
            result = c.execute('SELECT min(r.auction_date) FROM df_workbook_rows r JOIN df_workbooks w '
                'ON w.book=r.book AND w.revision=r.revision WHERE w.active=1 AND r.auction_date>=? AND r.auction_date<=?',
                ('2022-01-01', date.today().isoformat())).fetchone()[0]
        # Commercial earning e-auctions began in 2022. A workbook containing
        # only newer assets must not narrow the one-time IREPS backfill.
        return min(result or '2022-01-01','2022-01-01')

    def search_workbooks(self, query, limit=20):
        needle = str(query or '').strip().casefold()
        if not needle:
            return []
        with self.store.connect() as c:
            result = c.execute('SELECT r.data FROM df_workbook_rows r JOIN df_workbooks w '
                'ON w.book=r.book AND w.revision=r.revision WHERE w.active=1 AND instr(r.search,?)>0 '
                'ORDER BY r.auction_date DESC,r.book,r.sheet,r.row_number LIMIT ?', (needle, min(100, limit))).fetchall()
        return [json.loads(r[0]) for r in result]

    def start_scan(self, first, last):
        if not day(first) or not day(last) or first > last or last > date.today().isoformat():
            raise ValueError('Invalid history coverage dates.')
        identity = fingerprint([first, last, VERSION])
        with self.store.connect() as c:
            c.execute('INSERT INTO df_scans VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
                "status='running',updated_at=excluded.updated_at", (identity, first, last, 'running', None, '[]', datetime.now().isoformat()))
        return identity

    def known_catalogues(self):
        with self.store.connect() as c:
            return dict(c.execute("SELECT catalogue,fingerprint FROM df_catalogues WHERE detail_level='full'"))

    def _save_event(self, c, catalogue, row):
        value = dict(row)
        value['date'] = day(value.get('date') or value.get('start'))
        if not value['date'] or not value.get('lot') or not value.get('source'):
            raise ValueError('Historical lot requires its source, identity and actual auction date.')
        if value.get('catalogue') and value['catalogue'] != catalogue:
            raise ValueError('Historical lot does not belong to this catalogue.')
        value['catalogue'] = catalogue
        value['captured'] = True
        identity = fingerprint([catalogue, code(value['lot']), value['date']])
        prior = c.execute('SELECT data FROM df_auctions WHERE identity=?', (identity,)).fetchone()
        if prior:
            old = json.loads(prior[0])
            if old.get('outcome') == value.get('outcome') and old.get('rate_unit') == value.get('rate_unit'):
                for field in ('bid_rate', 'bid_value', 'bid_source', 'awardee', 'awardee_source'):
                    if value.get(field) in ('', None) and old.get(field) not in ('', None):
                        value[field] = old[field]
        revision = fingerprint(value)
        raw = encoded(value)
        c.execute('INSERT OR IGNORE INTO df_auction_versions VALUES(?,?,?,?)', (identity, revision, datetime.now().isoformat(), raw))
        c.execute('INSERT INTO df_auctions VALUES(?,?,?,?,?,?,1) ON CONFLICT(identity) DO UPDATE SET '
            'data=excluded.data,revision=excluded.revision,active=1', (identity, catalogue, code(value['lot']), value['date'], raw, revision))

    def save_catalogue(self, scan, catalogue, listing_fingerprint, rows):
        if not catalogue or not listing_fingerprint or not isinstance(rows, list):
            raise ValueError('Invalid catalogue checkpoint.')
        with self.store.connect() as c:
            if not c.execute('SELECT 1 FROM df_scans WHERE id=?', (scan,)).fetchone():
                raise ValueError('History scan is unavailable.')
            c.execute('UPDATE df_auctions SET active=0 WHERE catalogue=?', (catalogue,))
            for row in rows:
                self._save_event(c, catalogue, row)
            c.execute('INSERT OR REPLACE INTO df_catalogues VALUES(?,?,?,?,?)',
                (catalogue, listing_fingerprint, datetime.now().isoformat(), len(rows), 'full'))
            self.store.log(c, 'history_catalogue_checkpoint', {'scan': scan, 'catalogue': catalogue, 'rows': len(rows)})

    def finish_scan(self, scan, report):
        visited = report.get('visited', [])
        expected = report.get('expected')
        if not report.get('complete') or type(expected) is not int or expected != len(visited) or len(set(visited)) != expected:
            raise ValueError('Incomplete catalogue coverage. Completed checkpoints are retained.')
        with self.store.connect() as c:
            if visited:
                present = {r[0] for r in c.execute('SELECT catalogue FROM df_catalogues')}
                if not set(visited).issubset(present):
                    raise ValueError('Catalogue checkpoint is missing; coverage is incomplete.')
            c.execute("UPDATE df_scans SET status='complete',expected=?,visited=?,updated_at=? WHERE id=?",
                (expected, encoded(visited), datetime.now().isoformat(), scan))

    def scan_progress(self, scan, report, interrupted=False):
        with self.store.connect() as c:
            c.execute('UPDATE df_scans SET status=?,expected=COALESCE(?,expected),visited=?,updated_at=? WHERE id=?',
                ('interrupted' if interrupted else 'running', report.get('expected'), encoded(report.get('visited', [])), datetime.now().isoformat(), scan))

    def history_plan(self, end=None):
        last = end or date.today().isoformat()
        first = self.earliest_date()
        with self.store.connect() as c:
            complete = c.execute("SELECT from_date,to_date FROM df_scans WHERE status='complete' ORDER BY from_date,to_date").fetchall()
        through = first
        found = False
        for start, stop in complete:
            if start <= through:
                through = max(through, stop)
                found = True
        if found:
            first = max(first, (date.fromisoformat(through) - timedelta(days=30)).isoformat())
        followups = self.outcome_followups(last)
        due = [row for row in followups if row['date'] <= last]
        if due:
            first = min(first, min(row['date'] for row in due))
        return {'from_date': first, 'to_date': last, 'initial': not found,
                'known_catalogues': self.known_catalogues(),
                'force_catalogues': sorted({row['catalogue'] for row in due}),
                'refresh_after': (date.fromisoformat(last) - timedelta(days=30)).isoformat()}

    def outcome_followups(self, end=None):
        """Keep scheduled and unresolved lots eligible even after the overlap expires.

        A lot leaving the RP-pending schedule, or its date passing, is not an
        outcome. Only an explicitly collected final result settles this queue.
        """
        final = {'Sold', 'Rejected', 'No Bids', 'Withdrawn'}
        with self.store.connect() as c:
            events = [json.loads(row[0]) for row in c.execute('SELECT data FROM df_auctions WHERE active=1')]
        settled = {(row['catalogue'], code(row['lot']), row['date']) for row in events if row.get('outcome') in final}
        pending = {}
        for row in events + [lot for _, lot in self.store.lots()]:
            when = day(row.get('date') or row.get('start'))
            catalogue = row.get('catalogue', '')
            name = row.get('lot', '')
            identity = (catalogue, code(name), when)
            if when and catalogue and name and identity not in settled:
                pending[identity] = {'catalogue': catalogue, 'lot': name, 'date': when}
        return sorted(pending.values(), key=lambda row: (row['date'], row['catalogue'], row['lot']))

    def coverage(self):
        first=self.earliest_date()
        through=None
        with self.store.connect() as c:
            ranges=c.execute("SELECT from_date,to_date FROM df_scans WHERE status='complete' ORDER BY from_date,to_date").fetchall()
        for start,stop in ranges:
            boundary=first if through is None else (date.fromisoformat(through)+timedelta(days=1)).isoformat()
            if start<=boundary and stop>=first:through=max(through or first,stop)
        return {'from_date':first,'through':through,'complete':bool(through and through>=date.today().isoformat())}

    def auctions_for(self, lot):
        names = {code(lot.get('lot'))}
        with self.store.connect() as c:
            names.update(r[0] for r in c.execute('SELECT previous_code FROM df_asset_links WHERE current_code=? AND scope=?', (code(lot.get('lot')), scope(lot))))
            result = []
            for name in names:
                result.extend(json.loads(r[0]) for r in c.execute('SELECT data FROM df_auctions WHERE lot=? AND active=1 AND auction_date<? ORDER BY auction_date,catalogue', (name, lot.get('start', ''))))
        for row in result:
            row['previous_lot'] = row['lot']
        return sorted(result, key=lambda r: (r['date'], r['catalogue'], r['lot']))

    def bid_enrichment_plan(self, lots):
        catalogues=set();dates=[];codes=set()
        for lot in lots:
            codes.add(lot['lot'])
            for row in self.auctions_for(lot):
                codes.add(row['lot'])
                if row.get('outcome')=='Sold' and not row.get('bid_rate') and not row.get('bid_details_unavailable'):
                    catalogues.add(row['catalogue']);dates.append(row['date'])
        return {'force_catalogues':sorted(catalogues),'detail_lots':sorted(codes),'from_date':min(dates) if dates else None}

    def link_asset(self, lot, previous, source):
        if not str(source or '').strip() or code(previous) == code(lot['lot']):
            raise ValueError('Verify a different previous lot code and record its scope evidence.')
        with self.store.connect() as c:
            if not c.execute('SELECT 1 FROM df_auctions WHERE lot=?', (code(previous),)).fetchone():
                raise ValueError('Collect the previous lot in the history library before linking it.')
            c.execute('INSERT OR REPLACE INTO df_asset_links VALUES(?,?,?,?,?)',
                (code(lot['lot']), code(previous), scope(lot), str(source).strip(), datetime.now().isoformat()))
            self.store.log(c, 'asset_link_verified', {'current': lot['lot'], 'previous': previous, 'source': source, 'scope': scope(lot)})

    def proposal(self, key, revision, result):
        identity = fingerprint([revision, result, POLICY_VERSION])
        with self.store.connect() as c:
            prior = c.execute('SELECT revision,status,reviewed_at,saved_at,workbook_digests FROM df_proposals WHERE lot_key=?', (key,)).fetchone()
            retained = prior and prior[0] == identity
            state = prior[1] if retained else 'ready_for_review' if result.get('ready') else 'needs_evidence'
            if not retained:
                c.execute('INSERT OR REPLACE INTO df_proposals VALUES(?,?,?,?,?,?,?)', (key, identity, encoded(result), state, None, None, '{}'))
        return {'revision': identity, 'status': state, 'policy_version': POLICY_VERSION,
                'workbook_digests':json.loads(prior[4] or '{}') if retained else {}}

    def review_proposal(self, key, revision, workbook_digests=None):
        with self.store.connect() as c:
            row = c.execute('SELECT revision,result FROM df_proposals WHERE lot_key=?', (key,)).fetchone()
            if not row or row[0] != revision:
                raise ValueError('Proposal changed. Refresh and review the current working.')
            if not json.loads(row[1]).get('ready'):
                raise ValueError('Resolve missing evidence before reviewing the proposal.')
            c.execute("UPDATE df_proposals SET status='reviewed',reviewed_at=?,workbook_digests=? WHERE lot_key=?",
                (datetime.now().isoformat(),encoded(workbook_digests or {}),key))
            self.store.log(c, 'proposal_reviewed', {'key': key, 'revision': revision})

    def mark_saved(self, key, revision):
        with self.store.connect() as c:
            changed = c.execute("UPDATE df_proposals SET status='saved',saved_at=? WHERE lot_key=? AND revision=? AND status IN ('reviewed','saved')",
                (datetime.now().isoformat(), key, revision)).rowcount
            if not changed:
                raise ValueError('Only the reviewed proposal revision can be marked saved.')

    def status(self):
        with self.store.connect() as c:
            books = [json.loads(r[0]) for r in c.execute('SELECT manifest FROM df_workbooks WHERE active=1 ORDER BY book')]
            count = c.execute('SELECT count(*) FROM df_auctions WHERE active=1').fetchone()[0]
            catalogues = c.execute('SELECT count(*) FROM df_catalogues').fetchone()[0]
            scans = [dict(zip(('from_date','to_date','status','expected','updated_at'), r)) for r in c.execute('SELECT from_date,to_date,status,expected,updated_at FROM df_scans ORDER BY updated_at DESC LIMIT 5')]
            states = dict(c.execute('SELECT status,count(*) FROM df_proposals GROUP BY status'))
            missing_bids=c.execute("SELECT count(*) FROM df_auctions WHERE active=1 AND json_extract(data,'$.outcome')='Sold' AND (json_extract(data,'$.bid_rate') IS NULL OR json_extract(data,'$.bid_rate')='')").fetchone()[0]
        followups = self.outcome_followups()
        return {'workbooks': books, 'workbook_rows': sum(b['rows'] for b in books), 'auction_records': count,
                'outcomes_pending': len(followups),
                'outcomes_due': sum(row['date'] <= date.today().isoformat() for row in followups),
                'catalogues_saved': catalogues, 'missing_bid_details':missing_bids, 'coverage':self.coverage(), 'scans': scans, 'proposals': states, 'policy_version': POLICY_VERSION}
