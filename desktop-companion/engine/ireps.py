"""Read-only IREPS browser workflow, using a separate Chrome window."""
import re, time
from datetime import date, timedelta
from playwright.sync_api import TimeoutError
from urllib.parse import urljoin, urlparse
from core import relevant, key, day, contract_terms
from incremental import invoice_needed

HOME = 'https://www.ireps.gov.in/epsn/home/showHome.do'

class IncompleteResultsError(RuntimeError):
    """A result set could not be read completely."""


class FilteredResultError(IncompleteResultsError):
    """The exact-contract result retained category-wide pagination metadata."""

class DenseResultsError(IncompleteResultsError):
    def __init__(self, total):
        super().__init__(f'IREPS returned {total} results; split the search before paging.')
        self.total = total

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
        self.open_home()
        self.log('Sign in to IREPS in the separate Chrome window. The app never reads your password or OTP.')
        for _ in range(1200):
            if self.cancelled():
                raise RuntimeError('Cancelled.')
            if self.page.get_by_role('link', name='Payments', exact=True).is_visible():
                self.log('IREPS sign-in confirmed.')
                return
            time.sleep(1)
        raise RuntimeError('IREPS sign-in timed out after 20 minutes.')

    def open_home(self):
        # The authenticated controls are checked separately. Waiting for the
        # whole IREPS document can stall on resources unrelated to the search.
        self.page.goto(HOME, wait_until='commit', timeout=18000)

    def navigate(self, mode):
        self.check()
        menu = self.page.get_by_role('link', name=mode, exact=True)
        if not menu.is_visible():
            self.open_home()
        self.log('Opening IREPS ' + mode + ' menu.')
        self.click_navigation_link(mode)
        link = 'Payments Received' if mode == 'Payments' else 'View Contracts'
        self.log('Opening IREPS ' + link + ' page.')
        with self.page.expect_navigation(wait_until='commit'):
            self.click_navigation_link(link)
        self.page.locator('#menuLink').wait_for(state='visible')
        self.page.wait_for_function("document.querySelector('#menuLink')?.options.length > 0", polling=250)

    def click_navigation_link(self, label):
        link = self.page.get_by_role('link', name=label, exact=True)
        self.click_read_control(link, label)

    def click_read_control(self, link, label):
        try:
            link.wait_for(state='visible', timeout=15000)
        except TimeoutError:
            self.check()
            raise RuntimeError('IREPS read control unavailable: ' + label) from None
        # These controls only open or refresh source records. Their handlers
        # do not need a foreground mouse or a pointer animation.
        link.evaluate("""(element) => {
          if (element.matches(':disabled, [aria-disabled="true"]')) throw Error('IREPS read control is disabled');
          element.click();
        }""", timeout=15000)

    def search(self, category, kind=None, start=None, end=None, contract='', subcategory=None):
        self.check()
        self.page.locator('#regCat').select_option(label=category)
        subcategory_control = self.page.locator('#regSubCat')
        if subcategory is None:
            subcategory_control.select_option(label='---All---')
        else:
            subcategory_control.select_option(value=subcategory)
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
        self.click_read_control(self.page.get_by_role('button', name='Search', exact=True), 'Search')
        self.wait_results(stamp)
        if subcategory is not None and subcategory_control.input_value() != subcategory:
            raise IncompleteResultsError('IREPS changed the selected subcategory.')
        if start is not None:
            selected = [self.page.locator('#'+field).input_value() for field in ('ddmmyyDateformat1','ddmmyyDateformat2')]
            if selected != [start,end]:
                raise RuntimeError('IREPS changed the selected date filters. No spreadsheet writes will occur.')

    def wait_results(self, previous_document):
        # Pagination links have href="#" plus form submission. The hash change
        # can satisfy a navigation wait while the OLD result page still exists.
        # Wait for a different document with a parsed result body. Images or
        # other unrelated resources can keep the full page loading indefinitely.
        self.page.wait_for_function(
            "(stamp) => performance.timeOrigin !== stamp && document.readyState !== 'loading' && /(?:\\d+\\s*Records Found|No (?:results|records) Found)/i.test(document.body?.innerText || '')",
            arg=previous_document, polling=250)

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

    def all_rows(self, mode, filtered=False, max_rows=None):
        body = self.page.locator('body').inner_text()
        m = re.search(r'(\d+)\s*Records Found', body)
        empty = re.search(r'No (?:results|records) Found', body, re.I)
        # IREPS can retain a positive category count when the contract table
        # explicitly says the selected dates have no results.
        if empty and (not m or mode == 'contracts' and not filtered):
            if not self.page_rows(mode) and not self.page.locator('a[onclick*="menuexpand("]').count():
                return []
        if not m:
            raise IncompleteResultsError('IREPS result count missing.')
        total, page_num, seen, output = int(m[1]), 1, set(), []
        if max_rows is not None and total > max_rows:
            raise DenseResultsError(total)
        while True:
            self.check()
            batch = self.page_rows(mode)
            if filtered and not batch and total:
                raise FilteredResultError('Exact-contract results are empty but the displayed count is positive.')
            signature = repr(batch)
            if signature in seen:
                if filtered:raise FilteredResultError('Exact-contract pagination repeated a page.')
                raise IncompleteResultsError(f'IREPS repeated page {page_num} of {mode}.')
            if not batch and len(output) < total:
                raise IncompleteResultsError(f'IREPS returned an empty page at {len(output)} of {total}.')
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
                raise IncompleteResultsError(f'IREPS pagination stopped at {len(output)} of {total}.')
            page_num = next_page
            stamp = self.page.evaluate('performance.timeOrigin')
            self.click_read_control(link, f'results page {page_num}')
            self.wait_results(stamp)
        if len(output) != total:
            if filtered:raise FilteredResultError(f'Exact-contract row count mismatch: {len(output)} / {total}.')
            raise IncompleteResultsError(f'IREPS row count mismatch: {len(output)} / {total}.')
        return output

    def read_category_rows(self, navigation, category, mode, *, filtered=False, **filters):
        dated_query = not filtered and mode in ('contracts', 'paid') and filters.get('start') and filters.get('end')
        # A normal IREPS pager group has ten numbered pages of ten records.
        max_rows = 100 if dated_query and day(filters['start']) < day(filters['end']) else None
        try:
            self.search(category, **filters)
        except TimeoutError:
            self.check()
            self.log('Retrying the interrupted IREPS search: ' + category)
            self.navigate(navigation)
            self.search(category, **filters)
        try:
            return self.all_rows(mode, filtered=filtered, max_rows=max_rows)
        except FilteredResultError:
            raise
        except (IncompleteResultsError, TimeoutError) as exc:
            self.check()
            if isinstance(exc, DenseResultsError) and mode == 'contracts' and 'subcategory' not in filters:
                subcategories = self.page.locator('#regSubCat').evaluate(
                    "(el) => [...el.options].filter(o => !o.disabled && o.value && o.value !== '-1').map(o => o.value)")
                # Wide category menus are cheaper to read in date windows
                # than through dozens of individual searches.
                if 1 < len(subcategories) <= 10:
                    try:
                        rows = self.read_subcategories(navigation, category, filters, subcategories, exc.total)
                    except (IncompleteResultsError, TimeoutError):
                        self.check()
                        self.log(f'{category} subcategory query timed out. Retrying the full category with its numbered pager.')
                        self.navigate(navigation)
                        self.search(category, **filters)
                        try:
                            return self.all_rows(mode)
                        except (IncompleteResultsError, TimeoutError):
                            self.check()
                        rows = None
                    if rows is not None:
                        return rows
            if dated_query and day(filters['start']) < day(filters['end']):
                return self.read_date_partitions(navigation, category, mode, filters)
            if dated_query:
                self.log(f'{category} on {filters["start"]}: {str(exc).splitlines()[0]}')
                raise
            self.log('Retrying the interrupted category: ' + category)
            self.navigate(navigation)
            self.search(category, **filters)
            return self.all_rows(mode, filtered=filtered)

    def read_subcategories(self, navigation, category, filters, subcategories, displayed_count):
        observed = {tuple(row['cells']) for row in self.page_rows('contracts')}
        self.log(f'Reading {category} across {len(subcategories)} IREPS subcategories.')
        rows = {}
        for index, subcategory in enumerate(subcategories, 1):
            self.check()
            self.log(f'Checking {category} subcategory {index}/{len(subcategories)}.')
            for row in self.read_category_rows(navigation, category, 'contracts',
                                               **{**filters, 'subcategory':subcategory}):
                rows[tuple(row['cells'])] = row
        if len(rows) >= displayed_count and observed.issubset(rows):
            return list(rows.values())
        self.log(f'{category} subcategories did not reproduce the displayed count. Checking the date windows.')
        return None

    def read_date_partitions(self, navigation, category, mode, filters):
        """Read disjoint date windows when IREPS cannot advance its result pager."""
        first, last = day(filters['start']), day(filters['end'])
        date_column = 1 if mode == 'contracts' else 7
        if first >= last:
            raise IncompleteResultsError(
                f'IREPS could not read the complete {category} result on {first:%d/%m/%Y}.')
        middle = first + (last - first) // 2
        windows = ((first, middle), (middle + timedelta(days=1), last))
        lower, upper = date(2020, 1, 1), date(date.today().year + 10, 1, 1)
        if mode == 'paid' and first < lower < upper <= last:
            # Keep the full due-date range. Read the long outer stretches
            # once instead of repeatedly bisecting them around recent awards.
            windows = ((first, lower - timedelta(days=1)), (lower, upper - timedelta(days=1)), (upper, last))
        self.log(f'Reading smaller IREPS date windows for {category}: {first:%d/%m/%Y} to {last:%d/%m/%Y}.')
        rows = []
        undated_contracts = set()
        for start, end in windows:
            self.check()
            window = self.read_category_rows(
                navigation, category, mode,
                **{**filters, 'start': start.strftime('%d/%m/%Y'), 'end': end.strftime('%d/%m/%Y')})
            for row in window:
                value = row['cells'][date_column]
                if mode == 'contracts' and value in ('', '-'):
                    # Unsigned rows can have no contract date, and can appear
                    # in more than one source window. Keep each observed row once.
                    signature = tuple(row['cells'])
                    if signature in undated_contracts:
                        continue
                    undated_contracts.add(signature)
                elif not start <= day(value) <= end:
                    raise IncompleteResultsError(f'IREPS returned {category} records outside the selected date window.')
                rows.append(row)
        return rows

    def receipt_filters(self, category):
        if category != 'Parking':
            return {}
        # The routine earnings scope includes radio taxi only. The full
        # contract inventory still reads the entire Parking category.
        self.page.locator('#regCat').select_option(label=category)
        options = self.page.locator('#regSubCat').evaluate(
            "(el) => [...el.options].filter(o => !o.disabled && o.value !== '-1').map(o => [o.text.trim(), o.value])")
        matches = [value for label, value in options if 'RADIOTAXI' in key(label)]
        return {'subcategory': matches[0]} if len(matches) == 1 else {}

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
            cache_key=(cat,from_due,to_due)
            filters = self.receipt_filters(cat)
            try:
                scanned = self.read_category_rows('Payments', cat, 'paid', filtered=bool(contract),
                    kind='Previous Payments Made', start=from_due, end=to_due, contract=contract, **filters)
            except FilteredResultError as exc:
                warning=f'IREPS exact-contract pagination is inconsistent for {contract}. Verifying the category results and filtering this contract locally.'
                self.warnings.append(warning)
                self.log('Notice: '+warning)
                if cache_key not in category_cache:
                    # Start from the normal payment view. Clearing the text
                    # field on the faulty exact-contract result can retain
                    # server-side filtered state across pagination.
                    self.navigate('Payments')
                    category_cache[cache_key] = self.read_category_rows('Payments', cat, 'paid',
                        kind='Previous Payments Made', start=from_due, end=to_due, **filters)
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
            for row in self.read_category_rows('Payments', cat, 'failed', kind='Payment Failures (Beyond grace period)', **self.receipt_filters(cat)):
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
            for row in self.read_category_rows('Contracts', cat, 'contracts', start=start, end=end, **self.receipt_filters(cat)):
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
            self.click_read_control(link, 'Contract')
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
