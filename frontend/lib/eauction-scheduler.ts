export type Holiday = { date: string; name: string };
export type Booking = { id: string; date: string; time: string; category: string; subject: string; status: 'scheduled' | 'cancelled' | 'withdrawn'; noticeDate?: string; scheduleId?: string; catalogueId?: string; source?: boolean; sourceFile?: string; sheetRow?: number; sheetTab?: string; syncedAt?: string };
export type Proposal = { earliest: string; date: string; time: string; skipped: { date: string; reason: string }[]; daysAfterNotice: number; category: string; subject: string; noticeDate: string };

export const categories = [
  { name: 'Parking', time: '15:00' }, { name: 'Parcel', time: '11:00' },
  { name: 'Catering', time: '11:00' }, { name: 'MPS', time: '15:00' },
  { name: 'Miscellaneous', time: '12:00' }, { name: 'Pay & Use', time: '15:00' },
  { name: 'Advertising', time: '12:00' }, { name: 'ATM', time: '15:00' },
  { name: 'PMBJAK', time: '12:00' }, { name: 'CLK / SMVB', time: '15:00' },
  { name: 'Food truck', time: '12:00' }, { name: 'Other', time: '12:00' }
] as const;

// Latest active EA numbers and the latest catalogue number in the linked workbook.
// Update this snapshot when the sheet changes, or import a current schedule CSV.
const sheetScheduleNumbers: Record<string, number> = {
  Parking: 170, Parcel: 156, Catering: 189, MPS: 187,
  Miscellaneous: 136, 'Pay & Use': 75, Advertising: 87, ATM: 31,
  PMBJAK: 3, 'CLK / SMVB': 68, 'Food truck': 119
};
const sheetCatalogueNumber = 1003;
const idFormats: Record<string, { schedule: string; catalogue: string; suffix?: string; catalogueYear?: boolean }> = {
  Parking: { schedule: 'SBC-PRK-EA', catalogue: 'SBC-PRK' },
  Parcel: { schedule: 'SBC-Parcel-EA', catalogue: 'SBC-PRCL' },
  Catering: { schedule: 'SBC-CATG-EA', catalogue: 'SBC-CTG' },
  MPS: { schedule: 'SBC-MPS-EA', catalogue: 'SBC-MPS' },
  Miscellaneous: { schedule: 'SBC-Misc-EA', catalogue: 'SBC-Misc' },
  'Pay & Use': { schedule: 'SBC-PnU-EA', catalogue: 'SBC-PnU' },
  Advertising: { schedule: 'SBC-ADVT-EA', catalogue: 'SBC-Advt' },
  ATM: { schedule: 'SBC-ATM-EA', catalogue: 'SBC-ATM' },
  PMBJAK: { schedule: 'SBC-PMBJAK-EA', catalogue: 'SBC-PMBJK', suffix: 'F25', catalogueYear: false },
  'CLK / SMVB': { schedule: 'SBC-CLK-EA', catalogue: 'SBC-CLK' },
  'Food truck': { schedule: 'SBC-Misc-FT-', catalogue: 'SBC-FoodTruck', catalogueYear: false }
};

function idCategory(value: string): string {
  const category = value.trim().toLowerCase().replace(/\s+/g, ' ');
  if (/^(parking|park)/.test(category)) return 'Parking';
  if (/^parcel/.test(category)) return 'Parcel';
  if (/^(catering|catg)/.test(category)) return 'Catering';
  if (category === 'mps') return 'MPS';
  if (/food\s*truck/.test(category)) return 'Food truck';
  if (/^(misc|other)/.test(category)) return 'Miscellaneous';
  if (/^(pnu|pay\s*(?:&|n|and)\s*use)/.test(category)) return 'Pay & Use';
  if (/^(advt|advertising|ooh)/.test(category)) return 'Advertising';
  if (category === 'atm') return 'ATM';
  if (/^(pmbjak|pmbjk)/.test(category)) return 'PMBJAK';
  if (/^clk/.test(category)) return 'CLK / SMVB';
  return value;
}

