import importlib.util,pathlib,unittest
path=pathlib.Path(__file__).parent/'rp/direct_evidence.py'
spec=importlib.util.spec_from_file_location('direct_evidence',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class DirectTests(unittest.TestCase):
    def test_rendered_inline_agreement_fields_and_effective_cancellation(self):
        text=('Contract No.\tABC\tDated\t11/05/2022\n'
              'Contract Start Date\t28/05/2022\tContract End Date\t25/08/2022\n'
              'Contract cancelled w.e.f. 02/07/2022. EMD forfeited.\n'
              'Mode of allotment: e-Auction (Auction date- 10/05/2022 , Catalogue No- SBC-PAR-S2 , Lot No- PARKING-SBC-GBD-TW-5-22-1 )\n'
              'Asset Code\tPARKING-SBC-GBD-TW-5\nRate (Rs.)\t50000\tFull Contract value\nContract Value\tRs. 59000.00')
        f=module.agreement_fields(text,'ABC')
        self.assertEqual(f['lot'],'PARKING-SBC-GBD-TW-5-22-1')
        self.assertEqual(f['catalogue'],'SBC-PAR-S2')
        self.assertEqual(f['rate_unit'],'Full Contract value')
        self.assertEqual(f['agreement_rate'],'50000')
        self.assertEqual(f['actual_closure_date_iso'],'2022-07-02')
        self.assertEqual(f['planned_contract_end_iso'],'2022-08-25')
        self.assertEqual(f['decision_type'],'Cancelled')
        self.assertNotIn('explicit_lar',f)
    def test_scope_includes_actual_workbook_service_categories(self):
        for category in ['ATM - General','Parcel-SLR','Catering - General Minor Unit (GMU)',
          'Misc-Static-Services - Water Vending Machines','Misc-Static-Services - Battery Operated Carts with Advertisement',
          'Misc-Static-Services - Mobiles and accessories Kiosk','Misc-Mobile-Services - Mobile General']:
            self.assertTrue(module.in_scope(category),category)
        for category in module.EXCLUDED_CATEGORIES:self.assertFalse(module.in_scope(category))

    def test_scheduled_end_never_becomes_closure_or_lar(self):
        fields=module.agreement_fields('Contract No.\tABC-123\tContract Date\t01/01/2023\nRate (Rs.)\t12,500.00\nRate Unit\tPer Trip Licensing Fee\nContract End Date\t31/12/2026','ABC-123')
        self.assertEqual(fields['agreement_rate'],'12,500.00')
        self.assertEqual(fields['rate_unit'],'Per Trip Licensing Fee')
        self.assertEqual(fields['planned_contract_end'],'31/12/2026')
        self.assertNotIn('actual_closure_date',fields)
        self.assertNotIn('explicit_lar',fields)

    def test_exact_identity_and_explicit_termination(self):
        text='Contract No.\nABC-123\nContract End Date\n31/12/2026\nTermination Date\n15/09/2025\nTermination Reason\nLicensee request\nLast Accepted Rate\nRs. 12,000.00'
        fields=module.agreement_fields(text,'ABC-123')
        self.assertEqual(fields['actual_closure_date'],'15/09/2025')
        self.assertEqual(fields['explicit_lar'],'12,000.00')
        with self.assertRaises(ValueError):module.agreement_fields(text,'OTHER')

    def test_previous_or_planned_fields_are_not_current_facts(self):
        text='Previous Contract No.\tOLD\nContract No.\tABC-123\nPrevious Lot No.\t999\nLot No.\t123\nScheduled Closure Date\t31/12/2026\nReserve Rate (Rs.)\t500\nRate (Rs.)\t700'
        fields=module.agreement_fields(text,'ABC-123')
        self.assertEqual(fields['lot'],'123')
        self.assertEqual(fields['agreement_rate'],'700')
        self.assertNotIn('actual_closure_date',fields)
        with self.assertRaises(ValueError):module.agreement_fields('Contract No.\tAB-C','A-BC')

    def test_closure_dates_are_not_partial_or_non_date_text(self):
        fields=module.agreement_fields('Contract No.\tABC\nClosure Date\t31-Oct-2026','ABC')
        self.assertEqual(fields['actual_closure_date'],'31-Oct-2026')
        self.assertEqual(fields['actual_closure_date_iso'],'2026-10-31')
        fields=module.agreement_fields('Contract No.\tABC\nClosure Date\tNot applicable','ABC')
        self.assertNotIn('actual_closure_date',fields)

    def test_navigation_race_is_retried_but_other_errors_stop(self):
        class Page:
            calls=0
            def wait_for_load_state(self,state):pass
            def evaluate(self,script,marker):
                self.calls+=1
                if self.calls<3:raise RuntimeError('Execution context was destroyed, most likely because of a navigation')
                self.marker=marker
        page=Page();waits=[]
        module.mark_reader(page,'owned-marker',lambda:None,waits.append)
        self.assertEqual(page.marker,'owned-marker');self.assertEqual(page.calls,3)
        self.assertEqual(waits,[.25,.25])
        class InvalidPage(Page):
            def evaluate(self,*args):raise RuntimeError('Unexpected source origin')
        with self.assertRaisesRegex(RuntimeError,'Unexpected source origin'):
            module.mark_reader(InvalidPage(),'marker',lambda:None,waits.append)

    def test_remaining_stages_require_complete_metadata_and_bid_sources(self):
        import tempfile
        from types import SimpleNamespace
        from rp.store import Store
        from rp.history_library import HistoryLibrary
        with tempfile.TemporaryDirectory() as folder:
            store=Store(pathlib.Path(folder)/'source.sqlite');library=HistoryLibrary(store)
            desk=SimpleNamespace(store=store,library=lambda:library)
            collector=module.DirectCollector(desk)
            with self.assertRaises(ValueError):collector.completed_history('2022-01-01','2023-01-02')
            store.save_evidence('__workspace__','history_snapshot',{'complete':True,'from_date':'2022-01-01','to_date':'2023-01-02','coverage':{'complete':True,'expected':1,'visited':['ireps:1']}})
            scan=library.start_scan('2022-01-01','2023-01-02')
            row={'date':'2023-01-01','lot':'1','category':'Parking - Mixed','catalogue':'CAT','outcome':'Sold','rate_unit':'Annual',
                 'source':'https://www.ireps.gov.in/catalogue?catalogId=1'}
            library.save_catalogue(scan,'CAT','fp',[row],'ireps:1')
            with self.assertRaisesRegex(ValueError,'bid-viewer'):collector.completed_history('2022-01-01','2023-01-02')
            row.update(bid_details_unavailable='Only Bid Value shown',bid_source='https://www.ireps.gov.in/bids',bid_viewer_rows=[['Bid Value'],['500']])
            library.save_catalogue(scan,'CAT','fp',[row],'ireps:1')
            verified=collector.completed_history('2022-01-01','2023-01-02')
            self.assertEqual(verified['sold_lots'],1);self.assertEqual(verified['unavailable_rates'],1)
            # A metadata refresh keeps the source of missing rates, and a new
            # readable bid table clears the old unavailable marker.
            refresh={k:v for k,v in row.items() if not k.startswith('bid_')}
            library.save_catalogue(scan,'CAT','fp',[refresh],'ireps:1')
            self.assertEqual(collector.completed_history('2022-01-01','2023-01-02')['unavailable_rates'],1)
            fresh={**refresh,'bid_rows':[{'Bid Rate':'500'}],'bid_rate':500,'bid_source':'https://www.ireps.gov.in/bids'}
            library.save_catalogue(scan,'CAT','fp',[fresh],'ireps:1')
            self.assertEqual(collector.completed_history('2022-01-01','2023-01-02')['unavailable_rates'],0)

    def test_interrupted_refresh_keeps_completed_coverage(self):
        import tempfile
        from rp.store import Store
        from rp.history_library import HistoryLibrary
        with tempfile.TemporaryDirectory() as folder:
            store=Store(pathlib.Path(folder)/'source.sqlite');library=HistoryLibrary(store)
            first=library.start_scan('2022-01-01','2023-01-02')
            library.save_catalogue(first,'CAT','fp',[{'date':'2023-01-01','lot':'1','catalogue':'CAT','outcome':'No Bids','source':'https://www.ireps.gov.in/catalogue?catalogId=1'}],'ireps:1')
            library.finish_scan(first,{'complete':True,'expected':1,'visited':['ireps:1']})
            refresh=library.start_scan('2022-01-01','2023-01-02')
            self.assertNotEqual(first,refresh)
            library.scan_progress(refresh,{'expected':1,'visited':[]},interrupted=True)
            self.assertEqual(library.coverage()['through'],'2023-01-02')
            self.assertFalse(library.history_plan('2023-01-02')['initial'])

    def test_source_url_validation(self):
        self.assertTrue(module.official('https://www.ireps.gov.in/epsn/contract/view.do'))
        self.assertFalse(module.official('https://www.ireps.gov.in.evil.example/'))
        self.assertFalse(module.official('file:///workbook.xlsx'))

    def test_outcome_refresh_preserves_captured_bid_list(self):
        import tempfile,json
        from rp.store import Store
        from rp.history_library import HistoryLibrary
        with tempfile.TemporaryDirectory() as folder:
            store=Store(pathlib.Path(folder)/'source.sqlite');library=HistoryLibrary(store)
            scan=library.start_scan('2022-01-01','2023-01-02')
            row={'date':'2023-01-01','lot':'1','catalogue':'CAT','outcome':'Sold','rate_unit':'Per Trip',
                 'source':'https://www.ireps.gov.in/catalogue?catalogId=1','bid_rate':500,
                 'bid_source':'https://www.ireps.gov.in/bids','bid_rows':[{'Bid Rate':'500','Bidder':'Example company'}],
                 'bid_rate_basis':'Highest displayed bid'}
            library.save_catalogue(scan,'CAT','first',[row],'ireps:1')
            refresh={k:v for k,v in row.items() if not k.startswith('bid_')}
            library.save_catalogue(scan,'CAT','second',[refresh],'ireps:1')
            with store.connect() as c:saved=json.loads(c.execute('SELECT data FROM df_auctions WHERE active=1').fetchone()[0])
            self.assertEqual(saved['bid_rows'],row['bid_rows'])
            self.assertEqual(saved['bid_rate_basis'],row['bid_rate_basis'])
            self.assertEqual(saved['bid_rate'],500)

if __name__=='__main__':unittest.main()
