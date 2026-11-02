import ast
import io
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
import zipfile
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from rp.workbook_sync import preserve_excel_value
from rp.rules import Result
from deskflow import public_text


class TwoWaySyncTests(unittest.TestCase):
    def test_display_wording_preserves_real_workbook_paths(self):
        path='D:/ANIL/UK/RP Parcles Temp - Complete 20-10-2026.xlsx'
        result=public_text({'workbook':path,'message':'RP review'})
        self.assertEqual(result['workbook'],path)
        self.assertEqual(result['message'],'value review')

    def fixture(self, folder, fail=False):
        root=Path(folder);(root/'operator.key').write_text('fixture-only')
        paths={group:root/(group+'.xlsx') for group in ('commercial','parcel','catering')}
        for group,path in paths.items():path.write_bytes(('before-'+group).encode())
        order=[]
        def writeback():
            order.append('writeback')
            if fail:return None
            for group,path in paths.items():path.write_bytes(('after-'+group).encode())
            return {'saved':[{'workbook':str(p)} for p in paths.values()],'calculated':0,'pending':[],'at':'fixture-time'}
        deskflow=SimpleNamespace(userdir=root,state={'error':'Fixture failure' if fail else None},update_workbooks=Mock(side_effect=writeback))
        def upload(request, **kwargs):
            order.append('upload')
            with zipfile.ZipFile(io.BytesIO(request.data)) as package:
                self.assertEqual(package.read('others.xlsx'),paths['commercial'].read_bytes())
            return io.BytesIO(json.dumps({'generatedAt':'fixture-time','totalRows':3,'auctionRecordCount':2}).encode())
        opener=Mock(side_effect=upload)
        scope={'STATE':root,'deskflow':deskflow,'threading':threading,'json':json,'io':io,'zipfile':zipfile,'hashlib':hashlib,
               'API':'https://example.test/api/mcdo','read_state':lambda p:{},
               'write_state':lambda path,value:path.write_text(json.dumps(value)),
               'urllib':SimpleNamespace(request=SimpleNamespace(Request=urllib.request.Request,urlopen=opener),error=urllib.error)}
        tree=ast.parse(Path(__file__).with_name('server.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='WorkbookArchiveSync')
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'sync-fixture','exec'),scope)
        deskflow.store=SimpleNamespace(evidence=lambda *a:[])
        instance=scope['WorkbookArchiveSync']()
        selection=Mock();selection.target.side_effect=lambda folder,group:paths[group]
        return instance,deskflow,opener,order,selection

    def test_writeback_happens_before_website_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            sync,deskflow,opener,order,selection=self.fixture(folder)
            with patch('rp.workbooks.WorkbookSelection',return_value=selection):sync.work(True,True)
            self.assertEqual(order,['writeback','upload'])
            self.assertEqual(sync.state['phase'],'complete')
            self.assertIn('Two-way sync complete',sync.state['message'])
            self.assertEqual(len(sync.state['writeback']['files']),3)

    def test_background_upload_does_not_rewrite_excel(self):
        with tempfile.TemporaryDirectory() as folder:
            sync,deskflow,opener,order,selection=self.fixture(folder)
            with patch('rp.workbooks.WorkbookSelection',return_value=selection):sync.work(False)
            deskflow.update_workbooks.assert_not_called()
            self.assertEqual(order,['upload'])
            self.assertNotIn('Two-way sync complete',sync.state['message'])

    def test_failed_writeback_stops_upload_and_never_claims_success(self):
        with tempfile.TemporaryDirectory() as folder:
            sync,deskflow,opener,order,selection=self.fixture(folder,fail=True)
            sync.work(True,True)
            opener.assert_not_called()
            self.assertEqual(sync.state['phase'],'error')

    def test_manual_values_are_preserved_until_reviewed(self):
        ready=Result(True,rp='100')
        self.assertTrue(preserve_excel_value({'raw_value':'90'},ready,None,'current'))
        self.assertTrue(preserve_excel_value({'raw_value':'0'},ready,'old','current'))
        self.assertFalse(preserve_excel_value({'raw_value':'90'},ready,'current','current'))
        self.assertFalse(preserve_excel_value({'raw_value':''},ready,None,'current'))
        self.assertFalse(preserve_excel_value(None,ready,None,'current'))

if __name__=='__main__':unittest.main()