function scheduleNumber(value?: string): number {
  return Number(value?.match(/(?:EA|FT)[-\s]*(\d+)/i)?.[1] || 0);
}
function catalogueNumber(value?: string): number {
  return Math.max(0, ...(value?.match(/\d+/g) || []).map(Number).filter(n => n >= 500 && (n < 2000 || n > 2100)));
}

export function nextIdentifiers(category: string, bookings: Booking[], year: number): { scheduleId: string; catalogueId: string } {
  const key = idCategory(category);
  const format = idFormats[key] || idFormats.Miscellaneous;
  const sequence = Math.max(sheetScheduleNumbers[key] || sheetScheduleNumbers.Miscellaneous,
    ...bookings.filter(item => idCategory(item.category) === key).map(item => scheduleNumber(item.scheduleId))) + 1;
  const catalogue = Math.max(sheetCatalogueNumber, ...bookings.map(item => catalogueNumber(item.catalogueId))) + 1;
  const yearSuffix = String(year).slice(-2);
  return {
    scheduleId: `${format.schedule}${sequence}-${format.suffix || yearSuffix}`,
    catalogueId: `${format.catalogue}-${catalogue}${format.catalogueYear === false ? '' : `-${yearSuffix}`}`
  };
}

// Read-only snapshot from the linked Auction Schedule workbook, October 2026.
export const sourceBookings: Booking[] = [
  ['2026-10-22','11:00','Parcel','SBC-Parcel-EA155-26','SBC-PRCL-986-26'],
  ['2026-10-22','12:00','Miscellaneous','SBC-Misc-EA132-26','SBC-Misc-991-26'],
  ['2026-10-22','15:00','Pay & Use','SBC-PnU-EA74-26','SBC-PnU-988-26'],
  ['2026-10-23','11:00','Parcel','SBC-Parcel-EA156-26','SBC-PRCL-987-26'],
  ['2026-10-23','12:00','Miscellaneous','SBC-Misc-EA130-26','SBC-Misc-989-26'],
  ['2026-10-23','15:00','Catering','SBC-CATG-EA189-26','SBC-CTG-992-26'],
  ['2026-10-23','15:00','MPS','SBC-MPS-EA187-26','SBC-MPS-993-26'],
  ['2026-10-26','15:00','Miscellaneous','SBC-Misc-EA131-26','SBC-Misc-994-26'],
  ['2026-11-02','12:00','Miscellaneous','SBC-MSSBP-EA136-26','SBC-Misc-1001-26'],
  ['2026-11-02','13:00','Parking','SBC-PRK-EA169-26','SBC-PRK-1000-26'],
  ['2026-11-02','15:00','Pay & Use','SBC-PnU-EA75-26','SBC-PnU-1002-26'],
  ['2026-11-03','13:00','Parking','SBC-PRK-EA170-26','SBC-PRK-1003-26'],
  ['2026-11-09','12:00','Miscellaneous','SBC-Misc-EA135-26','SBC-Misc-999-26'],
  ['2026-11-10','12:00','Miscellaneous','SBC-Misc-EA133-26','SBC-Misc-997-26'],
  ['2026-11-11','12:00','Miscellaneous','SBC-Misc-EA134-26','SBC-Misc-998-26']
].map(([date, time, category, scheduleId, catalogueId], i) => ({ id: `source-${i}`, date, time, category, scheduleId, catalogueId, subject: 'Existing sheet booking', status: 'scheduled', source: true }));

