"""Auction Schedule workbook access using the existing Oracle service account."""
import re
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from urllib.parse import quote
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import text
from database import engine
from mcdo.sheets_api import Sheets

WORKBOOK = '1n_aQpueOSE8OYl5y5KW3_NuYFg7Knlw3BYslllEp1zk'
MONTHS = {name: index for index, name in enumerate(('jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'), 1)}
TIMES = {'Parking':'15:00','Parcel':'11:00','Catering':'11:00','MPS':'15:00','Miscellaneous':'12:00','Pay & Use':'15:00','Advertising':'12:00','ATM':'15:00','PMBJAK':'12:00','CLK / SMVB':'15:00','Food truck':'12:00','Other':'12:00'}
FORMATS = {'Parking':('SBC-PRK-EA','SBC-PRK',170),'Parcel':('SBC-Parcel-EA','SBC-PRCL',156),'Catering':('SBC-CATG-EA','SBC-CTG',189),'MPS':('SBC-MPS-EA','SBC-MPS',187),'Miscellaneous':('SBC-Misc-EA','SBC-Misc',136),'Pay & Use':('SBC-PnU-EA','SBC-PnU',75),'Advertising':('SBC-ADVT-EA','SBC-Advt',87),'ATM':('SBC-ATM-EA','SBC-ATM',31),'PMBJAK':('SBC-PMBJAK-EA','SBC-PMBJK',3),'CLK / SMVB':('SBC-CLK-EA','SBC-CLK',68),'Food truck':('SBC-Misc-FT-','SBC-FoodTruck',119)}
_write_lock = Lock()

@contextmanager
def _sync_lock():
    with _write_lock:
        if engine.dialect.name == 'postgresql':
            # Serialize check-and-append across all API workers.
            with engine.begin() as connection:
                connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': 1939091527})
                yield
        else:
            yield

def _sync_id(value):
    try:return str(UUID(str(value)))
    except (ValueError, AttributeError, TypeError):return ''

def _paint_status(sheets, row, status):
    color = {'scheduled':(0.91, 0.97, 0.93), 'cancelled':(1, 0.91, 0.91), 'withdrawn':(1, 0.91, 0.91)}[status]
    _request(sheets, 'POST', ':batchUpdate', json={'requests':[{'repeatCell':{'range':{'sheetId':row['sheetId'],'startRowIndex':row['sheetRow']-1,'endRowIndex':row['sheetRow'],'startColumnIndex':0,'endColumnIndex':6},'cell':{'userEnteredFormat':{'backgroundColor':{'red':color[0],'green':color[1],'blue':color[2]}}},'fields':'userEnteredFormat.backgroundColor'}}]})

def _request(sheets, method, suffix='', **kwargs):
    response = sheets.session.request(method, f'https://sheets.googleapis.com/v4/spreadsheets/{WORKBOOK}{suffix}', timeout=90, **kwargs)
    if not response.ok:
        raise HTTPException(502, f'Auction Schedule Google Sheets request failed ({response.status_code}). Check the Oracle service account access to this workbook.')
    return response.json()

def _month(title):
    match = re.fullmatch(r'\s*([a-z]{3})[a-z]*\s*[\' -]?(\d{2}|\d{4})\s*', title.lower())
    if not match or match[1] not in MONTHS:return -1
    year = int(match[2]); year += 2000 if year < 100 else 0
    return year * 12 + MONTHS[match[1]]

def _date(value):
    value = str(value or '').strip()
    for pattern in ('%Y-%m-%d','%d-%m-%Y','%d/%m/%Y','%d-%b-%Y','%d-%b-%y'):
        try:return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:pass
    return ''

def _time(value):
    value = str(value or '').strip()
    meridiem = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*([AP])\.?M\.?', value, re.I)
    if meridiem:
        hour, minute = int(meridiem[1]), int(meridiem[2] or 0)
        if 1 <= hour <= 12 and minute < 60:
            return f'{(hour % 12 + (12 if meridiem[3].upper() == "P" else 0)):02d}:{minute:02d}'
    if re.fullmatch(r'\d{1,2}(?::\d{2})?', value):
        hour, _, minute = value.partition(':')
        if int(hour) < 24 and int(minute or 0) < 60:return f'{int(hour):02d}:{int(minute or 0):02d}'
    return ''

def _range(title, cells):return quote("'" + title.replace("'", "''") + "'!" + cells, safe='')

