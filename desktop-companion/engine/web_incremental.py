"""Routine web scans: recent awards plus exact watched contracts and unpaid dues."""
from core import day, key, status_name
from incremental import category_for, merge_ranges


def watched_contracts(config, failures):
    watched = {key(r['contract']): r['contract'] for r in config['master_watch']
               if status_name(r['status']) == 'Running' or r['dues'] or r['pending']}
    watched.update({key(r['contract']): r['contract'] for r in failures})
    return watched


def payment_queries(config, statuses, failures):
    categories = config['categories']
    known = {key(r['contract']): r for r in config['master_watch']}
    windows = {c: [] for c in categories}
    extra = set()
    for k, record in statuses.items():
        category = category_for(record['category'], categories)
        if not category:
            continue
        source = known.get(k)
        if source is None or source['pending']:
            extra.add((category, record['contract'], '01/01/1900', '31/12/2099'))
        elif source['dues']:
            dates = [day(d) for d in source['dues']]
            windows[category].append((min(dates), max(dates)))
    for failure in failures:
        category = category_for(failure['category'], categories)
        if category:
            due = day(failure['due'])
            windows[category].append((due, due))
    return [(c, '', a.strftime('%d/%m/%Y'), b.strftime('%d/%m/%Y'))
            for c in categories for a, b in merge_ranges(windows[c])] + sorted(extra)
