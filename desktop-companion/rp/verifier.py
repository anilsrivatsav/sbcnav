"""Independent evidence checks for a Deskflow proposal.

This module never recalculates a proposal with the pricing engine. It checks the
saved inputs, the arithmetic in the result, and the provenance of each source.
"""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from rp.rules import canonical_unit


def _amount(value):
    try:
        amount = Decimal(str(value).replace(',', ''))
        return amount.quantize(Decimal('.01'), rounding=ROUND_HALF_UP) if amount.is_finite() and amount >= 0 else None
    except (InvalidOperation, ValueError):
        return None


def _pricing_basis(lot, auctions, contract, inputs, result):
    """Check the saved base and factor against the source fields, without calling the pricing engine."""
    rule = result.get('rule')
    if rule == 'workbook_continuation':
        return _continuation_basis(lot, auctions, inputs, result)
    base, factor = _amount(result.get('base')), _amount(result.get('multiplier'))
    previous = _amount(inputs.get('previous_rp')) or Decimal(0)
    initial = _amount(inputs.get('initial_rp')) or Decimal(0)
    finance = _amount(inputs.get('finance_fee')) or Decimal(0)
    events = sorted(auctions, key=lambda item: item.get('date', ''))
    last = events[-1] if events else {}
    sold = [item for item in events if item.get('outcome') == 'Sold']
    anchor = sold[-1].get('date', '') if sold else ''
    try:
        failures = int(inputs.get('earlier_failures') or 0) + sum(
            item.get('outcome') in ('Rejected', 'No Bids') and (not anchor or item.get('date', '') > anchor)
            for item in events)
        reductions = int(inputs.get('reductions') or 0)
    except (ValueError, TypeError):
        return False
    family = inputs.get('family')
    state = contract.get('status', 'No previous contract')
    expected = None
    if state in ('Running', 'Completed', 'Foreclosed'):
        expected = (_amount(contract.get('lar')), Decimal('1.1') if state == 'Completed' else Decimal(1))
    elif rule == 'non_commencement' and state in ('Not commenced', 'Not signed') and failures == 0:
        expected = (previous, _amount(contract.get('second_bidder_rate')) or Decimal(0)) if contract.get('second_bidder_verified') else None
    elif rule == 'withdrawn_retry' and last.get('outcome') == 'Withdrawn':
        expected = (previous or initial or finance, Decimal(1))
    elif rule == 'shop_market' and family == 'Shop (case by case)' and inputs.get('use_market_bid') and last.get('outcome') == 'Rejected' and last.get('rate_unit') == lot.get('rate_unit'):
        expected = (_amount(last.get('bid_rate')), Decimal(1))
    elif rule == 'food_truck' and family == 'Food truck' and failures == 0:
        expected = (initial, Decimal(1))
    elif rule == 'new_publicity' and family == 'Publicity' and failures == 0:
        expected = (initial or previous, Decimal(1))
    elif rule == 'publicity_failure' and family == 'Publicity' and failures > 0:
        expected = (previous, Decimal('.9'))
    elif rule == 'amenity_market' and family == 'Parking / Pay & Use' and inputs.get('important_amenity') and last.get('outcome') == 'Rejected' and last.get('rate_unit') == lot.get('rate_unit'):
        bid = _amount(last.get('bid_rate'))
        if bid is not None and bid > previous * Decimal('.6'):
            expected = (bid, Decimal(1))
    elif rule == 'parcel_market' and family == 'Parcel' and failures >= 2 and last.get('outcome') == 'Rejected' and last.get('rate_unit') == lot.get('rate_unit'):
        bid = _amount(last.get('bid_rate'))
        if bid is not None and bid > previous * Decimal('.5'):
            expected = (bid, Decimal(1))
    elif rule in ('first_two_attempts', 'parcel_reduction', 'successive_reduction'):
        benchmark = initial or (finance if family == 'Catering / MPS' else previous)
        if state in ('Not commenced', 'Not signed') and not initial:
            benchmark = max(previous, _amount(contract.get('second_bidder_rate')) or Decimal(0))
        if inputs.get('new_asset') and family == 'Catering / MPS':
            benchmark = finance
        if rule == 'first_two_attempts' and failures < 2:
            expected = (benchmark, Decimal(1))
        elif rule == 'parcel_reduction' and family == 'Parcel' and failures >= 2:
            count = min(7, max(reductions + 1, failures - 1))
            expected = (benchmark, Decimal(1) - Decimal('.1') * count)
        elif rule == 'successive_reduction' and family != 'Parcel' and failures >= 2:
            expected = (previous, Decimal('.9'))
    return bool(expected and expected[0] is not None and expected[0] > 0 and base == expected[0] and factor == expected[1])


