"""SBC-only MCDO calculations. Completed exports never read current asset status."""
from __future__ import annotations

import calendar
import hashlib
import io
import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

POLICIES = ['Z-611', 'Z-612', 'Z-613', 'Z-614', 'Z-615', 'Z-616', 'Z-617', 'Z-618', 'Z-248']
ASSETS = ['RDN', 'Mobile Assets', 'OOH', 'ATM', 'Misc Static Services', 'PMBJK',
          'Misc Mobile Services', 'Hybrid NFR', 'App Based Cab']
CRORE = Decimal('10000000')
TEMPLATE = Path(__file__).with_name('templates') / 'sbc_mcdo.xlsx'


class AssetPosition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    registered: StrictInt = Field(ge=0, le=1000000)
    leased: StrictInt = Field(ge=0, le=1000000)
    newly_created: StrictInt = Field(ge=0, le=1000000)


class MonthlyConfiguration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    annual_target_crore: Decimal | None = Field(default=None, gt=0, le=1000000, max_digits=16, decimal_places=6)
    target_source: str = Field(default='', max_length=1000)
    earnings_complete: StrictBool = False
    earnings_checked_through: date | None = None
    earnings_note: str = Field(default='', max_length=2000)
    asset_position_date: date | None = None
    asset_source: str = Field(default='', max_length=2000)
    assets: dict[str, AssetPosition] = Field(default_factory=dict, max_length=9)
    assets_verified: StrictBool = False


def period_dates(period):
    if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', period):
        raise ValueError('Choose a calendar month in YYYY-MM format.')
    y, m = map(int, period.split('-'))
    end = date(y, m, calendar.monthrange(y, m)[1])
    start_year = y if m >= 4 else y - 1
    return date(start_year, 4, 1), date(y, m, 1), end, f'{start_year}-{(start_year+1)%100:02d}'


