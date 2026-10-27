# Deskflow calculations

Open `/deskflow` directly. There is no navigation entry, and `?view=deskflow`
does not open it. Screens and new review exports use proposed-value wording.
On the configured Windows PC, open SBC NAV Updater and connect the digital token.
Choose **Update local workbooks**, then sign in to IREPS if asked.
The shared desktop connection handles IREPS; no browser extension or operator key
entry is needed in the web interface. MCDO and Deskflow serialize browser collection.

The private page has collection controls and an **Update desktop app** button.
After the one-time setup in `MCDO.md`, that button checks GitHub and updates the
Windows companion only when MCDO and Deskflow are idle. Update progress appears
on the page; updates are manual rather than scheduled. Collected commercial
records stay in the local database and are not included in progress responses.
The button waits for an active earnings update, collects pending lots, closed
history and contracts, then writes the configured commercial, parcel and catering
workbooks. Existing verified calculations are recomputed from their saved evidence;
new or changed evidence still requires a supported benchmark and exact identity.
Closed-catalogue collection follows the numbered `menuexpand` action behind the
`next` link and reconciles the visited catalogue count before claiming completion.
A sold catalogue without a bid-detail link retains its outcome and flags the
missing bid evidence; existing sourced rates are preserved. After a full verified
scan, repeated history refreshes for the same covered lot codes recheck the last
30 days and retain the older evidence. New lot codes or explicit date filters
require their requested scan; incomplete legacy scans cannot seed this cache.
Long history scans checkpoint every ten catalogues in the local evidence folder.
An interrupted scan can resume within 24 hours when its filters, lot codes and
catalogue count match. Partial rows stay outside the reviewed evidence until the
complete catalogue count is reconciled.
Missing evidence is written as a workbook note. Existing values and working inputs
are preserved for unresolved rows, and absent lots are appended with blank values.
The result explicitly distinguishes calculated rows from rows needing evidence.
Backups, evidence/file revision checks, Excel locks, ambiguous duplicate checks and
rate-unit checks remain in force. Unrelated workbook content is preserved.

Evidence and audit entries persist in `%LOCALAPPDATA%/RPAssistant/rpassistant.sqlite`,
the existing desktop workspace. Reviews use revision checks to prevent overwriting
changes made since opening a lot. Collection commits only a completed scan; stopping
or failing a scan retains prior saved evidence. New history requires identity review
again. No IREPS award, signature, RP register or transaction is submitted by Deskflow.

The supplied Standard Conditions v2.0 are available at `/deskflow-standard-conditions-v2.pdf`. Clauses 4.4/6,
8, 10/14, 17/18 guide the award and contract-state evidence checks. Clause 11 has a
separate existing-contract fee calculator: no escalation during the first three
years, 10% compounded from year four, or 5% for the stated P&U BOT/ROMT exception.
The re-auction RP rules are retained from the existing local workbook logic and
require the policy/Finance/benchmark reference. SCC v2.0 is not presented as the
authority for those local RP percentages. Proposals remain drafts for approval.

Install with `scripts/install-mcdo-desktop.ps1` using the existing configured Python
and private operator key file. The installer copies the RP reader and rules along
with the desktop server. This PC uses the installed Node/Playwright runtime under
the user's runtime cache; its files must remain installed for catalogue collection.

Checks: `python -m unittest discover -s desktop-companion -p 'test_*.py' -v`,
the retained `RPAssistant/test_rules.py` suite, TypeScript and the Next.js production
build. Live verification includes pending catalogues, closed bid viewer form POSTs,
contract listing, browser connection and saved review downloads.
