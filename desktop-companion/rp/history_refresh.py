"""Reuse proven history only for the same covered lot codes."""
from datetime import date, timedelta


def retry_connection(error, attempt, cancelled):
    message=str(error).lower()
    return not cancelled and attempt<3 and any(text in message for text in (
        'target page, context or browser has been closed', 'connection closed',
        'websocket', 'econnreset', 'epipe', 'open updater chrome connection did not respond',
        'page.goback: timeout', 'page.goto: timeout'))


def refresh_start(previous, lot_codes, default_start, end):
    try:
        if not previous or not previous.get('complete') or previous.get('reader_version') != 2:
            return None
        if not set(lot_codes).issubset(previous.get('lot_codes', [])):
            return None
        first = date.fromisoformat(previous['from_date'])
        last = date.fromisoformat(previous['to_date'])
        if first > date.fromisoformat(default_start) or not first <= last <= date.fromisoformat(end):
            return None
        baseline = previous.get('baseline_coverage') or previous.get('coverage') or {}
        for report in (baseline, previous.get('coverage') or {}):
            visited = report.get('visited', [])
            expected = report.get('expected')
            if not report.get('complete') or type(expected) is not int or expected != len(visited) or len(set(visited)) != expected:
                return None
        # Recheck recent decisions, while retaining the completed historical evidence.
        return max(first, last - timedelta(days=30)).isoformat()
    except (ValueError, TypeError, KeyError):
        return None