def _rows(sheets):
    meta = _request(sheets, 'GET', '?fields=sheets.properties(sheetId,title)')
    tabs = [item['properties'] for item in meta.get('sheets', []) if _month(item.get('properties', {}).get('title', '')) >= 0]
    if not tabs:raise HTTPException(502, 'No monthly Auction Schedule tab was found.')
    tabs.sort(key=lambda item:_month(item['title']))
    params = [('ranges', f"'{tab['title'].replace(chr(39), chr(39)*2)}'!A:G") for tab in tabs]
    response = _request(sheets, 'GET', '/values:batchGet', params=params)
    entries = []
    for tab, value_range in zip(tabs, response.get('valueRanges', [])):
        for row_number, values in enumerate(value_range.get('values', []), 1):
            values = (values + [''] * 7)[:7]
            day, hour = _date(values[0]), _time(values[1])
            if not day or not hour or not values[2]:continue
            status = 'withdrawn' if re.search('withdrawn', values[5], re.I) else 'cancelled' if re.search('cancelled', values[5], re.I) else 'scheduled'
            entries.append({'id':f"sheet-{tab['sheetId']}-{row_number}",'date':day,'time':hour,'category':values[2],'subject':'','scheduleId':values[3],'catalogueId':values[4],'status':status,'source':True,'sheetRow':row_number,'sheetTab':tab['title'],'sheetId':tab['sheetId'],'syncId':_sync_id(values[6])})
    return tabs, entries

def live_schedule():
    sheets = Sheets()
    _, entries = _rows(sheets)
    return entries

def _category(name):
    lower = name.strip().lower()
    if lower.startswith(('park',)):return 'Parking'
    if lower.startswith('parcel'):return 'Parcel'
    if lower.startswith(('catg','catering')):return 'Catering'
    if lower == 'mps':return 'MPS'
    if 'food' in lower and 'truck' in lower:return 'Food truck'
    if lower.startswith(('misc','other')):return 'Miscellaneous'
    if lower.startswith(('pnu','pay')):return 'Pay & Use'
    if lower.startswith(('advt','advertising','ooh')):return 'Advertising'
    if lower == 'atm':return 'ATM'
    if lower.startswith(('pmbjak','pmbjk')):return 'PMBJAK'
    if lower.startswith('clk'):return 'CLK / SMVB'
    return name

def _number(value, kind):
    value = str(value or '')
    if kind == 'schedule':
        found = re.search(r'(?:EA|FT)[-\s]*(\d+)', value, re.I)
        return int(found[1]) if found else 0
    numbers = [int(number) for number in re.findall(r'\d+', value)]
    return max([n for n in numbers if n >= 500 and (n < 2000 or n > 2100)], default=0)

def _identifiers(category, entries, year):
    key = _category(category)
    prefix, catalogue_prefix, floor = FORMATS.get(key, FORMATS['Miscellaneous'])
    sequence = max([floor] + [_number(row['scheduleId'], 'schedule') for row in entries if _category(row['category']) == key]) + 1
    auction = max([1003] + [_number(row['catalogueId'], 'catalogue') for row in entries]) + 1
    suffix = str(year)[-2:]
    schedule = f'{prefix}{sequence}-' + ('F25' if key == 'PMBJAK' else suffix)
    catalogue = f'{catalogue_prefix}-{auction}' + ('' if key in ('PMBJAK','Food truck') else f'-{suffix}')
    return schedule, catalogue