def _continuation_basis(lot, auctions, inputs, result):
    """Independently check a sourced, dated workbook working and exact factor."""
    try:
        c = inputs['continuation']
        if not all(c.get(k) for k in ('source', 'policy', 'scope_source')):
            return False
        if any(c.get(k) != lot.get(k) for k in ('lot', 'description')) or canonical_unit(c.get('rate_unit')) != canonical_unit(lot.get('rate_unit')):
            return False
        anchor = date.fromisoformat(c['date'])
        cutoff = date.fromisoformat(lot['start'][:10])
        events = [a for a in auctions if date.fromisoformat(a['date'][:10]) >= anchor]
        if anchor >= cutoff or not any(a['date'][:10] == c['date'] for a in events):
            return False
        if any(a.get('outcome') not in ('No Bids', 'Rejected', 'Withdrawn') or not a.get('source') or not (date.fromisoformat(a['date'][:10]) < cutoff and date.fromisoformat(a['date'][:10]) <= date.today()) for a in events):
            return False
        identities = [(a['date'], a.get('catalogue'), a.get('previous_lot', a.get('lot'))) for a in events]
        if len(identities) != len(set(identities)):
            return False
        failures = sum(a['outcome'] in ('No Bids', 'Rejected') for a in events)
        if c['mode'] == 'parcel_initial' and inputs.get('family') == 'Parcel':
            factor = Decimal(1) - Decimal('.1') * min(7, max(0, failures - 1))
        elif c['mode'] == 'successive' and inputs.get('family') in ('Parking / Pay & Use', 'Catering / MPS') and int(c.get('prior_failures', 0)) >= 2:
            factor = Decimal('.9') ** failures
        else:
            return False
        base = Decimal(str(c['base']))
        return base.is_finite() and base > 0 and Decimal(str(result['base'])) == base and Decimal(str(result['multiplier'])) == factor and _amount(base * factor) == _amount(result['rp'])
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return False