export function parseISO(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [y,m,d] = value.split('-').map(Number);
  const result = new Date(Date.UTC(y,m-1,d));
  return result.getUTCFullYear() === y && result.getUTCMonth() === m-1 && result.getUTCDate() === d ? result : null;
}
export function iso(date: Date): string { return date.toISOString().slice(0,10); }
export function addDays(date: Date, days: number): Date { const copy = new Date(date); copy.setUTCDate(copy.getUTCDate()+days); return copy; }
export function labelDate(value: string): string { const date=parseISO(value); return date ? new Intl.DateTimeFormat('en-IN',{weekday:'long',day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(date) : value; }
export function labelTime(value: string): string { const [h,m]=value.split(':').map(Number); return `${h%12||12}:${String(m).padStart(2,'0')} ${h>=12?'PM':'AM'}`; }
export function normalizeTime(raw: string): string | null {
  const value=raw.trim();
  const hour=Number(value);
  if(Number.isInteger(hour)&&hour>=0&&hour<24)return String(hour).padStart(2,'0')+':00';
  const twentyFour=value.match(/^([01]?\d|2[0-3]):([0-5]\d)$/);
  if(twentyFour)return twentyFour[1].padStart(2,'0')+':'+twentyFour[2];
  const twelve=value.match(/^(\d{1,2})(?::([0-5]\d))?\s*(AM|PM)$/i);
  if(!twelve)return null;
  const h=Number(twelve[1]);if(h<1||h>12)return null;
  const normalized=(h%12)+(twelve[3].toUpperCase()==='PM'?12:0);
  return String(normalized).padStart(2,'0')+':'+(twelve[2]||'00');
}

export function findDate(input: {noticeDate:string; time:string; holidays:Holiday[]; bookings:Booking[]; category:string; subject:string}): Proposal {
  const start=parseISO(input.noticeDate);
  if (!start) throw new Error('Enter a valid notice date.');
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(input.time)) throw new Error('Select a valid time.');
  const earliest=addDays(start,15);
  const holidays=new Map(input.holidays.map(h=>[h.date,h.name]));
  const occupied=new Set(input.bookings.filter(b=>b.status==='scheduled').map(b=>`${b.date}|${b.time}`));
  const skipped: Proposal['skipped']=[];
  for(let offset=0;offset<3660;offset++) {
    const day=addDays(earliest,offset), date=iso(day), weekday=day.getUTCDay();
    const reason=weekday===0||weekday===6?'Weekend':holidays.get(date) || (occupied.has(`${date}|${input.time}`)?`${labelTime(input.time)} already booked`:'');
    if(reason){skipped.push({date,reason});continue;}
    return {earliest:iso(earliest),date,time:input.time,skipped,daysAfterNotice:15+offset,category:input.category,subject:input.subject,noticeDate:input.noticeDate};
  }
  throw new Error('No free date was found within ten years.');
}

export function readCSV(text: string): string[][] {
  const rows:string[][]=[]; let row:string[]=[], field='', quoted=false;
  for(let i=0;i<text.length;i++){
    const char=text[i];
    if(char==='"'&&quoted&&text[i+1]==='"'){field+='"';i++;}
    else if(char==='"')quoted=!quoted;
    else if(char===','&&!quoted){row.push(field);field='';}
    else if((char==='\n'||char==='\r')&&!quoted){if(char==='\r'&&text[i+1]==='\n')i++;row.push(field);if(row.some(x=>x.trim()))rows.push(row);row=[];field='';}
    else field+=char;
  }
  row.push(field);if(row.some(x=>x.trim()))rows.push(row);
  return rows;
}
export function csv(rows: (string|number)[][]): string { return rows.map(row=>row.map(value=>`"${String(value).replaceAll('"','""')}"`).join(',')).join('\r\n'); }
export function normalizeDate(raw:string):string|null {
  const value=raw.trim();
  if(parseISO(value))return value;
  const numeric=value.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
  if(numeric){const candidate=`${numeric[3]}-${numeric[2].padStart(2,'0')}-${numeric[1].padStart(2,'0')}`;return parseISO(candidate)?candidate:null;}
  const named=value.match(/^(\d{1,2})[-/ ]([A-Za-z]{3,9})[-/ ,]+(\d{2}|\d{4})$/);
  if(!named)return null;
  const months=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];
  const month=months.indexOf(named[2].slice(0,3).toLowerCase())+1;
  const year=named[3].length===2?2000+Number(named[3]):Number(named[3]);
  const candidate=`${year}-${String(month).padStart(2,'0')}-${named[1].padStart(2,'0')}`;
  return month>0&&parseISO(candidate)?candidate:null;
}
