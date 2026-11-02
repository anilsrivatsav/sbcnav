"""Archive supplied monthly MCDO workbooks without changing any workbook bytes."""
import calendar
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from io import BytesIO
import re
from zipfile import ZipFile

from openpyxl import load_workbook
from mcdo.monthly import ASSETS, POLICIES, period_dates


def parse_reference(content, filename, expected_period):
    if not filename.lower().endswith('.xlsx') or len(content)>1024*1024:
        raise ValueError('Supply an MCDO .xlsx workbook no larger than 1 MB.')
    with ZipFile(BytesIO(content)) as archive:
        if sum(item.file_size for item in archive.infolist())>16*1024*1024:
            raise ValueError('MCDO workbook expands beyond the supported size.')
    book=load_workbook(BytesIO(content),data_only=True)
    try:
        earnings=book['Immediate earning '];policy=book['Policywise '];assets=book['Idle Assets ']
        if str(earnings['B10'].value).strip()!='SBC' or str(policy['B8'].value).strip()!='SBC':
            raise ValueError('The supplied workbook does not contain the expected SBC rows.')
        match=re.search(r'upto\s+([A-Za-z]+)\s+(20\d{2})',str(earnings['A3'].value),re.I)
        month=next((m for m in range(1,13) if match and calendar.month_name[m].lower()==match[1].lower()),None)
        if not month or f'{match[2]}-{month:02d}'!=expected_period:
            raise ValueError('The workbook reporting month differs from the selected month.')
        _,_,end,fy=period_dates(expected_period)
        position=re.search(r'(\d{2})\.(\d{2})\.(\d{4})',str(assets['A13'].value))
        if not position:raise ValueError('The supplied asset position date is missing.')
        position=f'{position[3]}-{position[2]}-{position[1]}'
        def number(sheet,row,col):
            value=sheet.cell(row,col).value
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not Decimal(str(value)).is_finite():
                raise ValueError(f'{sheet.title} {sheet.cell(row,col).coordinate}: numeric value/cached formula result missing.')
            return value
        keys=['previous_crore','current_crore','proportionate_target_crore','cumulative_crore',
              'proportionate_variance_percent','annual_target_crore','annual_variance_percent']
        e={k:str(number(earnings,10,col)) for col,k in enumerate(keys,3)}
        asset_rows={name:{key:number(assets,row,col) for row,key in [(16,'registered'),(17,'leased'),(18,'idle'),(19,'idle_percent'),(20,'newly_created')]}
                    for col,name in enumerate(ASSETS,2)}
        totals={key:number(assets,row,11) for row,key in [(16,'registered'),(17,'leased'),(18,'idle'),(19,'idle_percent'),(20,'newly_created')]}
        sha=hashlib.sha256(content).hexdigest()
        configuration={'annual_target_crore':e['annual_target_crore'],
                       'target_source':f'Supplied {filename}, Immediate earning H10.',
                       'earnings_complete':True,'earnings_checked_through':end.isoformat(),
                       'earnings_note':'Supplied completed monthly MCDO; original workbook values preserved unchanged.',
                       'asset_position_date':position,'asset_source':f'Supplied {filename}, Idle Assets B16:K20; SHA256 {sha}.',
                       'assets':{name:{k:int(v) for k,v in values.items() if k in ('registered','leased','newly_created')} for name,values in asset_rows.items()},
                       'assets_verified':True}
        return {'origin':'supplied_reference','period':expected_period,'financial_year':fy,
                'month_name':calendar.month_name[month],'month_end':end.isoformat(),
                'configuration':configuration,'earnings':e,
                'policies_crore':{code:str(number(policy,8,col)) for col,code in enumerate(POLICIES,3)},
                'assets':asset_rows,'asset_totals':totals,'row_count':0,
                'source':{'filename':filename,'import_id':sha,'imported_at':datetime.now(timezone.utc).isoformat()},
                'issues':[],'pending':[],'notes':['Original supplied monthly workbook. Downloaded bytes and all figures are preserved without recalculation.'],
                'fingerprint':sha,'status':'Ready to Download'}
    finally:book.close()
