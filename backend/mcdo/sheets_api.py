"""Google Sheets API transport. Fixed source IDs; no browser or token credentials."""
import os
from io import BytesIO
from urllib.parse import quote
from openpyxl import Workbook
from openpyxl.utils.datetime import from_excel

SOURCES = {
    'earnings': {'id': '1Sprl2AehF_yMaV1HMrbkMfT-0BWq6XDZx8yZlnnqnfw', 'title': 'Main Sheet', 'columns': 28},
    'master': {'id': '17VH0P5ENgUxYfh42sB6c4GPM21esBSbHAdXtC0fj6SI', 'title': 'E Auction', 'columns': 37},
}

class Sheets:
    def __init__(self):
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        path = os.environ.get('MCDO_GOOGLE_CREDENTIALS')
        if not path:
            raise RuntimeError('Google Sheets connection is not configured on Oracle.')
        credentials = service_account.Credentials.from_service_account_file(path, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        self.session = AuthorizedSession(credentials)

    def request(self, method, source, suffix='', **kwargs):
        response = self.session.request(method, 'https://sheets.googleapis.com/v4/spreadsheets/' + SOURCES[source]['id'] + suffix, timeout=90, **kwargs)
        if not response.ok:
            raise RuntimeError(f'Google Sheets {source} request failed ({response.status_code}); verify connection and edit access.')
        return response.json()

    def read(self, source, title=None, columns=None):
        spec = {**SOURCES[source]}
        if title:spec['title']=title
        if columns:spec['columns']=columns
        meta = self.request('GET', source, params={'fields': 'sheets.properties'})
        props = next((s['properties'] for s in meta['sheets'] if s['properties']['title'] == spec['title']), None)
        if not props:
            raise RuntimeError('Required sheet missing: ' + spec['title'])
        rows = props['gridProperties']['rowCount']
        if rows * spec['columns'] > 200000:
            raise RuntimeError('Source is larger than the configured sync limit; review before importing.')
        from openpyxl.utils import get_column_letter
        data = self.request('GET', source, params={'includeGridData': 'true', 'ranges': f"'{spec['title']}'!A1:{get_column_letter(spec['columns'])}{rows}", 'fields': 'sheets(data.rowData.values(userEnteredValue,effectiveValue,effectiveFormat.numberFormat,dataValidation))'})
        values = data['sheets'][0].get('data', [{}])[0].get('rowData', [])
        grid = [r.get('values', []) + [{}] * max(0, spec['columns'] - len(r.get('values', []))) for r in values]
        return {'properties': props, 'grid': grid}

    def batch(self, source, requests):
        if requests:
            return self.request('POST', source, ':batchUpdate', json={'requests': requests})

    def patches(self, source, snapshot, patches, formats=(), status=None):
        sid = snapshot['properties']['sheetId']
        capacity = snapshot['properties']['gridProperties']['rowCount']
        required = max([r - 1 + len(rows) for r, c, rows in patches] + [capacity])
        requests = []
        if required > capacity:
            requests.append({'appendDimension': {'sheetId': sid, 'dimension': 'ROWS', 'length': required-capacity}})
        for r, c, rows in patches:
            requests.append({'updateCells': {'start': {'sheetId': sid, 'rowIndex': r-1, 'columnIndex': c-1}, 'rows': [{'values': row} for row in rows], 'fields': 'userEnteredValue'}})
        # Copy formatting only; original formulas, filters and validation survive API writes.
        from openpyxl.utils.cell import range_boundaries
        for owner, exemplar, destination in formats:
            if owner != source:
                continue
            def rect(a1):
                c1,r1,c2,r2 = range_boundaries(a1)
                return {'sheetId':sid,'startRowIndex':r1-1,'endRowIndex':r2,'startColumnIndex':c1-1,'endColumnIndex':c2}
            requests.append({'copyPaste': {'source':rect(exemplar),'destination':rect(destination),'pasteType':'PASTE_FORMAT'}})
        if status is not None:
            meta = self.request('GET', source, params={'fields':'sheets.properties'})
            existing = next((s['properties'] for s in meta['sheets'] if s['properties']['title']=='IREPS Status Sync'), None)
            if not existing:
                result = self.batch(source, [{'addSheet':{'properties':{'title':'IREPS Status Sync'}}}])
                existing = result['replies'][0]['addSheet']['properties']
            status_id = existing['sheetId']
            if len(status) > existing['gridProperties']['rowCount']:
                requests.append({'appendDimension':{'sheetId':status_id,'dimension':'ROWS','length':len(status)-existing['gridProperties']['rowCount']}})
            # Clear stale status values in the managed ten-column report only.
            requests.append({'updateCells':{'range':{'sheetId':status_id,'startColumnIndex':0,'endColumnIndex':10},'rows':[{'values':r} for r in status],'fields':'userEnteredValue'}})
        # Google batches are atomic per workbook. Cross-workbook recovery checks planned values.
        return self.batch(source, requests)

def computed_workbook(source, snapshot):
    book = Workbook()
    sheet = book.active
    sheet.title = SOURCES[source]['title']
    for i,row in enumerate(snapshot['grid'],1):
        for j,cell in enumerate(row,1):
            value = cell.get('effectiveValue', cell.get('userEnteredValue', {}))
            if 'errorValue' in value:
                sheet.cell(i,j,'#'+value['errorValue'].get('type','ERROR'))
                continue
            val = value.get('numberValue',value.get('stringValue',value.get('boolValue')))
            date_column = source=='master' and (j in (6,13,14) or 18<=j<=36)
            if (date_column or cell.get('effectiveFormat',{}).get('numberFormat',{}).get('type') in ('DATE','DATE_TIME')) and isinstance(val,(int,float)):
                val = from_excel(val)
            if val is not None:
                target = sheet.cell(i,j,val)
                if isinstance(val,str) and val.startswith('='):
                    target.data_type = 's'
    stream = BytesIO(); book.save(stream)
    return stream.getvalue()
