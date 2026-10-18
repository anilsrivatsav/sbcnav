import { timingSafeEqual } from 'node:crypto';
import { GoogleAuth } from 'google-auth-library';
import { Booking, categories, nextIdentifiers, normalizeDate, normalizeTime, parseISO } from '../../../../lib/eauction-scheduler';

export const runtime = 'nodejs';

const defaultSpreadsheetId = '1n_aQpueOSE8OYl5y5KW3_NuYFg7Knlw3BYslllEp1zk';

type ValuesResponse = { valueRanges?: { range: string; values?: string[][] }[] };
type SheetMeta = { sheets?: { properties?: { sheetId?: number; title?: string } }[] };
const monthNames = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];

function scheduleMonth(title: string): number {
  const match = title.trim().toLowerCase().match(/^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*['-]?(\d{2}|\d{4})$/);
  if (!match) return -1;
  const year = Number(match[2]);
  return (year < 100 ? 2000 + year : year) * 12 + monthNames.indexOf(match[1]);
}

function sameSecret(actual: string | null, expected: string): boolean {
  if (!actual) return false;
  const a = Buffer.from(actual), b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

function sheetRange(title: string, cells: string): string {
  return `'${title.replaceAll("'", "''")}'!${cells}`;
}

async function sheetsRequest<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...init?.headers },
    cache: 'no-store',
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body?.error?.message || `Google Sheets returned ${response.status}.`);
  return body as T;
}

function invalidBooking(value: unknown): value is Booking {
  if (!value || typeof value !== 'object') return false;
  const item = value as Partial<Booking>;
  return typeof item.id === 'string' && !!parseISO(item.date || '') && !!normalizeTime(item.time || '')
    && categories.some(category => category.name === item.category)
    && ['scheduled', 'cancelled', 'withdrawn'].includes(item.status || '');
}

