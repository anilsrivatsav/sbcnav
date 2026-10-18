"""Checks from the supplied SCC v2.0; these are not an RP fixation authority."""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import calendar

SOURCE = 'Standard Conditions of Contract Version 2.0'

def anniversary(start, years):
    return start.replace(year=start.year + years, day=min(start.day, calendar.monthrange(start.year + years, start.month)[1]))

def annual_fee(base, start, end, asof, model='ordinary'):
    """Clause 11: escalation only from year four within the agreed term."""
    start, end, asof = map(date.fromisoformat, (start, end, asof))
    try:base = Decimal(str(base).replace(',',''))
    except InvalidOperation:raise ValueError('Enter a valid accepted base rate.') from None
    if not base.is_finite() or base < 0 or end < start or not start <= asof <= end:
        raise ValueError('Enter a valid fee and a date within the verified contract period.')
    if model not in ('ordinary', 'BOT', 'ROMT'):
        raise ValueError('Verify the contract model.')
    years = asof.year - start.year
    if asof < anniversary(start, years): years -= 1
    exponent = max(0, years - 2)
    factor = Decimal('1.05') if model in ('BOT', 'ROMT') else Decimal('1.10')
    return str((base * factor ** exponent).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))

def review(contract):
    notes = [
        'SCC clauses 4.4 and 6: an award requires a highest bid at least equal to RP and fulfilment of the other award conditions.',
        'SCC clause 11 governs fees during the existing term, not the RP for the next auction. RP percentages below come from the recorded local benchmark/policy.',
    ]
    state = contract.get('status')
    if state == 'Not signed':
        notes.append('Clause 8: five days runs from receipt of the agreement; cancellation is discretionary. Verify receipt date and the actual cancellation decision.')
    if state == 'Not commenced':
        notes.append('Clauses 10 and 14: verify the catalogue start date and any permitted condonation (maximum 30 days for passenger amenities); delay does not extend the end date or payment deadlines.')
    if state in ('Foreclosed', 'Cancelled (reason unknown)'):
        notes.append('Clauses 17 and 18 distinguish contractor surrender, Railway termination and punitive termination. Clause 17.1 counts six months of contractual period, and requires 30 days notice; the award date alone does not establish it.')
    if state in ('Running', 'Completed'):
        notes.append('Clause 10: verify the catalogue term and any approved extension (maximum three months). Do not infer an extension from late commencement.')
    return notes
