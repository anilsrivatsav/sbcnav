import { jsPDF } from "jspdf";

export type IrepsScheduleLot = {
  source_id: string;
  catalogue: string;
  start: string;
  lot: string;
  category: string;
  description: string;
};

const clean = (text: string) => text.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
  .replace(/[\u2010-\u2015]/g, "-").replace(/[\u2018\u2019]/g, "'")
  .replace(/[\u201c\u201d]/g, '"').replace(/[^\x20-\x7e]/g, " ").replace(/\s+/g, " ").trim();

function dateLabel(iso: string, delimiter: string) {
  return iso.slice(0, 10).split("-").reverse().join(delimiter);
}

function auctionModule(catalogue: string, lots: IrepsScheduleLot[]) {
  if (/^SBC-RDN(?:-|\d)/i.test(catalogue)) return "Publicity";
  const modules = lots.map(({ category }) => {
    if (/^Parcel\b/i.test(category)) return "Parcel";
    if (/^Pay\s*(?:and|&)\s*Use/i.test(category)) return "Pay and Use";
    if (/^Parking|^Radio Taxi/i.test(category)) return "Parking";
    if (/^Catering/i.test(category)) return "Catering";
    if (/^ATM\b/i.test(category)) return "ATM";
    if (/^(?:Advertising|Misc|Storage|Food Truck|Content on Demand)/i.test(category)) return "Publicity";
    return clean(category) || "Other";
  });
  return [...new Set(modules)].join(" / ");
}

function describeLots(catalogue: string, lots: IrepsScheduleLot[]) {
  const groups = new Map<string, { separator: string; items: string[] }>();
  const add = (name: string, id: string, separator = " at ") => {
    if (!groups.has(name)) groups.set(name, { separator, items: [] });
    groups.get(name)!.items.push(id);
  };

  for (const lot of lots) {
    const { category, description } = lot;
    const code = clean(lot.lot);
    const station = /^[A-Z]+-SBC-([A-Z0-9]{2,6})-/i.exec(code)?.[1].toUpperCase();
    const coach = /^(\d{5})-SLR-([FR])(\d+)-/i.exec(code);
    const van = /^(\d{5}-\d{5})-VP-(\d+)-/i.exec(code);
    const service = [
      [/food truck/i, "Food truck"], [/battery swapp/i, "Battery swapping"],
      [/health kiosk/i, "Health kiosk"], [/storage facility|digital (?:storage )?lockers?/i, "Storage facility"],
      [/textile (?:stall|store)/i, "Textile store"], [/exclusive brand/i, "Exclusive brand showroom"],
      [/souven[ie]+r/i, "Souvenir and gift shop"], [/parcel packing|two.wheeler packing/i, "Parcel packing"],
    ] as const;

    if (van && /^Parcel/i.test(category)) {
      add("VP", van[1] + " (VP" + van[2] + ")", ": ");
    } else if (coach && /^Parcel/i.test(category)) {
      const label = coach[2].toUpperCase() === "F" ? "FSLR" : "RSLR";
      add(label, coach[1] + (coach[3] === "1" ? "" : ` (${coach[2].toUpperCase()}${coach[3]})`), ": ");
    } else if (station && /^Parking/i.test(category)) {
      add(/mixed/i.test(category) ? "Mixed parking" : clean(category), station);
    } else if (station && /^Pay\s*(?:and|&)\s*Use/i.test(category)) {
      const subject = /toilets?/i.test(category) ? "Pay and Use toilets"
        : /retiring room|dormitor/i.test(description) ? "Retiring rooms and dormitory"
        : /cloak\s*room/i.test(description) ? "Cloakroom"
        : /waiting hall|waiting room/i.test(description) ? "Waiting hall" : clean(category);
      add(subject, station);
    } else if (station && /^Catering/i.test(category)) {
      const unit = /\b(GMU|SMU|MPS)\b/i.exec(code + " " + category)?.[1]?.toUpperCase();
      const stall = /\bCS[- ]?\d+\b/i.exec(description)?.[0];
      add(unit ? unit + " stalls" : "Catering", station + (stall ? ` (${stall})` : ""));
    } else if (station && /^ATM\b/i.test(category)) {
      add("ATM", station);
    } else if (station && /^SBC-RDN(?:-|\d)/i.test(catalogue)) {
      add("Rail Display Network", station);
    } else if (station && /Out of Home/i.test(category)) {
      add("Out-of-Home advertising", station);
    } else {
      const subject = service.find(([pattern]) => pattern.test(category + " " + description))?.[1];
      const trains = /Advertising - Train/i.test(category)
        ? [...new Set(description.match(/\b\d{5}\b/g))].join("/")
        : "";
      if (subject && station) add(subject, station);
      else add(subject || clean(category) || "Lot", trains || code, ": ");
    }
  }

  return [...groups].map(([name, { separator, items }]) => name + separator + items.join(", ")).join(". ");
}

