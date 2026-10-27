"""Read exact workbook identities for two-way sync without rewriting Excel."""
import re
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from .excel_io import _sheet_path, _strings, _text, Q
from .rules import number
from .workbooks import SPECS


def read_rows(paths):
    result={}
    columns={'commercial':('L','N','E','F'),'parcel':('Q','R','M','P'),'catering':('N','P','L','M')}
    for group,path in paths.items():
        path=Path(path);lotcol,catcol,valuecol,notecol=columns[group]
        with ZipFile(path) as package:
            strings=_strings(package)
            root=E.fromstring(package.read(_sheet_path(package,SPECS[group]['sheet'])))
            for row in root.find(Q('sheetData')):
                cells={re.match('[A-Z]+',cell.get('r'))[0]:cell for cell in row}
                identity=(_text(cells.get(lotcol),strings).strip(),_text(cells.get(catcol),strings).strip())
                if not all(identity):continue
                if identity in result:
                    result[identity]['ambiguous']=True
                    continue
                raw=_text(cells.get(valuecol),strings).strip()
                try:value=float(number(raw)) if raw else None
                except ValueError:value=None
                result[identity]={'group':group,'value':value,'raw_value':raw,'notes':_text(cells.get(notecol),strings),
                    'file':path.name,'path':str(path),'sheet':SPECS[group]['sheet'],'row':int(row.get('r'))}
    return result


def preserve_excel_value(existing, result, previously_saved_digest, current_digest):
    return bool(existing and existing.get('raw_value') and result.ready
                and previously_saved_digest!=current_digest)
