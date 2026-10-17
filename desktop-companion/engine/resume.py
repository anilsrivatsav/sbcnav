"""Apply/resume a saved preview without collecting IREPS again."""
import json
from pathlib import Path
from checkpoint import compatible,pending,dense_notes
from sheets import export,workbook,grid,SheetUI,verify,filter_spec
from core import day,latest_recorded_date

def read_google(context,config,log,authenticate):
    for attempt in range(3):
        try:
            result={name:export(context,config[name+'_id']) for name in ('earnings','master')}
            log('AUTH|Google Sheets read access confirmed')
            return result
        except Exception as exc:
            if attempt==2:
                raise RuntimeError('Google Sheets access is still unavailable. Sign in with the account that can edit both workbooks, then Resume the saved preview.') from exc
            page=context.new_page();page.goto('https://accounts.google.com/')
            log('Google Sheets access needs attention. Sign in to the correct account in Chrome, then press Continue. Your saved preview will be kept.')
            authenticate()
            page.close()

def apply_plan(context,config,folder,report,plan,before,log,cancel,write,journal,authenticate):
    # Verify both workbooks against the checkpoint BEFORE editing either one.
    current={};expected={};status_lengths={};status_exists={}
    def refresh():
        exports=read_google(context,config,log,authenticate)
        for name,columns in (('earnings',28),('master',37)):
            filters=report.setdefault('filters',{})
            if name not in filters:filters[name]=filter_spec(exports[name],config[name+'_tab'])
            f,v=workbook(exports[name]);current[name]=grid(f,v,config[name+'_tab'],columns)
            expected[name]=compatible(before[name],current[name],plan[name],columns)
            status_exists[name]=config['status_tab'] in f.sheetnames
            status_lengths[name]=sum(1 for _ in f[config['status_tab']].iter_rows(max_col=10)) if status_exists[name] else 0
    refresh()
    # Check edit access on both targets before the first paste.
    for attempt in range(3):
        try:
            for name in ('earnings','master'):
                ui=SheetUI(context,config[name+'_id'],config[name+'_tab'],config[name+'_gid'],log)
                try:ui.assert_editable()
                finally:ui.close()
            break
        except Exception:
            if attempt==2:raise
            page=context.new_page();page.goto('https://accounts.google.com/')
            log('Edit access is needed for both sheets. Switch to the correct Google account and press Continue; no IREPS rescan is needed.')
            authenticate();page.close()
    # Sign-in can take time; recheck for edits made while access was restored.
    refresh()
    if cancel():raise RuntimeError('Cancelled before spreadsheet writes. The preview remains available.')
    report.update(preview=False,state='writing saved preview')
    journal()
    for name in ('earnings','master'):
        ui=SheetUI(context,config[name+'_id'],config[name+'_tab'],config[name+'_gid'],log)
        try:
            todo=pending(plan[name],current[name])
            if todo:
                report['write_started']=True
                journal()
                active=filter_spec(export(context,config[name+'_id']),config[name+'_tab'])
                ui.suspend_filter(active)
                try:
                    for kind,src,dst in plan['formats']:
                        if kind==name:ui.copy_format(src,dst)
                    write(ui,dense_notes(todo,expected[name]),cancel)
                finally:
                    ui.restore_filter(report['filters'][name])
            else:
                ui.restore_filter(report['filters'][name])
            data=verify(context,config[name+'_id'],config[name+'_tab'],plan[name])
            (folder/(name.title()+' after.xlsx')).write_bytes(data)
            phase=name+' verified'
            if phase not in report['phases']:report['phases'].append(phase)
            journal()
            report['write_started']=True
            journal()
            if status_exists[name]:ui.existing_tab(config['status_tab'])
            else:ui.new_tab(config['status_tab'])
            rows=list(plan['status'])
            rows.extend([[{} for _ in range(10)] for _ in range(max(0,status_lengths[name]-len(rows)))])
            status_patch=[(1,1,rows)]
            write(ui,status_patch,cancel)
            data=verify(context,config[name+'_id'],config['status_tab'],status_patch)
            (folder/(name.title()+' after.xlsx')).write_bytes(data)
            if name=='earnings':
                f,v=workbook(data)
                report['last_recorded_after']=latest_recorded_date(grid(f,v,config[name+'_tab'],28)).strftime('%d/%m/%Y')
            phase=name+' statuses verified'
            if phase not in report['phases']:report['phases'].append(phase)
            journal()
        finally:ui.close()
    report['state']='complete and verified'
    journal()
    log('Complete. Saved preview applied and both workbooks verified.')

def run_saved(config,folder,log,cancel,authenticate,connect,clock,write):
    from playwright.sync_api import sync_playwright
    folder=Path(folder)
    plan=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
    report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
    saved=report.get('targets')
    targets={k:config[k] for k in ('earnings_id','master_id','earnings_tab','master_tab','status_tab')}
    if saved and saved!=targets:raise RuntimeError('The saved preview targets different workbooks. Make a fresh preview.')
    if report.get('end') and clock().date().isoformat()!=day(report['end']).isoformat():
        raise RuntimeError('This preview is from an earlier day. Check new data to refresh contract statuses before applying it.')
    before={}
    for name,columns in (('earnings',28),('master',37)):
        f,v=workbook((folder/(name.title()+' before.xlsx')).read_bytes())
        before[name]=grid(f,v,config[name+'_tab'],columns)
    def journal():
        (folder/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    try:
        with sync_playwright() as pw:
            context=connect(pw,config,log).contexts[0]
            log('Resuming saved preview. IREPS records will not be collected again.')
            apply_plan(context,config,folder,report,plan,before,log,cancel,write,journal,authenticate)
        return folder,report
    except Exception as exc:
        report.update(state='paused - saved preview can be resumed',error=str(exc))
        journal();log('Paused: '+str(exc));raise
