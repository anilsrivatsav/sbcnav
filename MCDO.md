# MCDO source updater

## Current Windows-backed web workflow (17 October 2026)

The MCDO page now controls `desktop-companion/server.py` on the operator's PC.
It uses the working Python IREPS collector in `desktop-companion/engine`, including
pagination recovery and PDF retries. It sends original evidence to the existing
Oracle validation/apply endpoints. Google Sheets API writes preserve filters;
the old desktop clipboard writer is not used by the web workflow.

Install once with `scripts/install-mcdo-desktop.ps1 -Python <existing-updater-python>
-KeyFile <private-operator-key-file>`. This creates a desktop shortcut, Windows
sign-in shortcut and `sbcnav-updater://open` launcher. The private key remains
under LocalAppData and is never returned to browser JavaScript. No extension is
needed. Chrome may ask for local network access to reach the desktop connection.

The local server listens only on 127.0.0.1:48722, validates the exact Host and
production Origin, and requires JSON for commands. MCDO accepts four fixed
actions. The same connection also serves the fixed Deskflow review/collection
actions described in DESKFLOW.md. It cannot proxy arbitrary API paths or execute
page-supplied code.
On another PC the helper must be installed and privately configured there.

The primary button is **Check for new payments**. Authentication takes place in
the same dedicated Chrome profile as the Windows updater. Dates are read afresh
from Sheets by Oracle. Original rows and invoice PDFs are validated before writes.
Progress and complete evidence persist locally; server write checkpoints persist
in Oracle. Closing the web page does not stop the job. Resume checks the server
before retrying a write. After a PC restart, incomplete collection requires a fresh
check; complete evidence and partial writes can be resumed. Payment scans use the
desktop collector's full installment range and filter actual receipt dates; this
avoids losing late payments on old installment schedules.

Verification: `python -m unittest discover -s desktop-companion -p test_server.py -v`
and the frontend production build. A real IREPS token sign-in remains necessary to
verify a new end-to-end collection. The sections below describe the retained legacy
extension/server implementation; the extension UI is no longer the primary entry.

SBC NAV has an MCDO navigation tab and a standalone `/mcdo` page. Vercel hosts
the UI. The existing Oracle FastAPI/PostgreSQL service owns previews, writes,
verification, import history and the receipt ledger. Supabase is not used.

The primary workflow is **Update now**. SBC NAV detects IREPS sign-in, waits
for authentication when needed, checks evidence, updates both Google Sheets,
verifies their values, imports into Oracle and refreshes the report.
Report filters and connection/recovery controls are collapsed. An optional
**Import existing sheets only** action skips IREPS collection. Only Earnings
Master **Main Sheet** and Master **E Auction** are managed.

The main page now has **Update earnings and contracts**, **Continue saved
update**, and one safe **Pause after current operation** control. Numbered
progress is read-only by default. Individual controls and manual administrator
sign-in are under Connection setup and other options, with descriptions of
what the alternate actions do.

Connector 1.0.6 can reconnect an authorized computer automatically, including
after an eight-hour web session expires. Prepare its private folder with
`scripts/pair-mcdo-connector.py --key-file <existing-private-operator-key>
--destination <private-folder-outside-this-repository>` and load that folder
once in Chrome/Edge. The pairing file stays on the computer; never commit,
publish, email or share it. The public ZIP contains an empty pairing file.
The extension sends the existing operator key only to the fixed SBC NAV
HTTPS session endpoint; it never returns the key to page JavaScript. Backend
authentication remains required. Only the credential-bearing session endpoint
accepts the extension's cross-origin login; all write endpoints retain the
same-origin and verified-session guards.

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
   Oracle's backend environment. Operators enter it once to sign in. The Vercel proxy stores a signed eight-hour session in an HttpOnly, Secure, SameSite cookie; it never stores the operator key. Every preview/evidence/write/history API
   requires this token. Public MCDO reporting does not.
4. Build the connector zip with `scripts/package-mcdo-connector.ps1` before
   building/deploying the frontend. Preserve `NEXT_PUBLIC_API_URL` pointing to
   the existing Oracle API.
5. In Chrome/Edge, extract the downloaded connector, open the browser extension
   manager, enable Developer mode, choose Load unpacked and select its folder.
   Reload SBC NAV. This grants scripting access only to IREPS; the bridge runs
   only on the configured SBC NAV production origin.
   A signed Web Store release can replace unpacked installation after review.
6. Connect the DSC token, sign in to the updater once, and click Update now.
   Authenticate on IREPS if requested. Keep SBC NAV open during collection.
   The connector detects sign-in and continues automatically. Validated changes
   are applied automatically; incomplete or conflicting evidence stops the
   update. Numbered results turn Updated only after readback verifies each stage.

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