def plain(value):
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def digest(value):
    return hashlib.sha256(json.dumps(plain(value), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def policy_code(row):
    # The Main Sheet Detailed Head owns the Z policy; broad Policy labels do not.
    detailed = re.fullmatch(r'Z\s*-\s*(\d{3})', str(row.get('detailed_head') or '').strip().upper())
    if detailed:
        return 'Z-' + detailed[1]
    found = set()
    for value in (row.get('detailed_head'), row.get('allocation_code')):
        value = str(value or '').strip().upper()
        match = re.fullmatch(r'Z\s*-\s*(\d{3})', value)
        if match:
            found.add('Z-' + match[1])
        elif re.fullmatch(r'\d{8}(?:\.0)?', value):
            found.add('Z-' + value.split('.')[0][-5:-2])
    return next(iter(found)) if len(found) == 1 else None


def calculate(period, rows, source, configuration, today):
    fy_start, month_start, month_end, fy = period_dates(period)
    config = MonthlyConfiguration.model_validate(configuration or {})
    config_data = config.model_dump(mode='json')
    issues, pending, notes = [], [], []
    if month_end >= today:
        pending.append('The selected month has not closed.')
    if not source:
        pending.append('Import Earnings Master Main Sheet first.')
    records = [r for r in rows if r.get('financial_year') == fy]
    if source and not records:
        pending.append(f'No earnings source is available for financial year {fy}.')
    scope = []
    for row in records:
        m = row.get('month')
        if m not in range(1, 13):
            issues.append(f"Earnings row {row['source_row']}: reporting month is missing.")
            continue
        y = int(fy[:4]) if m >= 4 else int(fy[:4]) + 1
        if date(y, m, 1) <= month_start:
            scope.append(row)
    for row in scope:
        dt = row.get('receipt_date')
        if isinstance(dt, str):
            try:
                dt = date.fromisoformat(dt)
            except ValueError:
                dt = None
        if not dt or not fy_start <= dt <= month_end or dt.month != row['month']:
            notes.append(f"Earnings row {row['source_row']}: receipt date differs; reporting follows the maintained Year/Month.")
        allocation = str(row.get('allocation_code') or '').split('.')[0]
        if re.fullmatch(r'\d{8}', allocation) and policy_code(row) and 'Z-'+allocation[-5:-2] != policy_code(row):
            notes.append(f"Earnings row {row['source_row']}: reporting follows Detailed Head {policy_code(row)}; allocation code is retained unchanged.")
        division = str((row.get('source_values') or {}).get('Division', 'SBC')).strip().upper()
        if division not in ('SBC', 'BENGALURU', 'BANGALORE'):
            issues.append(f"Earnings row {row['source_row']}: division is not SBC.")
    seen = set()
    previous = current = Decimal(0)
    policy_totals = dict.fromkeys(POLICIES, Decimal(0))
    for row in scope:
        raw = row.get('source_values') or {}
        invoice = str(raw.get('Invoice') or '').strip().upper()
        if invoice:
            if invoice in seen:
                issues.append(f"Earnings row {row['source_row']}: duplicate invoice {invoice}.")
            seen.add(invoice)
        amount = row.get('nfr_earnings')
        if amount is None:
            issues.append(f"Earnings row {row['source_row']}: NFR earnings amount is missing.")
            continue
        amount = Decimal(str(amount))
        if not amount.is_finite():
            issues.append(f"Earnings row {row['source_row']}: invalid earnings amount.")
            continue
        if row['month'] == month_start.month:
            current += amount
        else:
            previous += amount
        code = policy_code(row)
        if code not in policy_totals:
            if amount:
                issues.append(f"Earnings row {row['source_row']}: missing, conflicting or unsupported Z policy.")
        else:
            policy_totals[code] += amount
    cumulative = previous + current
    if sum(policy_totals.values()) != cumulative:
        issues.append('Policy-wise earnings do not reconcile with cumulative SBC earnings.')
    if config.annual_target_crore is None or not config.target_source.strip():
        pending.append('Enter the applicable annual SBC target and its source.')
    if not config.earnings_complete or not config.earnings_note.strip():
        pending.append('Confirm all financial-year earnings through this month are collected and reconciled, including zero-earning months.')
    if not config.earnings_checked_through or not month_end <= config.earnings_checked_through <= today:
        pending.append('Set the verified earnings coverage date to this month end or later, no later than today.')
    if set(config.assets) != set(ASSETS):
        pending.append('Supply dated asset counts for all nine categories; enter zero explicitly where applicable.')
    if not config.assets_verified or not config.asset_source.strip() or not config.asset_position_date:
        pending.append('Verify the asset position and identify its dated IREPS report/source.')
    elif not month_end <= config.asset_position_date <= today:
        issues.append('Asset position date must be on/after the selected month end and no later than today.')
    asset_rows = {}
    for name, position in config.assets.items():
        if name not in ASSETS:
            issues.append('Unknown asset category: ' + name)
            continue
        if position.leased > position.registered:
            issues.append(f'{name}: leased assets exceed registered assets.')
        if position.newly_created > position.registered:
            issues.append(f'{name}: newly created assets exceed registered assets.')
        idle = position.registered-position.leased
        asset_rows[name] = {**position.model_dump(), 'idle': idle,
                            'idle_percent': str(Decimal(idle)*100/position.registered) if position.registered else None}
    totals = {k: sum(r[k] for r in asset_rows.values()) for k in ('registered', 'leased', 'idle', 'newly_created')}
    totals['idle_percent'] = str(Decimal(totals['idle'])*100/totals['registered']) if totals['registered'] else None
    elapsed = (month_start.year-fy_start.year)*12 + month_start.month-fy_start.month+1
    target = config.annual_target_crore
    proportionate = target*elapsed/12 if target else None
    cum_crore = cumulative/CRORE
    data = {'period': period, 'financial_year': fy, 'month_name': calendar.month_name[month_start.month],
            'month_end': month_end.isoformat(), 'configuration': config_data,
            'earnings': {'previous_crore': str(previous/CRORE), 'current_crore': str(current/CRORE),
                         'cumulative_crore': str(cum_crore), 'annual_target_crore': str(target) if target else None,
                         'proportionate_target_crore': str(proportionate) if proportionate else None,
                         'proportionate_variance_percent': str((cum_crore-proportionate)/proportionate*100) if proportionate else None,
                         'annual_variance_percent': str((cum_crore-target)/target*100) if target else None},
            'policies_crore': {k: str(v/CRORE) for k,v in policy_totals.items()},
            'assets': asset_rows, 'asset_totals': totals, 'row_count': len(scope),
            'source': source, 'issues': issues, 'pending': pending, 'notes': notes}
    # Later months/imports do not stale a completed month when its underlying rows are unchanged.
    fingerprint = digest({'period': period, 'configuration': config_data,
                          'rows': [{k: v for k,v in r.items() if k != 'import_id'} for r in scope],
                          'unallocated': [r for r in records if r.get('month') not in range(1,13)]})
    return {**plain(data), 'fingerprint': fingerprint,
            'status': 'Needs Correction' if issues else 'Data Pending' if pending else 'Ready to Complete'}


def filename(report, version):
    y, m = report['period'].split('-')
    return f"SBC_MCDO_{y}_{m}_{report['month_name']}_v{version}.xlsx"


def export_workbook(report, version):
    """Populate a blank template derived from the supplied October format."""
    if report['issues'] or report['pending']:
        raise ValueError('Only fully reconciled reports may be exported.')
    book = load_workbook(TEMPLATE)
    earning, policy, assets = (book[n] for n in ('Immediate earning ', 'Policywise ', 'Idle Assets '))
    y, m = map(int, report['period'].split('-'))
    label = f"{report['month_name']} {y}"
    fy = report['financial_year']
    prev = date(y-1 if m == 1 else y, 12 if m == 1 else m-1, 1)
    earning['A3'] = f'1. Division - wise NFR Earnings in FY {fy} (Cumulative upto {label}) (in crore Rs.)'
    earning['C5'] = f'Revenue earned upto {prev:%B %Y} (last month)'
    earning['D5'] = f'Revenue earned in {label} (current month)'
    earning['E5'] = f'Proportionate Target (upto {label})'
    earning['F5'] = f'Cumulative NFR earned upto {label}'
    earning['H5'] = f'Annual Target FY {fy}'
    e = report['earnings']
    keys = ['previous_crore','current_crore','proportionate_target_crore','cumulative_crore',
            'proportionate_variance_percent','annual_target_crore','annual_variance_percent']
    for col, key in enumerate(keys, 3):
        earning.cell(10, col, float(e[key]) if e[key] is not None else 'N/A')
    earning['A12'] = 'SBC only'
    policy['A3'] = f'2. Division - wise, Policy - wise NFR Earnings in FY {fy} (Cumulative upto {label})'
    policy['M5'] = f'NFR Target FY {fy}'
    policy['N5'] = f'Percentage excess / shortfall against Annual Target in FY {fy}'
    for col, code in enumerate(POLICIES, 3):
        policy.cell(8, col, float(report['policies_crore'][code]))
    for col, key in ((12,'cumulative_crore'),(13,'annual_target_crore'),(14,'annual_variance_percent')):
        policy.cell(8, col, float(e[key]))
    policy['N8'].number_format = '0.00'
    policy['A10'] = 'SBC only'
    position = date.fromisoformat(report['configuration']['asset_position_date'])
    assets['A13'] = f'4. Status of NFR IDLE ASSETS (Position dated:{position:%d.%m.%Y})'
    for col, category in enumerate(ASSETS + ['Total'], 2):
        values = report['assets'][category] if category != 'Total' else report['asset_totals']
        for row, key in ((16,'registered'),(17,'leased'),(18,'idle'),(19,'idle_percent'),(20,'newly_created')):
            value = values[key]
            assets.cell(row, col, float(value) if value is not None else 'N/A')
            assets.cell(row, col).number_format = '0.00' if key == 'idle_percent' else '0'
    # Preserve template sheet count/layout. Provenance lives in cell notes.
    from openpyxl.comments import Comment
    earning['B10'].comment = Comment(f"SBC only; version {version}; source import {report['source']['import_id']}; fingerprint {report['fingerprint']}. Earnings: NFR earnings, excludes GST; PUB and NFR are not added. Percentages retain template excess/shortfall convention.", 'SBC NAV')
    assets['A13'].comment = Comment(report['configuration']['asset_source'], 'SBC NAV')
    earning['H10'].comment = Comment(report['configuration']['target_source'], 'SBC NAV')
    output = io.BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()
