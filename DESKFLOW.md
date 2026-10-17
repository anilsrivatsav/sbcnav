# Deskflow RP review

Open the **Deskflow** navigation tab, `/?view=deskflow`, or `/deskflow`.
On the configured Windows PC, open SBC NAV Updater and connect the digital token.
Choose **Sign in & collect pending lots**, then sign in to IREPS if asked.
The shared desktop connection handles IREPS; no browser extension or operator key
entry is needed in the web interface. MCDO and Deskflow serialize browser collection.

Choose a pending lot. Under **Collect previous auctions and contracts**, set the
history window and collect the evidence required for the asset. Closed history
matches exact lot numbers; renamed assets require sourced earlier evidence in the
review. A contract candidate is a suggestion and must be verified against the lot.
Review the benchmark, accepted bid rate, outcome, awardee, dates, rate unit and
applicable conditions, then **Save evidence & calculate RP**. Missing evidence is
reported instead of generating a proposal. **Download saved RP review** exports
all current proposals and missing evidence as an Excel-compatible CSV.

Evidence and audit entries persist in `%LOCALAPPDATA%/RPAssistant/rpassistant.sqlite`,
the existing desktop workspace. Reviews use revision checks to prevent overwriting
changes made since opening a lot. Collection commits only a completed scan; stopping
or failing a scan retains prior saved evidence. New history requires identity review
again. No IREPS award, signature, RP register or transaction is submitted by Deskflow.

The supplied Standard Conditions v2.0 are linked inside the review. Clauses 4.4/6,
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