def save_schedule(payload):
    booking = payload.get('booking') if isinstance(payload, dict) else None
    if not isinstance(booking, dict):raise HTTPException(400, 'Invalid auction row.')
    category, status = booking.get('category'), booking.get('status')
    if category not in TIMES or status not in ('scheduled','cancelled','withdrawn'):
        raise HTTPException(400, 'Invalid auction category or status.')
    if _date(booking.get('date')) != booking.get('date') or _time(booking.get('time')) != booking.get('time'):
        raise HTTPException(400, 'Invalid auction date or time.')
    if booking.get('sourceFile'):raise HTTPException(400, 'Imported CSV rows cannot be sent to the linked workbook.')
    sync_id = _sync_id(booking.get('id'))
    with _sync_lock():
        sheets = Sheets()
        tabs, entries = _rows(sheets)
        match = next((row for row in entries if sync_id and row['syncId'] == sync_id), None)
        if match and any(match[key] != booking.get(key) for key in ('category','date','time')):
            raise HTTPException(409, 'The linked sheet row changed. Refresh the schedule and try again.')
        if not match and booking.get('sheetRow') and booking.get('sheetTab'):
            match = next((row for row in entries if row['sheetTab'] == booking['sheetTab'] and row['sheetRow'] == booking['sheetRow']), None)
            if not match or any(match[key] != booking.get(key) for key in ('catalogueId','category','date','time')):
                raise HTTPException(409, 'The linked sheet row changed. Refresh the schedule and try again.')
        elif not match:
            match = next((row for row in entries if row['catalogueId'] == booking.get('catalogueId') and row['date'] == booking['date'] and row['time'] == booking['time'] and row['category'] == category), None)
        if match:
            if match['status'] != status:
                _request(sheets, 'PUT', f"/values/{_range(match['sheetTab'], 'F' + str(match['sheetRow']))}", params={'valueInputOption':'RAW'}, json={'values':[[status.capitalize()]]})
            _paint_status(sheets, match, status)
            return {'row':match['sheetRow'],'tab':match['sheetTab'],'scheduleId':match['scheduleId'],'catalogueId':match['catalogueId'],'syncedAt':datetime.now(timezone.utc).isoformat()}
        if booking.get('source') or status != 'scheduled':
            raise HTTPException(409, 'This source row was not found in the live sheet. Refresh before changing it.')
        if not sync_id:
            raise HTTPException(400, 'Refresh the app before creating an auction row.')
        if booking['time'] != TIMES[category]:
            raise HTTPException(400, 'Invalid time for this auction category.')
        auction = date.fromisoformat(booking['date'])
        today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
        if auction < today + timedelta(days=15) or auction.weekday() >= 5:
            raise HTTPException(409, 'Auction date must be at least 15 days from today and cannot be Saturday or Sunday.')
        holidays = payload.get('holidays', [])
        if any(isinstance(item, dict) and item.get('date') == booking['date'] for item in holidays):
            raise HTTPException(409, 'Auction date is a listed holiday.')
        if any(row['status'] == 'scheduled' and row['date'] == booking['date'] and row['time'] == booking['time'] for row in entries):
            raise HTTPException(409, 'This auction date and time are already booked.')
        automatic_schedule, automatic_catalogue = _identifiers(category, entries, auction.year)
        schedule_id = booking.get('scheduleId') if booking.get('manualScheduleId') else automatic_schedule
        catalogue_id = booking.get('catalogueId') if booking.get('manualCatalogueId') else automatic_catalogue
        if not isinstance(schedule_id, str) or not isinstance(catalogue_id, str) or len(schedule_id) > 100 or len(catalogue_id) > 100 or not _number(schedule_id, 'schedule') or not _number(catalogue_id, 'catalogue'):
            raise HTTPException(409, 'Invalid EA Schedule ID or Catalogue ID.')
        if any(_category(row['category']) == _category(category) and _number(row['scheduleId'], 'schedule') == _number(schedule_id, 'schedule') for row in entries):
            raise HTTPException(409, 'EA Schedule ID is already used for this category.')
        if any(_number(row['catalogueId'], 'catalogue') == _number(catalogue_id, 'catalogue') for row in entries):
            raise HTTPException(409, 'Catalogue auction number is already used.')
        target_month = auction.year * 12 + auction.month
        target_tab = next((item for item in tabs if _month(item['title']) == target_month), None)
        if not target_tab:
            raise HTTPException(409, f'No Auction Schedule tab exists for {auction.strftime("%B %Y")}. Add that monthly tab before sending this auction.')
        tab = target_tab['title']
        values = [[auction.strftime('%d-%m-%Y'), str(int(booking['time'][:2])), category, schedule_id, catalogue_id, 'Scheduled', sync_id]]
        result = _request(sheets, 'POST', f"/values/{_range(tab, 'A:G')}:append", params={'valueInputOption':'RAW','insertDataOption':'INSERT_ROWS'}, json={'values':values})
        updated = result.get('updates', {}).get('updatedRange', '')
        row_match = re.search(r'![A-Z]+(\d+)', updated)
        if not row_match:raise HTTPException(502, 'Google accepted the row but did not return its position. Check the sheet before retrying.')
        _paint_status(sheets, {'sheetId':target_tab['sheetId'],'sheetRow':int(row_match[1])}, status)
        return {'row':int(row_match[1]),'tab':tab,'scheduleId':schedule_id,'catalogueId':catalogue_id,'syncedAt':datetime.now(timezone.utc).isoformat()}