def verify(record, scheduled=None, history=None, workbook=None, today=None):
    lot, auctions = record['lot'], record['auctions']
    contract, inputs, result = record['contract'], record['inputs'], record['result']
    lot = {**lot, 'rate_unit': canonical_unit(lot.get('rate_unit'))}
    auctions = [{**a, 'rate_unit': canonical_unit(a.get('rate_unit'))} for a in auctions]
    contract = {**contract, 'rate_unit': canonical_unit(contract.get('rate_unit'))}
    today = today or date.today()
    checks = []

    def check(code, state, message):
        checks.append({'code': code, 'state': state, 'message': message})

    auction_day = None
    try:
        auction_day = date.fromisoformat(lot.get('start', '')[:10])
    except (ValueError, TypeError):
        pass
    check('auction_date', 'pass' if auction_day else 'fail',
          f"Auction date: {auction_day.isoformat()}." if auction_day else 'Announced auction date is missing or invalid.')

    ids = scheduled.get('ids', []) if scheduled else []
    in_snapshot = record['key'] in ids
    collected = bool(scheduled and scheduled.get('complete') and in_snapshot
                     and scheduled.get('count') == len(ids) == len(set(ids)))
    check('scheduled_collection', 'pass' if collected else 'fail',
          'Lot is in the latest complete scheduled IREPS collection.' if collected
          else 'Collect scheduled IREPS lots again and resolve duplicate or missing lot identities.')
    collected_on = str((scheduled or {}).get('collected_at') or '')[:10]
    try:
        collection_day = date.fromisoformat(collected_on)
    except ValueError:
        collection_day = None
    if auction_day:
        cutoff_ok = bool(collection_day and collection_day <= min(auction_day, today))
        check('collection_cutoff', 'pass' if cutoff_ok else 'fail',
              'Scheduled collection is within the auction-date cutoff.' if cutoff_ok
              else 'Scheduled IREPS collection needs a valid timestamp no later than the announced auction date.')
        review_day = min(auction_day, today)
        check('scheduled_freshness', 'pass' if collection_day == review_day else 'warn',
              f'Scheduled IREPS lots were collected through {review_day.isoformat()}.' if collection_day == review_day
              else f'Recollect scheduled IREPS lots through {review_day.isoformat()} before final verification.')

    target = min(today, auction_day) if auction_day else today
    first_recorded = min((a.get('date', '') for a in auctions if a.get('date')), default=target.isoformat())
    try:
        history_collected = date.fromisoformat(str((history or {}).get('collected_at') or '')[:10])
    except ValueError:
        history_collected = None
    if (history and history.get('complete') and history.get('from_date', '') <= first_recorded
            and history.get('to_date', '') == target.isoformat()
            and history_collected and target <= history_collected <= today):
        check('history_coverage', 'pass', f"IREPS auction history scanned from {history['from_date']} through {history['to_date']}.")
    else:
        check('history_coverage', 'warn', f'Collect IREPS auction history through {target.isoformat()} to check later results.')

    if not inputs.get('identity_verified'):
        check('asset_identity', 'fail', 'Verify that every earlier lot and contract belongs to this exact asset and scope.')
    else:
        check('asset_identity', 'pass', 'Asset and previous lot identity confirmed.')

    identities = [(a.get('date'), a.get('catalogue'), a.get('previous_lot', a.get('lot'))) for a in auctions]
    def earlier_date(item):
        try:
            auction = date.fromisoformat(str(item.get('date') or '')[:10])
            return auction <= today and (auction < auction_day if auction_day else True)
        except ValueError:
            return False

    dates_valid = all(earlier_date(a) for a in auctions)
    unique = len(identities) == len(set(identities))
    source_valid = all(a.get('source') and a.get('outcome') in ('Sold', 'Rejected', 'No Bids', 'Withdrawn') for a in auctions)
    check('auction_evidence', 'pass' if dates_valid and unique and source_valid else 'fail',
          f'{len(auctions)} earlier IREPS outcomes have dates, sources and unique identities.' if dates_valid and unique and source_valid
          else 'Earlier auctions need valid dates no later than today and before this auction, distinct identities, verified outcomes and sources.')
    recorded_order = [a.get('date') or '' for a in auctions]
    ordered = recorded_order == sorted(recorded_order)
    check('auction_order', 'pass' if ordered else 'warn',
          'Previous auctions are stored in date order.' if ordered else 'Previous auctions are out of date order; review the latest outcome.')

    sold = [a for a in auctions if a.get('outcome') == 'Sold']
    sold_complete = all(_amount(a.get('bid_rate')) is not None and _amount(a.get('bid_rate')) > 0 and a.get('awardee') and a.get('rate_unit') == lot.get('rate_unit') for a in sold)
    check('bid_and_lar', 'pass' if sold_complete else 'fail',
          f'{len(sold)} sold outcomes include accepted bid rate, awardee and comparable unit.' if sold_complete else 'Sold outcomes need an accepted bid rate/LAR, awardee and matching rate unit.')
    rejected = [a for a in auctions if a.get('outcome') == 'Rejected']
    rejected_with_rate = [a for a in rejected if a.get('bid_rate') not in (None, '')]
    rejected_valid = all(_amount(a.get('bid_rate')) is not None and _amount(a.get('bid_rate')) > 0
                         and a.get('rate_unit') == lot.get('rate_unit') and a.get('bid_source')
                         for a in rejected_with_rate)
    rejected_missing = len(rejected) - len(rejected_with_rate)
    check('rejected_bids', 'fail' if not rejected_valid else 'warn' if rejected_missing else 'pass',
          'Rejected bid rates require a positive amount, comparable unit and IREPS bid source.' if not rejected_valid
          else f'{rejected_missing} rejected outcome(s) need bid presence and rate confirmed against IREPS.' if rejected_missing
          else f'{len(rejected)} rejected outcome(s) have sourced comparable bid rates.')

    status = contract.get('status', 'No previous contract')
    if status in ('Running', 'Completed', 'Foreclosed'):
        try:
            awarded = date.fromisoformat(str(contract.get('award_date') or '')[:10])
            started = date.fromisoformat(str(contract.get('start') or '')[:10])
        except ValueError:
            awarded = started = None
        contract_source_ok = bool(contract.get('source') and contract.get('rate_unit') == lot.get('rate_unit')
                                  and awarded and started and awarded <= started <= today)
        check('contract_evidence', 'pass' if contract_source_ok else 'fail',
              'Contract award, commencement, rate unit and source recorded.' if contract_source_ok
              else 'Verify the contract award date, commencement, comparable rate unit and source.')
        end_text = str(contract.get('end') or '')[:10]
        try:
            end_day = date.fromisoformat(end_text)
        except (ValueError, TypeError):
            end_day = None
        if end_day:
            days = (end_day - today).days
            period_ok = bool(started and end_day >= started and
                             (days >= 0 if status == 'Running' else days <= 0 if status == 'Completed' else True))
            check('contract_period', 'pass' if period_ok else 'fail',
                  f'{status} contract ends {end_day.isoformat()} ({days} days from today).' if status == 'Running' else f'{status} contract period ends {end_day.isoformat()}.')
        else:
            check('contract_period', 'fail', 'Contract end date is missing or invalid.')
        latest = sorted(sold, key=lambda a: a.get('date', ''))[-1] if sold else {}
        linked = bool(latest and _amount(contract.get('lar')) == _amount(latest.get('bid_rate')) and contract.get('awardee', '').strip().casefold() == latest.get('awardee', '').strip().casefold())
        check('contract_link', 'pass' if linked else 'fail',
              'Contract LAR and awardee match the latest sold auction.' if linked else 'Contract LAR/awardee do not match the latest sold auction.')
        if status == 'Foreclosed':
            try:
                closed_day = date.fromisoformat(str(contract.get('closed') or '')[:10])
            except ValueError:
                closed_day = None
            foreclosure_ok = bool(closed_day and started and started <= closed_day <= today
                                  and contract.get('termination_source'))
            check('foreclosure', 'pass' if foreclosure_ok else 'fail',
                  'Foreclosure date and decision source recorded.' if foreclosure_ok else 'Record a valid past foreclosure date and decision source.')
    elif status in ('Not commenced', 'Not signed', 'Cancelled (reason unknown)'):
        check('termination', 'pass' if contract.get('termination_source') and status != 'Cancelled (reason unknown)' else 'fail',
              'Non-commencement decision and source recorded.' if contract.get('termination_source') and status != 'Cancelled (reason unknown)' else 'Resolve the cancellation reason and decision source.')

    if inputs.get('new_asset'):
        basis = _amount(inputs.get('finance_fee')) or _amount(inputs.get('initial_rp'))
        check('new_asset_basis', 'pass' if basis and basis > 0 and inputs.get('benchmark_source') and not sold else 'fail',
              'New asset has a sourced Finance/tariff/comparable basis and no prior sold lot.' if basis and basis > 0 and inputs.get('benchmark_source') and not sold else 'New asset requires a sourced Finance/tariff/comparable basis; review any prior sold lot.')
    else:
        check('previous_outcome', 'pass' if auctions else 'fail',
              'Latest previous auction outcome recorded.' if auctions else 'Record the latest previous sold, rejected, no-bid or withdrawn auction.')

    check('standard_conditions', 'pass' if inputs.get('conditions_reviewed') else 'fail',
          'SCC v2.0 and applicable catalogue conditions marked reviewed.' if inputs.get('conditions_reviewed') else 'Review SCC v2.0 and applicable catalogue conditions.')
    check('benchmark_source', 'pass' if inputs.get('benchmark_source') else 'fail',
          'Pricing authority source recorded.' if inputs.get('benchmark_source') else 'Record the benchmark or Finance/tariff authority source.')
    if result.get('ready'):
        base, factor, proposed = (_amount(result.get(key)) for key in ('base', 'multiplier', 'rp'))
        rule = result.get('rule')
        expected = max(base, factor) if rule == 'non_commencement' and base is not None and factor is not None else max(base, Decimal(300000)) if rule == 'food_truck' and base is not None else base * factor if base is not None and factor is not None else None
        if expected is not None:
            expected = expected.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        if status in ('Running', 'Completed', 'Foreclosed'):
            lar = _amount(contract.get('lar'))
            expected_lar = (lar * (Decimal('1.1') if status == 'Completed' else Decimal(1))).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) if lar is not None else None
            correct_rule = rule == {'Running': 'running_lar', 'Completed': 'completed_lar', 'Foreclosed': 'foreclosed_lar'}[status]
            arithmetic_ok = expected == proposed == expected_lar and correct_rule
        elif rule == 'workbook_continuation':
            arithmetic_ok = _continuation_basis(lot, auctions, inputs, result)
        else:
            arithmetic_ok = expected is not None and expected == proposed
        check('calculation', 'pass' if arithmetic_ok else 'fail',
              f'{rule}: independently checked proposed value {proposed}.' if arithmetic_ok else 'Calculated value or rule does not match its evidence and formula.')
        basis_ok = _pricing_basis(lot, auctions, contract, inputs, result)
        check('pricing_basis', 'pass' if basis_ok else 'fail',
              'Formula base and factor match the recorded auction, contract or benchmark evidence.' if basis_ok
              else 'Formula base, factor or rule does not match the recorded bid, contract or benchmark evidence.')
        justification = result.get('justification', '')
        source = inputs.get('benchmark_source')
        justified = bool(justification and result.get('rule') and source and source in justification and str(result.get('rp')) in justification)
        check('justification', 'pass' if justified else 'fail',
              'Justification identifies the rule, amount and source.' if justified else 'Justification must identify the rule, amount and source.')
    else:
        check('calculation', 'fail', result.get('missing') or 'Complete the evidence before fixing the proposed value.')
        check('justification', 'warn', 'A final justification is available after the value is calculated.')

    if workbook and workbook.get('revision') == record['revision'] and workbook.get('ready') and workbook.get('digest') and workbook.get('current_digest') == workbook.get('digest'):
        check('local_workbook', 'pass', f"Saved in local workbook {workbook.get('workbook', '')} for this evidence revision.")
    else:
        check('local_workbook', 'warn', 'Sync the local workbook after reviewing this evidence; no matching saved revision is recorded.')

    state = 'blocked' if any(c['state'] == 'fail' for c in checks) else 'needs_review' if any(c['state'] == 'warn' for c in checks) else 'verified'
    return {'status': state, 'revision': record['revision'], 'checks': checks}
