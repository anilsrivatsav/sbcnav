import unittest
from rp.asset_library import identity,workbook_record

class AssetEvidenceTest(unittest.TestCase):
    def test_commercial_uses_current_sheet_columns_not_old_price_column(self):
        r={'book':'commercial','sheet':'Table1','row':12,'file':'Commercial.xlsx','cells':{k:{'value':v} for k,v in {'A':'2026-10-01','B':'Parking','D':'Parking 250 sq.m','E':'12000','F':'Reviewed working','H':'90000','L':'PRK-SBC-1','N':'CAT-1'}.items()}}
        v=workbook_record(r)
        self.assertEqual((v['value'],v['lot'],v['catalogue'],v['cell']),(12000,'PRK-SBC-1','CAT-1','E12'))
        self.assertEqual(v['justification'],'Reviewed working')
    def test_area_variants_are_not_erased(self):
        self.assertEqual(identity('P','Parking area 1,250.50 sq.m.')['areas'],[1250.5])
        self.assertNotEqual(identity('P','Parking 250 sqm')['areas'],identity('P','Parking 350 sqm')['areas'])
    def test_parcel_position_conflict_remains_visible(self):
        v=identity('17294-SLR-F1-SMVB-NS-26-1','3.9 tons in RSLR coach')
        self.assertTrue(v['scope_conflict']);self.assertEqual(v['parcel_types'],['RSLR'])
        self.assertEqual(v['encoded_parcel_types'],['FSLR'])
        self.assertEqual(v['train'],'17294')
    def test_rear_is_never_classified_front_from_generic_slr(self):
        self.assertEqual(identity('12345-SLR-R1','RSLR compartment')['parcel_types'],['RSLR'])
        self.assertEqual(identity('12345-VP1','Parcel van')['parcel_types'],['VP'])
    def test_blank_price_does_not_become_zero(self):
        r={'book':'parcel','sheet':'Sheet1 (2)','row':2,'file':'Parcel.xlsx','cells':{k:{'value':v} for k,v in {'A':'2026-10-01','C':'12345','F':'12345-SLR-R1','M':'','P':'Pending','Q':'12345-SLR-R1'}.items()}}
        self.assertIsNone(workbook_record(r)['value'])
    def test_blank_asset_does_not_steal_default_selection(self):
        r={'book':'catering','sheet':'Sheet1','row':2,'file':'Catering.xlsx','cells':{'A':{'value':'2026-10-01'}}}
        self.assertIsNone(workbook_record(r))

if __name__=='__main__':unittest.main()
