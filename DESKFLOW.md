# Deskflow calculations

Open `/deskflow` directly. There is no navigation entry, and `?view=deskflow`
does not open it. Screens and new review exports use proposed-value wording.
On the configured Windows PC, open SBC NAV Updater and connect the digital token.
Choose **Update Deskflow**, then sign in to IREPS if asked.
The shared desktop connection handles IREPS; no browser extension or operator key
entry is needed in the web interface. MCDO and Deskflow serialize browser collection.

The private page has collection controls and an **Update desktop app** button.
After the one-time setup in `MCDO.md`, that button checks GitHub and updates the
Windows companion only when MCDO and Deskflow are idle. Update progress appears
on the page; updates are manual rather than scheduled. Collected commercial
records stay in the local database and are not included in progress responses.
The **Update Deskflow** command performs two-way sync: it collects pending
lots, closed history and contracts, writes the selected local workbooks, and then
uploads those saved files to the website archive. A background archive upload is
labelled separately and does not claim that Excel files were updated. Current
website values and notes read the exact matching lot/catalogue workbook rows.
The review panel shows a separate draft proposal, its arithmetic and short
justification. Save source evidence, mark the exact proposal reviewed, then choose
**Save reviewed proposals**. Only reviewed, unchanged proposals can replace Excel
values. Both views use the same short justification; the full sourced working is
retained in the audit. A later manual Excel edit requires another review.
New lots are appended even when their value is pending. Existing manually saved
values are retained for review unless the workbook still matches the app's last
saved version. Existing verified calculations are recomputed from their saved evidence;
new or changed evidence still requires a supported benchmark and exact identity.
Closed-catalogue collection follows the numbered `menuexpand` action behind the
`next` link and reconciles the visited catalogue count before claiming completion.
A sold catalogue without a bid-detail link retains its outcome and flags the
missing bid evidence; existing sourced rates are preserved. After a full verified
scan, repeated history refreshes recheck the recent 30-day window and retain older
evidence. Previously scheduled or unresolved lots remain on a persistent follow-up
list beyond that window until an explicit Sold, Rejected, No Bids or Withdrawn
result is collected. An auction date passing or a lot leaving the pending schedule
does not settle its outcome. Due catalogues override the unchanged-listing cache;
future lots are followed up only after their auction date. This happens when the
user runs an update; it does not install a background schedule.

The one-time library covers every visible closed-catalogue lot, independent of
the current RP-pending lot codes, from 2022 onward. Completed catalogue records
are committed atomically to SQLite after each catalogue. They survive interruption,
app restarts and more than 24 hours. Unchanged older catalogue listings are reused;
changed listings are read again. Coverage remains incomplete until the entire
catalogue manifest reconciles. Legacy partial evidence never implies full coverage.
Detailed accepted rates are collected for current proposal codes and their verified
aliases; unrelated sold lots retain outcomes with bid detail flagged as pending.
Unavailable viewers retain their outcomes and require separately sourced evidence.

All populated rows and cells in every sheet of the three selected workbooks are
imported into the local library with file hash, worksheet, row, original formula,
cached value, style and hidden-row provenance. New file revisions are imported
without deleting prior versions. Exact lot-code history is automatic; changed
codes require a verified asset/scope link. Text-similar workbook rows are suggestions.
Missing evidence is written as a workbook note. Existing values and working inputs
are preserved for unresolved rows, and absent lots are appended with blank values.
The result explicitly distinguishes calculated rows from rows needing evidence.
Backups, evidence/file revision checks, Excel locks, ambiguous duplicate checks and
rate-unit checks remain in force. Unrelated workbook content is preserved.

Evidence and audit entries persist in `%LOCALAPPDATA%/RPAssistant/rpassistant.sqlite`,
the existing desktop workspace. Reviews use revision checks to prevent overwriting
changes made since opening a lot. Collection retains completed catalogue checkpoints;
stopping or failing a scan does not claim full coverage. New history requires identity review
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
