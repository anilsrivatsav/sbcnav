"""Validate resumable writes against the before snapshot and planned values."""
from copy import deepcopy
from .core import entered
from .core import day
from datetime import timedelta

def completed_range(report):
    latest=report.get('last_recorded_after')
    if latest:
        return 'Last recorded: '+latest+'     â€¢     Checked through: '+str(report.get('end',''))
    return 'Verified scan: '+str(report.get('start',''))+' â†’ '+str(report.get('end',''))

def seven_day_failures(status_rows,asof):
    result=[]
    for row in status_rows[1:]:
        values=[entered(c) for c in row]
        if values[5].startswith('No beyond-grace'):continue
        due=day(values[7]);grace=due+timedelta(days=7)
        overdue=(day(asof)-grace).days
        if overdue>0:
            result.append((values[1],values[3],values[6] if values[6]!='' else 'Not provided by IREPS',due.strftime('%d/%m/%Y'),grace.strftime('%d/%m/%Y'),overdue))
    return result

def planned_grid(before,patches,columns):
    expected=deepcopy(before)
    for r,c,rows in patches:
        while len(expected)<r-1+len(rows):
            expected.append([{} for _ in range(columns)])
        for i,row in enumerate(rows):
            for j,value in enumerate(row):
                expected[r-1+i][c-1+j]=deepcopy(value)
    return expected

def compatible(before,current,patches,columns):
    expected=planned_grid(before,patches,columns)
    differences=[]
    for i in range(max(len(before),len(current),len(expected))):
        for j in range(columns):
            a=entered(before[i][j]) if i<len(before) else ''
            b=entered(expected[i][j]) if i<len(expected) else ''
            x=entered(current[i][j]) if i<len(current) else ''
            if x!=a and x!=b:
                differences.append((i+1,j+1))
    if differences:
        raise RuntimeError('The sheet was edited since this preview at '+str(differences[:6])+'. Make a fresh preview; the saved plan was not applied.')
    return expected

def pending(patches,current):
    todo=[]
    for r,c,rows in patches:
        equal=all(entered(value)==(entered(current[r-1+i][c-1+j]) if r-1+i<len(current) else '')
                  for i,row in enumerate(rows) for j,value in enumerate(row))
        if not equal:
            todo.append((r,c,rows))
    return todo

def dense_notes(patches,expected):
    """Paste a remarks column once, preserving untouched cells between changes."""
    output=[]
    columns={c for r,c,rows in patches if len(rows)==1 and len(rows[0])==1}
    for c in columns:
        group=[p for p in patches if p[1]==c and len(p[2])==1 and len(p[2][0])==1]
        first,last=min(p[0] for p in group),max(p[0] for p in group)
        output.append((first,c,[[expected[n-1][c-1]] for n in range(first,last+1)]))
    output.extend(p for p in patches if not(len(p[2])==1 and len(p[2][0])==1))
    return output
