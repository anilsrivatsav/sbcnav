import io,json,tempfile,unittest
from pathlib import Path
from rp.browser_repair import repair_catalogue_tabs

class BrowserRepairTests(unittest.TestCase):
    def test_only_catalogue_list_tabs_are_closed(self):
        targets=[{'id':'list','type':'page','title':'Folder Details','url':'https://www.ireps.gov.in/epsn/laBuyerInboxLink.do'},
                 {'id':'register','type':'page','title':'Reserve Price Register','url':'https://www.ireps.gov.in/epsn/commAuction/viewCommAucReg.do'},
                 {'id':'google','type':'page','title':'Google Account','url':'https://myaccount.google.com/'}]
        seen=[]
        def opener(request,timeout=8):
            url=request.full_url if hasattr(request,'full_url') else request;seen.append(url)
            return io.StringIO(json.dumps(targets) if url.endswith('/json/list') else 'ok')
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'browser.json').write_text('{"port":9333}')
            result=repair_catalogue_tabs(folder,opener)
        self.assertEqual(result['closed'],1)
        self.assertIn('http://127.0.0.1:9333/json/close/list',seen)
        self.assertNotIn('http://127.0.0.1:9333/json/close/register',seen)
        self.assertNotIn('http://127.0.0.1:9333/json/close/google',seen)

    def test_a_keepalive_tab_prevents_closing_the_browser_window(self):
        seen=[]
        def opener(request,timeout=8):
            url=request.full_url if hasattr(request,'full_url') else request;seen.append(url)
            if url.endswith('/json/list'):data=[{'id':'list','type':'page','title':'Folder Details','url':'https://www.ireps.gov.in/epsn/laBuyerInboxLink.do'}]
            elif '/json/new?' in url:data={'id':'blank','type':'page','url':'about:blank'}
            else:return io.StringIO('ok')
            return io.StringIO(json.dumps(data))
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'browser.json').write_text('{"port":9333}')
            repair_catalogue_tabs(folder,opener)
        self.assertLess(seen.index('http://127.0.0.1:9333/json/new?about:blank'),seen.index('http://127.0.0.1:9333/json/close/list'))

if __name__=='__main__':unittest.main()
