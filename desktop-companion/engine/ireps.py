"""Read-only IREPS browser workflow, using a separate Chrome window."""
import re, time
from urllib.parse import urljoin, urlparse
from core import relevant, key, day, contract_terms
from incremental import invoice_needed

HOME = 'https://www.ireps.gov.in/epsn/home/showHome.do'

class FilteredResultError(RuntimeError):
    """The exact-contract result retained category-wide pagination metadata."""

class Ireps:
    def __init__(self, context, log, cancelled):
        self.context, self.log, self.cancelled = context, log, cancelled
        self.warnings = []
        self.confirmed_paid_due = {}
        self.page = context.new_page()
        self.page.set_default_timeout(30000)

    def check(self):
        if self.cancelled():
            raise RuntimeError('Cancelled before any further writes.')
        if 'Your session has expired' in self.page.locator('body').inner_text():
            raise RuntimeError('IREPS session expired. Run again and sign in; existing invoice numbers prevent duplicates.')

    def login(self):
        self.page.goto(HOME)
        self.log('Sign in to IREPS in the separate Chrome window. The app never reads your password or OTP.')
        for _ in range(1200):
            if self.cancelled():
                raise RuntimeError('Cancelled.')
            if self.page.get_by_role('link', name='Payments', exact=True).is_visible():
                self.log('IREPS sign-in confirmed.')
                return
            time.sleep(1)
        raise RuntimeError('IREPS sign-in timed out after 20 minutes.')

    def navigate(self, mode):
        self.check()
        self.page.goto(HOME)
        self.page.get_by_role('link', name=mode, exact=True).click()
        link = 'Payments Received' if mode == 'Payments' else 'View Contracts'
        with self.page.expect_navigation(wait_until='load'):
            self.page.get_by_role('link', name=link, exact=True).click()
        self.page.locator('#menuLink').wait_for(state='visible')
        self.page.wait_for_function("document.querySelector('#menuLink')?.options.length > 0")

    def search(self, category, kind=None, start=None, end=None, contract=''):
        self.check()
        self.page.locator('#regCat').select_option(label=category)
        self.page.locator('#regSubCat').select_option(label='---All---')
        if kind:
            self.page.locator('#status').select_option(label=kind)
        else:
            self.page.locator('#tdStatus').select_option(label='All')
        self.page.locator('#tenderNumber').fill(contract)
        self.page.locator('#bidderName').fill('')
        if start is not None:
            # These are the site's own read-only calendar fields; only the selected dates change.
            for field, value in (('ddmmyyDateformat1', start), ('ddmmyyDateformat2', end)):
                self.page.locator('#'+field).evaluate("(el, value) => {el.value = value; el.dispatchEvent(new Event('change', {bubbles:true}));}", value)
        stamp = self.page.evaluate('performance.timeOrigin')
        with self.page.expect_navigation(wait_until='load'):
            self.page.get_by_role('button', name='Search', exact=True).click()
        self.wait_results(stamp)
        if start is not None:
            selected = [self.page.locator('#'+field).input_value() for field in ('ddmmyyDateformat1','ddmmyyDateformat2')]
            if selected != [start,end]:
                raise RuntimeError('IREPS changed the selected date filters. No spreadsheet writes will occur.')

    def wait_results(self, previous_document):
        # Pagination links have href="#" plus form submission. The hash change
        # can satisfy a navigation wait while the OLD result page still exists.
        # Wait for a different, fully loaded document before reading any rows.
        self.page.wait_for_function("(stamp) => performance.timeOrigin !== stamp && document.readyState === 'complete' && /\\d+\\s*Records Found/.test(document.body?.innerText || '')",arg=previous_document)

    def page_rows(self, mode):
        # Read rendered HTML only. No undocumented endpoints or transaction actions.
        return self.page.locator('table').evaluate_all("""(tables, mode) => {
          let found = [];
          for (const table of tables) {
            const rows = [...table.rows];
            const wanted = mode === 'paid' ? 'Payment date' : 'Contract No';
            const header = rows.find(r => [...r.cells].some(c => c.innerText.trim() === wanted || c.innerText.trim() === wanted+'.'));
            if (!header) continue;
            const columns = mode === 'failed' ? 8 : 9;
            const values = rows.filter(r => r !== header && r.cells.length === columns && (mode !== 'paid' || /^\\d{4}-\\d{2}-\\d{2}/.test(r.cells[0]?.innerText.trim() || '')));
            if (values.length) found = values.map(r => ({cells:[...r.cells].map(c=>c.innerText.trim()), links:[...r.querySelectorAll('a')].map(a=>({text:a.innerText.trim(),title:a.title,onclick:a.getAttribute('onclick'),href:a.getAttribute('href')}))}));
          }
          return found;
        }""", mode)

    def all_rows(self, mode, filtered=False):
        body = self.page.locator('body').inner_text()
        m = re.search(r'(\d+)\s*Records Found', body)
        if not m:
            raise RuntimeError('IREPS result count missing; no spreadsheet writes will occur.')
        total, page_num, seen, output = int(m[1]), 1, set(), []
        while True:
            self.check()
            batch = self.page_rows(mode)
            if filtered and not batch and total:
                raise FilteredResultError('Exact-contract results are empty but the displayed count is positive.')
            signature = repr(batch)
            if signature in seen:
                if filtered:raise FilteredResultError('Exact-contract pagination repeated a page.')
                raise RuntimeError('IREPS repeated a page; refusing an incomplete scan.')
            seen.add(signature)
            output.extend(batch)
            if total > 10 and (page_num % 5 == 0 or len(output) >= total):
                self.log(f'Checked {len(output)} / {total} records in this category.')
            if len(output)==total:
                break
            next_page = page_num+1
            pages = self.page.locator('a[onclick*="menuexpand("]')
            link = pages.filter(has_text=re.compile(r'^'+str(next_page)+r'$'))
            if link.count() != 1:
                link = pages.filter(has_text=re.compile(r'^next$',re.I))
            if link.count() != 1:
                if len(output) == total:
                    break
                # IREPS's contract count can include records it does not render:
                # live Advertising showed 78, but all eight pages contained 75.
                # Only accept a small final-page discrepancy after exhausting
                # every visible page. Statuses apply only to explicit records;
                # absence never marks a contract as stopped or paid.
                if mode == 'contracts' and page_num == max(1,(total+9)//10) and 0 < total-len(output) < 10:
                    warning=f'IREPS contract count says {total}; all {page_num} visible pages contain {len(output)}. Only explicitly listed contracts will be updated.'
                    self.warnings.append(warning)
                    self.log('Notice: '+warning)
                    return output
                if filtered:raise FilteredResultError(f'Exact-contract pagination stopped at {len(output)} of {total}.')
                raise RuntimeError(f'IREPS pagination stopped at {len(output)} of {total}.')
            page_num = next_page
            stamp = self.page.evaluate('performance.timeOrigin')
            with self.page.expect_navigation(wait_until='load'):
                link.click()
            self.wait_results(stamp)
        if len(output) != total:
            if filtered:raise FilteredResultError(f'Exact-contract row count mismatch: {len(output)} / {total}.')
            raise RuntimeError(f'IREPS row count mismatch: {len(output)} / {total}.')
        return output

    def payments(self, categories, start, end, queries=None, existing=None, known_due=None):
        self.navigate('Payments')
        records = {}
        category_cache = {}
        requests = queries if queries is not None else [(cat,'','01/01/1900','31/12/2099') for cat in categories]
        for cat,contract,from_due,to_due in requests:
            self.log('Reading collected payments: '+cat+((' / '+contract) if contract else '')+' • installment dues '+from_due+' to '+to_due)
            # Live verification showed that this site's Payment Date filter actually
            # matches installment pay-by dates. Blank filters revert to 90 days,
            # so use an explicit broad range and scan every returned page before
            # selecting by the collection timestamp displayed in column one.
            if contract:
                self.search(cat, 'Previous Payments Made', from_due, to_due, contract=contract)
            else:
                self.search(cat, 'Previous Payments Made', from_due, to_due)
            cache_key=(cat,from_due,to_due)
            try:
                scanned = self.all_rows('paid',filtered=True) if contract else self.all_rows('paid')
            except FilteredResultError as exc:
                warning=f'IREPS exact-contract pagination is inconsistent for {contract}. Verifying the category results and filtering this contract locally.'
                self.warnings.append(warning)
                self.log('Notice: '+warning)
                if cache_key not in category_cache:
                    # Start from the normal payment view. Clearing the text
                    # field on the faulty exact-contract result can retain
                    # server-side filtered state across pagination.
                    self.navigate('Payments')
                    self.search(cat, 'Previous Payments Made', from_due, to_due, contract='')
                    category_cache[cache_key]=self.all_rows('paid')
                scanned=category_cache[cache_key]
            if not contract:category_cache[cache_key]=scanned
            selected = 0
            for row in scanned:
                c = row['cells']
                if len(c) != 9:
                    raise RuntimeError('Payment columns changed.')
                if contract and key(c[2])!=key(contract):
                    continue
                if not relevant(c[4]):
                    continue
                if float(c[1].replace(',',''))>0 and re.fullmatch(r'ES\w+',c[8]):
                    self.confirmed_paid_due.setdefault(key(c[2]),set()).add(day(c[7]))
                if not day(start) <= day(c[0]) <= day(end):
                    continue
                selected += 1
                links = [a for a in row['links'] if re.fullmatch(r'ES\w+', a['text'])]
                if len(links) != 1:
                    raise RuntimeError('Missing unique invoice link.')
                a = links[0]
                if existing is not None and not invoice_needed(a['text'],c[2],c[7],existing,known_due or {}):
                    continue
                m = re.search(r"window\.open\(\s*['\"]([^'\"]+)", a['onclick'] or '')
                if not m:
                    raise RuntimeError('Invoice link format changed.')
                url = urljoin(HOME, m[1])
                if urlparse(url).hostname != 'www.ireps.gov.in' or not url.lower().endswith('.pdf'):
                    raise RuntimeError('Unexpected invoice destination.')
                item = dict(invoice=a['text'], url=url, paid=c[0], total=float(c[1].replace(',','')),
                            contract=c[2], contract_date=c[3], category=c[4], asset=c[5], firm=c[6], due=c[7])
                if item['invoice'] in records and records[item['invoice']] != item:
                    raise RuntimeError('Conflicting duplicate invoice rows.')
                records[item['invoice']] = item
            self.log(f'{cat}: checked {len(scanned)} records; {selected} collected in the update range.')
        return sorted(records.values(), key=lambda r:(r['paid'], r['invoice']))

    def failures(self, categories):
        self.navigate('Payments')
        output = []
        for cat in categories:
            self.log('Checking overdue payment failures: '+cat)
            self.search(cat, 'Payment Failures (Beyond grace period)')
            for row in self.all_rows('failed'):
                c = row['cells']
                if len(c) != 8:
                    raise RuntimeError('Failed-payment columns changed.')
                if relevant(c[2]):
                    output.append(dict(contract=c[0], category=c[2], amount=c[5], due=c[6], status='Payment failed / beyond grace period'))
        return output

    def contracts(self, categories, start, end):
        self.navigate('Contracts')
        output = {}
        for cat in categories:
            self.log('Checking contract status: '+cat)
            self.search(cat, start=start, end=end)
            for row in self.all_rows('contracts'):
                c = row['cells']
                if len(c) != 9:
                    raise RuntimeError('Contract columns changed.')
                if relevant(c[3]) and key(c[0]):
                    item = dict(contract=c[0], contract_date=c[1], firm=c[2], category=c[3], asset=c[4], start=c[5], end=c[6], status=c[7])
                    if key(c[0]) in output and output[key(c[0])] != item:
                        raise RuntimeError('Conflicting official contract records: '+c[0])
                    output[key(c[0])] = item
        return output

    def terms(self, record, raw=False):
        self.navigate('Contracts')
        self.search('---All---', start='01/01/2020', end=record['asof'], contract=record['contract'])
        rows = self.all_rows('contracts')
        if len(rows) != 1 or key(rows[0]['cells'][0]) != key(record['contract']):
            raise RuntimeError('Exact contract search did not return one matching record.')
        status = rows[0]['cells'][7]
        link = self.page.get_by_role('link', name='Contract', exact=True)
        with self.page.expect_navigation(wait_until='domcontentloaded'):
            link.click()
        text = self.page.locator('body').inner_text()
        with self.page.expect_popup() as popup:
            self.page.get_by_role('button', name='Payment Schedule', exact=True).click()
        schedule_page = popup.value
        try:
            schedule_page.locator('tr[id^="row-"]').first.wait_for()
            schedule = schedule_page.locator('tr[id^="row-"]').evaluate_all('(rs)=>rs.map(r=>[...r.cells].map(c=>c.innerText.trim()))')
            heading = schedule_page.locator('body').inner_text()
            if record['contract'] not in heading:
                raise RuntimeError('Wrong contract schedule returned.')
            if raw:
                return {'text': text, 'schedule': schedule}
            return contract_terms(text, schedule, record['contract'], status)
        finally:
            schedule_page.close()

    def download(self, record, path):
        for attempt in range(3):
            self.check()
            response = None
            try:
                response = self.context.request.get(record['url'], timeout=60000)
                data = response.body()
                valid = response.ok and data.startswith(b'%PDF')
            except Exception:
                # Playwright request errors include cookie headers. Keep those
                # credentials out of the UI and report when a connection drops.
                valid = False
            finally:
                if response is not None:
                    response.dispose()
            if valid:
                path.write_bytes(data)
                return data
            if attempt < 2:
                self.log(f"Retrying invoice {record['invoice']} after an interrupted download ({attempt+1}/2).")
                time.sleep(2 * (attempt + 1))
        raise RuntimeError('Invoice PDF download failed after three attempts: '+record['invoice'])