export async function POST(request: Request) {
  const syncKey = process.env.SHEETS_SYNC_KEY;
  const credentials = process.env.GOOGLE_SERVICE_ACCOUNT_JSON;
  if (!syncKey || !credentials) return Response.json({ error: 'Google Sheet sync is not configured. See DEPLOYMENT.md.' }, { status: 503 });
  if (!sameSecret(request.headers.get('x-sync-key'), syncKey)) return Response.json({ error: 'Invalid sync key.' }, { status: 401 });

  let booking: Booking;
  try {
    const body = await request.json();
    if (!invalidBooking(body.booking)) throw new Error('Invalid schedule row.');
    booking = body.booking;
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : 'Invalid request.' }, { status: 400 });
  }

  try {
    const serviceAccount = JSON.parse(credentials) as { client_email?: string; private_key?: string };
    if (!serviceAccount.client_email || !serviceAccount.private_key) throw new Error('Service account JSON is incomplete.');
    const auth = new GoogleAuth({ credentials: serviceAccount, scopes: ['https://www.googleapis.com/auth/spreadsheets'] });
    const token = await auth.getAccessToken();
    if (!token) throw new Error('Could not obtain a Google access token.');

    const spreadsheetId = process.env.GOOGLE_SHEET_ID || defaultSpreadsheetId;
    const base = encodeURIComponent(spreadsheetId);
    const meta = await sheetsRequest<SheetMeta>(`${base}?fields=sheets.properties(sheetId,title)`, token);
    const sheets = (meta.sheets || []).map(sheet => sheet.properties).filter((sheet): sheet is { sheetId: number; title: string } => typeof sheet?.sheetId === 'number' && !!sheet.title);
    const configuredGid = process.env.GOOGLE_SHEET_GID;
    const target = configuredGid
      ? sheets.find(sheet => sheet.sheetId === Number(configuredGid))
      : sheets.filter(sheet => scheduleMonth(sheet.title) >= 0).sort((a, b) => scheduleMonth(b.title) - scheduleMonth(a.title))[0];
    if (!target) throw new Error(configuredGid ? `Target sheet tab with gid ${configuredGid} was not found.` : 'No monthly schedule tab was found.');
    const targetId = target.sheetId;

    const query = new URLSearchParams();
    for (const sheet of sheets) query.append('ranges', sheetRange(sheet.title, 'A:F'));
    const all = await sheetsRequest<ValuesResponse>(`${base}/values:batchGet?${query.toString()}`, token);
    const rowsBySheet = sheets.map((sheet, index) => ({ ...sheet, rows: all.valueRanges?.[index]?.values || [] }));
    // A synced row remains editable after a newer monthly tab is created.
    if (booking.sheetRow && booking.sheetTab) {
      const originalSheet = rowsBySheet.find(sheet => sheet.title === booking.sheetTab);
      if (!originalSheet || booking.sheetRow < 1 || originalSheet.rows[booking.sheetRow - 1]?.[4] !== booking.catalogueId) {
        return Response.json({ error: 'This sheet row changed. Refresh the schedule before syncing again.' }, { status: 409 });
      }
      const row = booking.sheetRow;
      const values = [[booking.status === 'scheduled' ? 'Scheduled' : booking.status === 'cancelled' ? 'Cancelled' : 'Withdrawn']];
      await sheetsRequest(`${base}/values/${encodeURIComponent(sheetRange(originalSheet.title, `F${row}`))}?valueInputOption=RAW`, token, { method: 'PUT', body: JSON.stringify({ values }) });
      return Response.json({ row, tab: originalSheet.title, scheduleId: booking.scheduleId, catalogueId: booking.catalogueId, syncedAt: new Date().toISOString() });
    }

    const existing = rowsBySheet.flatMap(sheet => sheet.rows.map((row, index) => ({ sheet, row, index: index + 1 })))
      .find(entry => entry.row[4] === booking.catalogueId && normalizeDate(entry.row[0] || '') === booking.date && normalizeTime(entry.row[1] || '') === booking.time && entry.row[2] === booking.category);
    if (existing) {
      const values = [[booking.status === 'scheduled' ? 'Scheduled' : booking.status === 'cancelled' ? 'Cancelled' : 'Withdrawn']];
      await sheetsRequest(`${base}/values/${encodeURIComponent(sheetRange(existing.sheet.title, `F${existing.index}`))}?valueInputOption=RAW`, token, { method: 'PUT', body: JSON.stringify({ values }) });
      return Response.json({ row: existing.index, tab: existing.sheet.title, scheduleId: booking.scheduleId, catalogueId: booking.catalogueId, syncedAt: new Date().toISOString() });
    }

    const existingBookings = rowsBySheet.flatMap(sheet => sheet.rows.map((row, index) => ({
      id: `${sheet.sheetId}-${index}`, date: '', time: '', category: row[2] || '', subject: '',
      status: /cancelled|withdrawn/i.test(row[5] || '') ? 'cancelled' as const : 'scheduled' as const,
      scheduleId: row[3] || '', catalogueId: row[4] || '',
    })));
    const identifiers = nextIdentifiers(booking.category, existingBookings, Number(booking.date.slice(0, 4)));
    const [year, month, day] = booking.date.split('-');
    const values = [[`${day}-${month}-${year}`, String(Number(booking.time.slice(0, 2))), booking.category, identifiers.scheduleId, identifiers.catalogueId, booking.status === 'scheduled' ? 'Scheduled' : booking.status === 'cancelled' ? 'Cancelled' : 'Withdrawn']];
    const appended = await sheetsRequest<{ updates?: { updatedRange?: string } }>(`${base}/values/${encodeURIComponent(sheetRange(target.title, 'A:F'))}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`, token, { method: 'POST', body: JSON.stringify({ values }) });
    const row = Number(appended.updates?.updatedRange?.match(/![A-Z]+(\d+)/)?.[1]);
    if (!row) throw new Error('Google Sheet accepted the row but did not return its position. Check the sheet before retrying.');
    return Response.json({ row, tab: target.title, ...identifiers, syncedAt: new Date().toISOString() });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : 'Could not sync the row.' }, { status: 502 });
  }
}
