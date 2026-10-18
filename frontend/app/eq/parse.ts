export type EqData = {
  applicationDate: string; diaryNo: string; train: string; journeyDate: string; pnr: string;
  from: string; to: string; travelClass: string; berths: string; passengers: string[];
  mobile: string; requesterName: string; designation: string; address: string;
  reason: string; applicantSignature: string; officer: string; officerMobile: string;
};
export const blankEq = (): EqData => ({
  applicationDate: new Date().toLocaleDateString('en-GB'), diaryNo: '', train: '', journeyDate: '', pnr: '',
  from: '', to: '', travelClass: '', berths: '', passengers: ['', '', ''], mobile: '',
  requesterName: '', designation: '', address: '', reason: '', applicantSignature: '', officer: '', officerMobile: '',
});
const pick = (text: string, patterns: RegExp[]) => {
  for (const pattern of patterns) { const match = text.match(pattern); if (match?.[1]?.trim()) return match[1].trim().replace(/[.,;]+$/, ''); }
  return '';
};
export function parseEqMessage(message: string): Partial<EqData> {
  const text = message.replace(/\r/g, '').trim();
  const lines = text.split('\n').map(line => line.trim()).filter(Boolean);
  const result: Partial<EqData> = {};
  const tenDigitNumbers = [...text.matchAll(/\b\d{10}\b/g)].map(match => match[0]);
  const labelledPnr = pick(text, [/\bPNR\s*(?:no\.?|number)?\s*[:#-]?\s*(\d{10})\b/i]);
  const labelledMobile = pick(text, [/(?:mobile|phone|contact|mob)\s*(?:no\.?|number)?\s*[:#-]?\s*(?:\+91[-\s]?)?([6-9]\d{9})\b/i]);
  result.pnr = labelledPnr || tenDigitNumbers.find(number => number !== labelledMobile && !/^[6-9]/.test(number)) || tenDigitNumbers.find(number => number !== labelledMobile) || '';
  result.train = pick(text, [/\b(?:train|tr\.?\s*no\.?|train\s*number)\s*[:#-]?\s*(\d{5})\b/i, /\b(\d{5})\b/]);
  result.journeyDate = pick(text, [/(?:date of journey|journey date|doj|travel date|journey on|travelling on)\s*[:#-]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})/i, /\b(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})\b/]);
  result.from = pick(text, [/(?:^|\n)\s*from\s*[:#-]\s*([^\n,;]+)/i, /\bfrom\s+([A-Z][A-Z ]{1,25}?)(?=\s+to\b|[,.;\n]|$)/i]);
  result.to = pick(text, [/(?:^|\n)\s*to\s*[:#-]\s*([^\n,;]+)/i, /\bto\s+([A-Z][A-Z ]{1,25}?)(?=\s+(?:on|by|in|for|class|pnr)\b|[,.;\n]|$)/i]);
  const stationPair = text.match(/\b([A-Z]{2,5})\s*[-–]\s*([A-Z]{2,5})\b/);
  if (stationPair) { result.from = stationPair[1]; result.to = stationPair[2]; }
  result.travelClass = pick(text, [/(?:class|travel class)\s*[:#-]?\s*(1A|2A|3A|3E|SL|CC|EC|2S|FC|AC first|sleeper)\b/i, /\b(1A|2A|3A|3E|SL|CC|EC|2S|FC)\b/i]);
  result.berths = pick(text, [/(?:berths?|seats?|pax|passengers?)\s*(?:required|requested)?\s*[:#-]?\s*(\d{1,2})\b/i, /\b(\d{1,2})\s*(?:berths?|seats?)\b/i]);
  result.mobile = labelledMobile || [...tenDigitNumbers].reverse().find(number => number !== result.pnr && /^[6-9]/.test(number)) || '';
  result.diaryNo = pick(text, [/(?:diary|reference)\s*(?:no\.?|number)?\s*[:#-]\s*([^\n,;]+)/i]);
  result.requesterName = pick(text, [/(?:requested by|applicant|recommending person)\s*[:#-]\s*([^\n,;]+)/i]);
  result.designation = pick(text, [/(?:designation|design\.?|desig\.?|post)\s*[:#-]\s*([^\n,;]+)/i]);
  result.address = pick(text, [/(?:address|office)\s*[:#-]\s*([^\n]+)/i]);
  result.reason = pick(text, [/(?:special reason|reason(?: for journey)?|purpose)\s*[:#-]\s*([^\n]+)/i]);
  result.officer = pick(text, [/(?:recommending officer)\s*[:#-]\s*([^\n,;]+)/i]);
  const namedLines = lines.filter(line => /^(?:passenger\s*\d*|pax\s*\d*|\d+[.)])\s*[:.)-]?\s*\S/i.test(line));
  const passengers = namedLines.map(line => line.replace(/^(?:passenger\s*\d*|pax\s*\d*|\d+[.)])\s*[:.)-]?\s*/i, '').trim()).filter(Boolean).slice(0, 3);
  const shorthandPassenger = lines.find(line => /^[A-Za-z][A-Za-z .'-]{1,50}\s*\+\s*\d{1,2}$/.test(line));
  if (shorthandPassenger) { result.passengers = [shorthandPassenger, '', '']; result.berths = String(Number(shorthandPassenger.match(/\+\s*(\d{1,2})$/)?.[1] || 0) + 1); }
  else if (passengers.length) result.passengers = [...passengers, ...Array(Math.max(0, 3 - passengers.length)).fill('')];
  else { const inline = pick(text, [/(?:passenger names?|names? of passengers)\s*[:#-]\s*([^\n]+)/i]); if (inline) result.passengers = [...inline.split(/\s*[,;]\s*/).slice(0, 3), '', '', ''].slice(0, 3); }
  if (!result.berths && result.passengers?.filter(Boolean).length) result.berths = String(result.passengers.filter(Boolean).length);
  return Object.fromEntries(Object.entries(result).filter(([, value]) => value !== '' && value !== undefined));
}
