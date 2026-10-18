"""Reserve-price proposals from explicit, verified evidence. No IREPS mutations."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
import calendar

VERSION = '2026-10-17 / RP workbook logic with SCC v2.0 checks'
FAMILIES = ['Parking / Pay & Use', 'Parcel', 'Publicity', 'Catering / MPS', 'Food truck', 'Shop (case by case)']
UNITS = ['Annual Licensing Fee', 'Per Trip Licensing Fee', 'Per Round Trip Licensing Fee', 'Full Contract value']
CONTRACT_STATES = ['No previous contract','Running','Completed','Foreclosed','Not commenced','Not signed','Cancelled (reason unknown)','Unknown']

def canonical_unit(value):
    text=' '.join(str(value or '').split())
    if text.casefold() in ('per round trip ( two way )','per round trip (two way)'):
        return 'Per Round Trip Licensing Fee'
    return text

def number(value):
    try:
        n = Decimal(str(value).replace(',', '').strip())
        if not n.is_finite() or n < 0: raise ValueError()
        return n
    except Exception:
        raise ValueError('Enter a non-negative numeric rate.')

def money(value): return number(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
def dt(value):
    try: return date.fromisoformat(str(value)[:10])
    except Exception: raise ValueError('Dates must use YYYY-MM-DD.')

def months_after(day, months):
    y, m = divmod(day.year * 12 + day.month - 1 + months, 12)
    return date(y, m + 1, min(day.day, calendar.monthrange(y, m + 1)[1]))

@dataclass
class Result:
    ready: bool
    rp: str = ''
    formula: str = ''
    base: str = ''
    multiplier: str = ''
    justification: str = ''
    missing: str = ''
    rule: str = ''

def calculate(lot, auctions, contract, inputs):
    """Excel formula uses H = base, I = factor; {r} is filled at export."""
    try:
        lot={**lot,'rate_unit':canonical_unit(lot.get('rate_unit'))}
        auctions=[{**a,'rate_unit':canonical_unit(a.get('rate_unit'))} for a in auctions]
        if contract:contract={**contract,'rate_unit':canonical_unit(contract.get('rate_unit'))}
        result = _calculate(lot, auctions, contract, inputs)
        if result.ready:
            result.justification += ' RP authority: ' + inputs['benchmark_source'] + '. SCC v2.0 clause 11 concerns existing-contract fees, not this re-auction RP.'
        return result
    except (ValueError, TypeError, KeyError) as e:
        return Result(False, missing=str(e))

def _calculate(lot, auctions, contract, inputs):
    family = inputs.get('family', '')
    if family not in FAMILIES: raise ValueError('Select the asset family.')
    if not inputs.get('benchmark_source'):raise ValueError('Record the benchmark / Finance / tariff evidence source.')
    if lot.get('status') not in ('RP Pending', 'RP yet to be fixed'):
        raise ValueError('This lot is not marked RP yet to be fixed.')
    if not lot.get('lot'): raise ValueError('Lot identity is missing.')
    if not lot.get('start'): raise ValueError('Announced auction date is missing.')
    dt(lot['start'])
    if not inputs.get('identity_verified'):
        raise ValueError('Confirm that the history and contract belong to this exact asset / compartment / scope.')
    target_unit = lot.get('rate_unit', '')
    if target_unit not in UNITS: raise ValueError('Confirm the catalogue rate unit.')
    events = sorted(auctions, key=lambda a: dt(a['date']))
    for a in events:
        if a.get('outcome') not in ('Sold', 'Rejected', 'No Bids', 'Withdrawn'):
            raise ValueError('Previous auction outcome is not verified.')
        if not a.get('source'): raise ValueError('Record the source for the auction evidence.')
        if a['outcome'] == 'Sold':
            if not a.get('awardee'): raise ValueError('Record who was awarded the sold lot.')
            if number(a.get('bid_rate', 0)) <= 0: raise ValueError('Sold lot requires the accepted BID RATE / LAR.')
            if a.get('rate_unit') != target_unit: raise ValueError('Sold rate unit differs from this lot. Confirm a comparable rate; never substitute total contract value.')
    last = events[-1] if events else None
    sold = [a for a in events if a['outcome'] == 'Sold']
    new_asset = bool(inputs.get('new_asset'))
    if not new_asset and not last: raise ValueError('Check and record the latest previous bidding outcome.')
    if new_asset and sold: raise ValueError('A sold auction exists. Review the asset history instead of treating it as a new asset.')
    state = contract.get('status', 'Unknown') if contract else 'No previous contract'
    if state not in CONTRACT_STATES: raise ValueError('Contract status is not recognised; select a verified contract state.')
    if not new_asset and state in ('Unknown', 'No previous contract'):
        raise ValueError('Verify whether the previous contract is running, foreclosed, completed or never commenced.')
    if state == 'Cancelled (reason unknown)': raise ValueError('Cancellation reason is needed: foreclosure and non-commencement use different rules.')
    if contract:
        if not contract.get('source'): raise ValueError('Record the source for the contract evidence.')
        if state != 'No previous contract':
            if not contract.get('awardee'): raise ValueError('Contract awardee is missing.')
            if contract.get('rate_unit') != target_unit: raise ValueError('Contract LAR is not in the catalogue rate unit.')
            if not contract.get('award_date'): raise ValueError('Contract award date is missing.')
        if state in ('Running', 'Completed', 'Foreclosed'):
            if not contract.get('start') or not contract.get('end'): raise ValueError('Contract start and end dates are required.')
            if dt(contract['end']) < dt(contract['start']): raise ValueError('Contract end precedes its start.')
        if sold:
            latest = sold[-1]
            if contract.get('awardee', '').strip().casefold() != latest['awardee'].strip().casefold():
                raise ValueError('Latest sold awardee and linked contract awardee do not agree.')
            if number(contract.get('lar', 0)) != number(latest['bid_rate']):
                raise ValueError('Contract LAR and latest accepted bid rate do not agree. Check the correct contract.')
    previous = number(inputs.get('previous_rp') or 0)
    initial = number(inputs.get('initial_rp') or 0)
    finance = number(inputs.get('finance_fee') or 0)
    lar = number(contract.get('lar') or 0) if contract else Decimal(0)
    old_failures = int(inputs.get('earlier_failures') or 0)
    reductions = int(inputs.get('reductions') or 0)
    if old_failures < 0 or reductions < 0: raise ValueError('Attempt and reduction counts cannot be negative.')
    anchor = dt(sold[-1]['date']) if sold else None
    failures = old_failures + sum(a['outcome'] in ('Rejected', 'No Bids') and (anchor is None or dt(a['date']) > anchor) for a in events)
    if reductions > 0 and failures < 2: raise ValueError('A prior reduction is recorded but the failed-attempt count is incomplete. Enter earlier failures before calculating.')
    evidence = f"Latest auction: {last['date']} {last['outcome']}. " if last else 'New asset, no previous sold contract confirmed. '
    if previous > 0: evidence += f'Previous RP {previous}. '
    if sold:
        evidence += f"Accepted rate {sold[-1]['bid_rate']} {target_unit}; awarded to {sold[-1]['awardee']}. "
    if contract and state != 'No previous contract':
        evidence += f"Contract {state}; award {contract['award_date']}, period {contract.get('start', '')} to {contract.get('end', '')}. "

    def done(base, factor, formula, text, rule):
        rp = money(base * factor)
        return Result(True, str(rp), formula, str(base), str(factor), evidence + text + f' Proposed RP {rp} {target_unit}.', rule=rule)

    if state in ('Not commenced', 'Not signed'):
        if previous <= 0: raise ValueError('Previous RP is needed for non-commencement.')
        if not contract.get('second_bidder_verified'): raise ValueError('Verify the second-highest DISTINCT bidder rate (or explicitly confirm a single bidder). Bidding increments do not qualify.')
        second = number(contract.get('second_bidder_rate') or 0)
        base = max(previous, second)
        if failures == 0:
            result = done(base, Decimal(1), '=IF(H{r}>I{r},H{r},I{r})', f'Previous RP {previous} and verified distinct second-bidder rate {second}; higher rate used under Item 65 of MSoP/2018.', 'non_commencement')
            result.base = str(previous);result.multiplier = str(second)
            return result
        if initial <= 0: initial = base
    if last and last['outcome'] == 'Withdrawn':
        base = previous or initial or finance
        if base <= 0: raise ValueError('Previous approved RP is required for a withdrawn catalogue retry.')
        return done(base, Decimal(1), '=+H{r}', 'Latest catalogue was withdrawn, not a bidding-price failure. Retain its previous approved RP for the retry; no additional reduction is applied.', 'withdrawn_retry')
    if state == 'Foreclosed' and family == 'Food truck':raise ValueError('Food-truck foreclosure pricing needs an explicit case-by-case decision; no automatic family-specific foreclosure rule is recorded.')
    if state == 'Foreclosed' and family != 'Shop (case by case)':
        if not contract.get('closed'): raise ValueError('Actual foreclosure date is missing.')
        closed, awarded = dt(contract['closed']), dt(contract['award_date'])
        if closed < awarded: raise ValueError('Foreclosure precedes award.')
        if family == 'Publicity':
            if previous <= 0: raise ValueError('Previous publicity RP is needed.')
            return done(previous, Decimal('.9'), '=+H{r}*0.9', 'Publicity foreclosure: previous RP reduced by 10%.', 'publicity_foreclosure')
        if closed < months_after(awarded, 6):
            base = finance if family == 'Catering / MPS' else previous
            if base <= 0: raise ValueError('Finance-vetted LF (catering) or previous RP is required for foreclosure within six months.')
            return done(base, Decimal(1), '=+H{r}', 'Foreclosed within six months; original Finance fee / previous RP retested, rather than the failed award rate.', 'early_foreclosure')
        if lar <= 0: raise ValueError('Accepted LAR is missing.')
        if failures == 0:
            return done(lar, Decimal(1), '=+H{r}', 'Foreclosed after six months or more; accepted LAR retested.', 'late_foreclosure')
        if initial <= 0: initial = lar
    if state in ('Running', 'Completed'):
        if lar <= 0: raise ValueError('Accepted LAR is missing.')
        full_three_years = dt(contract['end']) + timedelta(days=1) >= months_after(dt(contract['start']), 36)
        if family in ('Parking / Pay & Use', 'Parcel'):
            factor = Decimal('1.1') if full_three_years else Decimal(1)
            text = 'Full three-year tenure: LAR + 10%.' if full_three_years else 'Tenure below three years: accepted LAR retained.'
            if state == 'Running': text += ' Existing contract remains live; a new contract must start after its verified end date.'
            if last is None or last['outcome'] == 'Sold':return done(lar, factor, '=+H{r}*1.1' if full_three_years else '=+H{r}', text, 'expiry')
            if initial <= 0:initial=lar*factor
        elif last is None or last['outcome'] == 'Sold':raise ValueError('This completed/running asset needs its family-specific benchmark or review; automatic expiry escalation is not specified by the local logic.')
    if family == 'Shop (case by case)':
        if not inputs.get('use_market_bid'): raise ValueError('Shop pricing requires an explicit case-by-case decision. Select market-bid adoption only after review.')
        if not last or last['outcome'] != 'Rejected' or number(last.get('bid_rate') or 0) <= 0: raise ValueError('A verified rejected bid RATE is required for market-price adoption.')
        if last.get('rate_unit') != target_unit: raise ValueError('Rejected bid rate unit is not comparable.')
        return done(number(last['bid_rate']), Decimal(1), '=+H{r}', 'Latest market bid adopted for an idle shop after explicit case-by-case review.', 'shop_market')
    if family == 'Food truck':
        if failures: raise ValueError('Food-truck re-auction reduction requires a case-by-case decision; the local note does not specify an automatic food-truck reduction rule.')
        if initial <= 0: raise ValueError('Enter a sourced food-truck / station benchmark, such as the verified YNK/HSRA comparable.')
        base = max(initial, Decimal(300000))
        result = done(base, Decimal(1), '=IF(H{r}<300000,300000,H{r})', f'Food-truck benchmark {initial}, subject to the Rs 3,00,000 minimum used in 29.12.23.', 'food_truck')
        result.base = str(initial)
        return result
    if initial <= 0: initial = finance if family == 'Catering / MPS' else previous
    if new_asset and family == 'Catering / MPS':
        if finance <= 0: raise ValueError('New catering asset requires its Finance-vetted LF.')
        initial = finance
    if initial <= 0: raise ValueError('Initial tariff / Finance fee / comparable benchmark RP is missing.')
    if family == 'Publicity':
        if failures == 0: return done(initial, Decimal(1), '=+H{r}', 'Comparable / initial publicity benchmark used.', 'new_publicity')
        if previous <= 0: raise ValueError('Previous RP is required for publicity reduction.')
        return done(previous, Decimal('.9'), '=+H{r}*0.9', 'Verified failed publicity attempt; previous RP reduced by 10%.', 'publicity_failure')
    if last and last['outcome'] == 'Rejected' and previous > 0:
        bid = number(last.get('bid_rate') or 0)
        comparable = last.get('rate_unit') == target_unit
        if family == 'Parking / Pay & Use' and inputs.get('important_amenity') and comparable and bid > previous * Decimal('.6'):
            return done(bid, Decimal(1), '=+H{r}', 'Important amenity: latest rejected bid exceeds 60% of previous RP; market bid adopted.', 'amenity_market')
        if family == 'Parcel' and failures >= 2 and comparable and bid > previous * Decimal('.5'):
            return done(bid, Decimal(1), '=+H{r}', 'Third-or-later parcel attempt; latest rejected bid exceeds 50% of RP and is adopted as market rate.', 'parcel_market')
    if failures < 2:
        return done(initial, Decimal(1), '=+H{r}', f'Initial RP retained for attempt {failures + 1}; withdrawn catalogues do not count as bidding failures.', 'first_two_attempts')
    if family == 'Parcel':
        count = min(7, max(reductions + 1, failures - 1))
        factor = Decimal(1) - Decimal('.1') * count
        return done(initial, factor, '=+H{r}*I{r}', f'Parcel convention: {count} ten-percentage-point reductions from the original benchmark; maximum seven. Factor {factor}.', 'parcel_reduction')
    if previous <= 0: raise ValueError('Previous RP is required for the next 10% reduction.')
    return done(previous, Decimal('.9'), '=+H{r}*0.9', 'After two actual failed auctions, previous RP reduced by a further 10%, using the repeated multiplication convention of 29.12.23.', 'successive_reduction')