export function makeIrepsSchedulePdf(lots: IrepsScheduleLot[], checkedAt: string) {
  const catalogues = new Map<string, IrepsScheduleLot[]>();
  for (const lot of lots) {
    const group = catalogues.get(lot.source_id);
    if (group) group.push(lot);
    else catalogues.set(lot.source_id, [lot]);
  }
  const ordered = [...catalogues.values()].sort(([a], [b]) =>
    a.start.localeCompare(b.start) || a.catalogue.localeCompare(b.catalogue) || a.source_id.localeCompare(b.source_id)
  );
  const first = ordered[0]?.[0].start;
  const last = ordered.at(-1)?.[0].start;
  const heading = first && last
    ? `AUCTION SCHEDULE FROM ${dateLabel(first, ".")} to ${dateLabel(last, ".")}`
    : "UPCOMING AUCTION SCHEDULE";
  const pdf = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4", compress: true });
  pdf.setProperties({ title: "SBC Division IREPS Auction Schedule" });

  const left = 13;
  const widths = [48, 37, 136, 50];
  const tableWidth = widths.reduce((sum, value) => sum + value);
  const maxY = 187;
  const padding = 2.8;
  const lineHeight = 4.25;
  let y = 13;
  pdf.setDrawColor(48, 58, 68);
  pdf.setTextColor(27, 35, 43);
  pdf.setLineWidth(0.32);

  function cells(lines: string[][], height: number) {
    let x = left;
    for (const [index, width] of widths.entries()) {
      pdf.rect(x, y, width, height);
      const text = lines[index];
      if (text.length) {
        const firstLineY = y + (height - text.length * lineHeight) / 2 + lineHeight * 0.76;
        text.forEach((line, i) => pdf.text(line, x + width / 2, firstLineY + i * lineHeight, { align: "center" }));
      }
      x += width;
    }
    y += height;
  }

  function header() {
    y = 13;
    pdf.setFont("times", "bold").setFontSize(14);
    pdf.rect(left, y, tableWidth, 9);
    pdf.text(heading, left + tableWidth / 2, y + 6.1, { align: "center" });
    y += 9;
    pdf.setFontSize(11);
    cells([["DATE & TIME"], ["MODULE"], ["LOTS"], ["CATALOGUE No."]], 8);
    pdf.setFont("times", "normal").setFontSize(11);
  }

  header();
  for (const group of ordered) {
    const { catalogue, start } = group[0];
    const row = [
      dateLabel(start, "-") + " " + start.slice(11, 16),
      auctionModule(catalogue, group),
      describeLots(catalogue, group),
      clean(catalogue),
    ].map((value, index) => pdf.splitTextToSize(value, widths[index] - padding * 2) as string[]);
    const height = Math.max(7.5, Math.max(...row.map(lines => lines.length)) * lineHeight + 3);
    if (y > 30 && y + height > maxY) {
      pdf.addPage();
      header();
    }
    const maxLines = Math.floor((maxY - y - 3) / lineHeight);
    const lineCount = Math.max(...row.map(lines => lines.length));
    for (let offset = 0; offset < lineCount; offset += maxLines) {
      if (offset) {
        pdf.addPage();
        header();
      }
      const chunk = row.map((lines, index) =>
        offset && lines.length <= maxLines && index !== 2 ? lines : lines.slice(offset, offset + maxLines)
      );
      cells(chunk, Math.max(7.5, Math.max(...chunk.map(lines => lines.length)) * lineHeight + 3));
    }
  }
  if (!ordered.length) {
    pdf.rect(left, y, tableWidth, 10);
    pdf.text("No upcoming SBC Division auctions were listed in IREPS.", left + tableWidth / 2, y + 6.4, { align: "center" });
  }

  for (let page = 1; page <= pdf.getNumberOfPages(); page++) {
    pdf.setPage(page);
    pdf.setFont("times", "normal").setFontSize(9);
    pdf.text(`SBC Division | IREPS E-Auction Leasing | Checked ${dateLabel(checkedAt, "-")} ${checkedAt.slice(11, 16)} IST`, left, 196);
    pdf.text(`${page} / ${pdf.getNumberOfPages()}`, left + tableWidth, 196, { align: "right" });
  }
  return pdf;
}

