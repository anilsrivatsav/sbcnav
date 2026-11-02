import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from rp.review import WorkbookPreview, cells
from rp.rules import Result


class LayoutTests(unittest.TestCase):
    def test_pending_refresh_preserves_existing_height_and_value(self):
        ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        rel='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
        def text(address,value):
            return f'<c r="{address}" t="inlineStr"><is><t>{value}</t></is></c>'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'commercial.xlsx'
            sheet=f'<worksheet xmlns="{ns}"><dimension ref="A1:N6"/><sheetData><row r="5">'+''.join(text(a,v) for a,v in {
                'E5':'RP','F5':'RP justification','L5':'Lot / original detail','N5':'Catalogue / source J'}.items())+'</row><row r="6" ht="180" customHeight="1"><c r="E6"><v>100</v></c>'+''.join(text(a,v) for a,v in {
                'F6':'Original manual working','G6':'Annual Licensing Fee','L6':'LOT','N6':'CAT'}.items())+'</row></sheetData></worksheet>'
            with ZipFile(path,'w') as package:
                package.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets><sheet name="Table1" sheetId="1" r:id="rId1"/></sheets></workbook>')
                package.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
                package.writestr('xl/worksheets/sheet1.xml',sheet)
            record={'lot':{'lot':'LOT','catalogue':'CAT','rate_unit':'Annual Licensing Fee','start':'2026-11-01'},
                    'inputs':{'family':'Parking / Pay & Use'},'result':Result(False,missing='Review new evidence.')}
            preview=WorkbookPreview(path,'commercial',[record],allow_existing=True,preserve_pending=True)
            try:preview.commit()
            finally:preview.close()
            values=cells(path,'Table1')
            self.assertEqual(values['E6'],'100')
            self.assertTrue(values['F6'].startswith('Original manual working'))
            with ZipFile(path) as package:
                root=E.fromstring(package.read('xl/worksheets/sheet1.xml'))
                row=root.find(f'.//{{{ns}}}row[@r="6"]')
                self.assertGreaterEqual(float(row.get('ht')),180)

if __name__=='__main__':unittest.main()
