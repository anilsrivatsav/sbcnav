"""One daily incremental payment check followed by upcoming auction catalogues only."""
from datetime import datetime, timedelta, timezone
from state_store import read_state, write_state
from uuid import uuid4

IST = timezone(timedelta(hours=5, minutes=30))


def tick(controller, deskflow, state_path, now=None):
    now = now or datetime.now(IST)
    if (now.hour, now.minute) < (9, 30):
        return 'not_due'
    status = controller.snapshot()
    if not status.get('configured') or status['busy'] or status['deskflow_busy']:
        return 'busy'
    if status.get('phase') in ('paused', 'error', 'interrupted'):
        return 'attention'
    day = now.date().isoformat()
    state = read_state(state_path)
    if state.get('day') != day:
        state = {'day': day}
    run = status.get('run') or {}
    if run.get('state') != 'complete' or status.get('end') != now.strftime('%d/%m/%Y'):
        if state.get('receipts_started'):
            return 'attention'
        state['receipts_started'] = True
        write_state(state_path, state)
        controller.command('start')  # This action always requests scan_mode=incremental.
        return 'receipts'
    schedules = deskflow.schedule_pdf_status()
    if any(r.get('phase') == 'ready' and r.get('checked_at', '')[:10] == day for r in schedules.values()):
        state['auctions_complete'] = True
        write_state(state_path, state)
    if state.get('auctions_complete'):
        return 'complete'
    if state.get('auctions_started'):
        return 'attention'
    state['auctions_started'] = True
    write_state(state_path, state)
    # 'schedule-pdf' uses all_scheduled + scheduled_only and publishes the same
    # verified schedule shown on SBCnav. No history, closed catalogue
    # enrichment, proposal saving or contract inventory runs in this daily path.
    deskflow.command('schedule-pdf', {'request_id': str(uuid4())})
    return 'auctions'
