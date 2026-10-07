# MCDO source updater

SBC NAV has an MCDO navigation tab and a standalone `/mcdo` page. Vercel hosts
the UI. The existing Oracle FastAPI/PostgreSQL service owns previews, writes,
verification, import history and the receipt ledger. Supabase is not used.

The workflow is **IREPS sign-in → Check IREPS → review preview → Update sheets
& Oracle**. A separate **Sync existing sheets to Oracle** operation imports the
latest complete sources without collecting IREPS again. Only Earnings Master
**Main Sheet** and Master **E Auction** are managed.

IREPS requires the user's physical DSC token and signer. Ordinary web pages
cannot read another site's authenticated tabs. The browser connector provides
that connection without a Windows updater. Sign in directly on IREPS; the
connector never extracts passwords, PINs, cookies or private keys or transmits them to SBC NAV. Authenticated requests to IREPS use the browser's existing session.
It only operates IREPS read/search controls and extracts contract/payment
evidence. Sheet writes and DB imports happen on Oracle.

## Install and configure

1. Deploy backend migrations through `0031_mcdo_sync` and this source.
2. Configure `MCDO_GOOGLE_CREDENTIALS` as the absolute path of an existing
   Google service-account JSON credential mounted read-only in the backend
   container. Enable Google Sheets API and grant that account edit access to
   the two configured source workbooks. Credentials never enter the frontend.
3. Configure a unique `MCDO_ADMIN_TOKEN` of at least 32 random characters in
   Oracle's backend environment. Operators enter it in the MCDO tab; it is
   retained only in page memory. Every preview/evidence/write/history API
   requires this token. Public MCDO reporting does not.
4. Build the connector zip with `scripts/package-mcdo-connector.ps1` before
   building/deploying the frontend. Preserve `NEXT_PUBLIC_API_URL` pointing to
   the existing Oracle API.
5. In Chrome/Edge, extract the downloaded connector, open the browser extension
   manager, enable Developer mode, choose Load unpacked and select its folder.
   Reload SBC NAV. This grants scripting access only to IREPS; the bridge runs
   only on the configured SBC NAV production origin.
   A signed Web Store release can replace unpacked installation after review.
6. Connect the DSC token, click Sign in to IREPS, authenticate there, return to
   MCDO, enter the operator key, and click Check IREPS. Keep SBC NAV open during
   collection. Review invoice counts, amounts, source warnings and failures.

## Integrity and recovery

- The collector reads all visible pages for all configured categories. Ordinary
  parking is excluded; Radio Taxi is retained. A small documented IREPS contract
  count discrepancy is reported, with statuses applied only to listed contracts.
- Invoice PDFs are validated against invoice number, contract, total, GST and
  allocation before a preview is accepted. New invoices need their PDFs and
  official agreements/payment schedules. No missing record establishes payment
  or closure. Duplicate invoice numbers do not create duplicate earnings.
- Source snapshots and plans live in PostgreSQL. Both sources are checked for
  manual edits before a write, and each is checked again immediately beforehand.
  Avoid editing source sheets during an update; Sheets does not expose a
  cross-workbook transaction or a conditional cell-write operation.
- API cell writes preserve filters, unrelated formatting and validation. Each
  workbook batch is atomic. Each source and its IREPS Status Sync report are
  read back before a phase is marked verified.
- A failed second workbook leaves the first verified checkpoint intact. Resume
  checks before/after values and skips already-present changes. Oracle is loaded
  only after both source workbooks verify. DB imports are idempotent; prior
  publicity ledgers are retained. Registry and ledger imports use separate
  transactions, so a failed ledger phase can safely be retried.
- PostgreSQL advisory locking serializes writers across backend processes. An
  interrupted job can be recovered after five minutes only when no updater
  owns the lock, then resumed from the saved preview. Earlier-day previews
  require a fresh check. Restarted browser collection requires a fresh check;
  it has no sheet side effects.

## Verification and limits

Run `python -m unittest discover -s backend -p 'test_*.py' -v`, the frontend
production build, and JavaScript syntax checks. Deployment verification must
include a real token-authenticated IREPS scan, Google preview/apply/readback,
Oracle totals and the Vercel MCDO view. Unit/build checks do not establish that
production authentication or deployment succeeded. Contract schedules currently
support the same verified quarterly format as the original updater. A changed
IREPS layout, unsupported schedule or payment format stops before writes.

The MCDO report shows selected-month PUB/NFR, fiscal year-to-month PUB, running
contracts and CSV export, with the full historical earnings report below. PUB
and NFR overlap and must not be added. Monthly totals exclude unallocated rows;
annual totals retain them.
