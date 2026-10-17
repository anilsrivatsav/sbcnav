"""Explicit workbook routing and layout validation before reading or writing."""
import json
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from .excel_io import _sheet_path,_strings,_text,Q

SPECS={
    'commercial':{'name':'Parking / Pay & Use / Publicity / Food truck / Shop','file':'Prk PnU.xlsx','sheet':'Table1','history':'RP history source','checks':{'E5':'RP','F5':'RP justification','L5':'Lot / original detail','N5':'Catalogue / source J'}},
    'parcel':{'name':'Parcel','file':'RP Parcles Temp.xlsx','sheet':'Sheet1 (2)','history':'Sheet1 (2)','checks':{'C1':'Train','G1':'LAR','M1':'RP','N1':'No of Trips'}},
    'catering':{'name':'Catering / MPS','file':'E_AUCTION CATG JUn 2025 EA.xlsx','sheet':'Sheet1','history':'Sheet1','checks':{'C4':'Stall No.','D4':'Stn','J4':'Indicative license Fee (in Rs.)','M4':'Accounts Vetting'}}
}

def family_group(family):
    if family=='Parcel':return'parcel'
    if family=='Catering / MPS':return'catering'
    if family in ('Parking / Pay & Use','Publicity','Food truck','Shop (case by case)'):return'commercial'
    raise ValueError('Choose a recognised asset family before selecting a target workbook.')

def validate(path,group):
    path=Path(path)
    if not path.is_file():raise ValueError('Workbook not found: '+str(path))
    if path.suffix.lower()!='.xlsx':raise ValueError('Select an .xlsx workbook: '+str(path))
    spec=SPECS[group]
    try:
        with ZipFile(path)as z:
            try:sp=_sheet_path(z,spec['sheet'])
            except StopIteration:raise ValueError('Expected worksheet '+spec['sheet']+' is missing in '+path.name)
            ss=_strings(z);sheet=E.fromstring(z.read(sp))
            cells={c.get('r'):c for c in sheet.findall('.//'+Q('sheetData')+'/'+Q('row')+'/'+Q('c'))if c.get('r')in spec['checks']}
            mismatches=[address for address,text in spec['checks'].items()if _text(cells.get(address),ss).strip()!=text]
            if mismatches:raise ValueError('This workbook does not match the '+spec['name']+' layout ('+', '.join(mismatches)+'). Select the correct workbook; no file was changed.')
    except ValueError:raise
    except Exception as e:raise ValueError('Cannot read workbook '+str(path)+': '+str(e))from e
    return path.resolve()

class WorkbookSelection:
    def __init__(self,config):
        self.config=Path(config);self.overrides={}
        if self.config.exists():
            try:self.overrides=json.loads(self.config.read_text(encoding='utf8'))
            except Exception as e:raise ValueError('Cannot read the saved workbook selection: '+str(e))from e
    def paths(self,folder):return{g:Path(self.overrides.get(g,Path(folder)/s['file']))for g,s in SPECS.items()}
    def target(self,folder,group):return validate(self.paths(folder)[group],group)
    def save(self,paths):
        validated={g:str(validate(paths[g],g))for g in SPECS}
        if len(set(p.casefold()for p in validated.values()))!=3:raise ValueError('Select a separate correct workbook for each asset group.')
        self.config.parent.mkdir(parents=True,exist_ok=True)
        temp=self.config.with_suffix('.tmp');temp.write_text(json.dumps(validated,indent=2),encoding='utf8');temp.replace(self.config)
        self.overrides=validated
