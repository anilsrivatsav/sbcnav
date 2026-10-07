# Historical publicity earnings

The publicity workspace and `/publicity-earnings` read a versioned PostgreSQL
receipt ledger through FastAPI. Only the workbook tab named **Main Sheet** is
imported. Other tabs, including pivot tables and drill-down copies, are ignored.

## Source analysis

The maintained source is Earnings Master, **Main Sheet**. Import complete
exports rather than monthly deltas. Amounts sum populated source cells and
round to paise after aggregation. Current receipt counts, dates and totals
are verified from each source export instead of stored in repository docs.

Comparisons use common source month buckets, not equal day cutoffs. A current
month may be incomplete. PUB and NFR overlap and must never be added together.

Rows without a month remain in annual totals, but do not
enter monthly totals or comparisons. Missing amounts remain null, and an
all-missing aggregate displays no value. Date/Year/Month disagreements follow
the source Year and Month without silently changing them. Three non-numeric
With GST Total cells (rows 455, 456, 668) are retained in source data and left
null as amounts. An ambiguous date such as `10-1-2025 ?` remains unparsed.
The import reports row-level quality notes for the current workbook.

Policy new is used when populated, with Policy as fallback. Original spelling
and classification are retained, including similarly named policies. No
station or contract match is inferred from free-text locations. The original
27 named columns remain in the database for audit; raw contact/address/GST
identity columns are omitted from the read API. Cumulative and Target Watch
are preserved as source fields and are never summed.

## API and import

- `GET /api/publicity-earnings?year=2026-27&policy=RDN&head=Z-611&q=receipt`
  returns yearly/monthly totals, common-month comparisons, policy totals,
  filtered receipts, source metadata and quality notes.
- `POST /api/publicity-earnings/import?dry_run=true` accepts multipart `file`
  and validates Main Sheet without writes. This is the default.
- `POST /api/publicity-earnings/import?dry_run=false` atomically imports and
  activates the validated complete ledger.

Importing identical Main Sheet values is a no-op even if the filename or other
tabs change. Changed workbooks become new snapshots; prior imports and rows
are retained. A transaction and a locked singleton pointer serialize activation.
Rows within a workbook are never deduplicated by amount or firm because
identical receipts may be legitimate. Import a complete ledger, not a monthly
delta. An import affects only this historical ledger, not registry payments.

CLI (run with the backend dependencies and configured DATABASE_URL):

```sh
python backend/publicity_earnings.py '/path/Earnings upto 26-27.xlsx'
python backend/publicity_earnings.py '/path/Earnings upto 26-27.xlsx' --apply
```

## Oracle Cloud deployment

Use the existing Oracle PostgreSQL service and its environment configuration.
Apply Alembic revision `0030_publicity_earnings` before importing. The backend
Docker entrypoint applies migrations before starting FastAPI. The production
frontend must be built with NEXT_PUBLIC_API_URL pointing to the deployed
Oracle API, as in the existing hosting configuration.

Take a database backup using the existing `/opt/sbcnav/backups` volume before
deploying. Build/deploy the updated backend image and frontend using the normal
deployment process; then upload the workbook in the new publicity UI, review
the preview totals, and import it. Verify source row counts, receipt dates,
each year's PUB/NFR totals and the current-year receipt ledger against Main Sheet.

The web workflow and browser authentication connector are documented in [MCDO](MCDO.md).

For rollback, reactivate a verified earlier import ID by updating the
`publicity_earnings_current` row with dataset `main_sheet` in a transaction.
Do not downgrade the schema to roll back an import: a downgrade drops the
historical ledger. Existing application tables are unaffected by this revision.

## Verification

Run `python -m unittest discover -s backend -p test_publicity_earnings.py -v`
from the repository root. Tests cover sheet scope, monetary precision,
missing-month comparisons, invalid amount/formula rejection, source retention,
filtering, idempotent imports, version retention and rollback.

The supplied workbook has additionally been validated through the API and the
migration in an isolated local SQLite database, with all yearly totals
reconciled after import. A production PostgreSQL migration/import still requires
access to the Oracle server. Source workbook data is not bundled in the public
frontend or committed as a seed file.
