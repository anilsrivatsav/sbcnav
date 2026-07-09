import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "C:/Users/CMI PA/OneDrive - PRAGNA VIDYANIKETAN/Documents/Works - PH-53";
const inputPath = `${root}/Untitled spreadsheet.xlsx`;
const outputDir = `${root}/outputs/station_db`;
const outputPath = `${outputDir}/Station_Database.xlsx`;

const input = await FileBlob.load(inputPath);
const sourceWorkbook = await SpreadsheetFile.importXlsx(input);
const sourceSheet = sourceWorkbook.worksheets.getItemAt(0);
const sourceValues = sourceSheet.getUsedRange().values;

const normalizeHeader = (value) =>
  String(value ?? "")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/[^A-Za-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();

const parseDate = (value) => {
  const text = String(value ?? "").trim();
  const match = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!match) return text || null;
  const [, day, month, year] = match;
  return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
};

const parseBlockSectionStation = (value) => {
  const raw = String(value ?? "").trim();
  const find = (...labels) => {
    const labelGroup = labels.join("|");
    const regex = new RegExp(`(?:${labelGroup})\\s*:\\s*([^:;]*?)(?=\\s*(?:Block|Blk|Section|Sec|Stn|Station)\\s*:|$)`, "i");
    const match = raw.match(regex);
    return match?.[1]?.trim() || "";
  };
  const stnScopeRaw = find("Stn", "Station");
  const scopeItems = splitScopeItems(stnScopeRaw);
  return {
    block: find("Block", "Blk"),
    sectionFromBlockSectionStation: find("Section", "Sec"),
    stnScopeRaw,
    scopeItems,
  };
};

const classifyScopeItem = (value) => {
  const original = String(value ?? "").trim();
  const cleaned = original.replace(/^[.\-:,\s]+|[.\-:,\s]+$/g, "").trim();
  const upper = cleaned.toUpperCase();
  if (!cleaned) {
    return { scopeType: "Other", scopeValue: "", stationCode: null };
  }
  if (/\bABSS\b/i.test(cleaned)) {
    return { scopeType: "ABSS", scopeValue: cleaned, stationCode: null };
  }
  if (/\b(DIVISION|DIV|DIVL|DIVISIONAL)\b/i.test(cleaned)) {
    return { scopeType: "Division", scopeValue: cleaned, stationCode: null };
  }
  if (/^[A-Z0-9]{2,8}$/.test(upper)) {
    return { scopeType: "Station", scopeValue: upper, stationCode: upper };
  }
  return { scopeType: "Other", scopeValue: cleaned, stationCode: null };
};

const splitScopeItems = (value) => {
  const text = String(value ?? "").trim();
  if (!text) return [];
  const normalized = text
    .replace(/\r?\n/g, ",")
    .replace(/\s*(?:,|;|\/|&|\+)\s*/g, ",")
    .replace(/\s+\band\b\s+/gi, ",");
  const parts = normalized
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  return (parts.length ? parts : [text]).map(classifyScopeItem);
};

const asNumberOrNull = (value) => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const numeric = Number(String(value ?? "").replace(/,/g, "").trim());
  return Number.isFinite(numeric) && String(value ?? "").trim() !== "" ? numeric : null;
};

const table1HeaderRow = 0;
const table1EndRow = sourceValues.findIndex((row, idx) => idx > table1HeaderRow && row.every((cell) => cell === null || cell === ""));
const table2HeaderRow = sourceValues.findIndex((row, idx) =>
  idx > table1HeaderRow && String(row[0] ?? "").trim().toLowerCase() === "station code"
);

if (table1EndRow < 0 || table2HeaderRow < 0) {
  throw new Error("Could not identify both source tables.");
}

const table1Headers = sourceValues[table1HeaderRow].filter((header) => header !== null && header !== "");
const table2Headers = sourceValues[table2HeaderRow].filter((header) => header !== null && header !== "");
const table1Rows = sourceValues.slice(table1HeaderRow + 1, table1EndRow).filter((row) => row.some((cell) => cell !== null && cell !== ""));
const table2Rows = sourceValues.slice(table2HeaderRow + 1).filter((row) => row.some((cell) => cell !== null && cell !== ""));

const stationCodeIndex = table2Headers.findIndex((header) => normalizeHeader(header) === "station_code");
const stationCodes = new Set(table2Rows.map((row) => String(row[stationCodeIndex] ?? "").trim().toUpperCase()).filter(Boolean));

const t1Index = Object.fromEntries(table1Headers.map((header, index) => [normalizeHeader(header), index]));
const t2Index = Object.fromEntries(table2Headers.map((header, index) => [normalizeHeader(header), index]));

const projectHeaders = [
  "project_id",
  "sn",
  "year_of_sanction",
  "year_ub_works",
  "status",
  "date_of_sanction",
  "short_name_of_work",
  "block_section_station_raw",
  "block",
  "section_from_block_section_station",
  "stn_scope_raw",
  "station_codes",
  "division_scopes",
  "abss_scopes",
  "other_scopes",
  "scope_count",
  "allocation",
  "cost",
  "parent_work",
  "source_section",
  "anticipated_expenditure_jan_mar_2025",
  "remarks",
  "station_master_check",
];

const projectRecords = table1Rows.map((row) => {
  const parsed = parseBlockSectionStation(row[t1Index.block_section_station]);
  const projectId = String(row[t1Index.projectid] ?? "").trim();
  return { row, parsed, projectId };
});

const summarizeScopes = (scopeItems, scopeType) =>
  scopeItems
    .filter((item) => item.scopeType === scopeType)
    .map((item) => item.stationCode ?? item.scopeValue)
    .filter(Boolean)
    .join(", ") || null;

const stationMasterCheck = (scopeItems) => {
  const stationItems = scopeItems.filter((item) => item.scopeType === "Station");
  if (stationItems.length === 0) return "No station scope";
  return stationItems.every((item) => stationCodes.has(item.stationCode)) ? "All station scopes matched" : "One or more station scopes missing";
};

const projectRows = projectRecords.map(({ row, parsed, projectId }) => [
    projectId,
    asNumberOrNull(row[t1Index.sn]),
    row[t1Index.year_of_sanction] ?? null,
    row[t1Index.year_ub_works] ?? null,
    row[t1Index.status] ?? null,
    parseDate(row[t1Index.date_of_sanction]),
    row[t1Index.short_name_of_work] ?? null,
    row[t1Index.block_section_station] ?? null,
    parsed.block || null,
    parsed.sectionFromBlockSectionStation || null,
    parsed.stnScopeRaw || null,
    summarizeScopes(parsed.scopeItems, "Station"),
    summarizeScopes(parsed.scopeItems, "Division"),
    summarizeScopes(parsed.scopeItems, "ABSS"),
    summarizeScopes(parsed.scopeItems, "Other"),
    parsed.scopeItems.length,
    row[t1Index.allocation] ?? null,
    asNumberOrNull(row[t1Index.cost]),
    row[t1Index.parent_work] ?? null,
    row[t1Index.section] ?? null,
    asNumberOrNull(row[t1Index.anticipated_expenditure_for_revised_grant_jan_2025_mar2025]),
    row[t1Index.remarks] ?? null,
    stationMasterCheck(parsed.scopeItems),
]);

const stationHeaders = [
  "station_code",
  "station_name",
  "division",
  "zone",
  "section_name",
  "cmi",
  "den",
  "sr_den",
  "categorisation",
  "earnings_range",
  "passenger_range",
  "passenger_footfall",
  "platforms_raw",
  "number_of_platforms",
  "platform_type",
];

const stationRows = table2Rows.map((row) => [
  String(row[t2Index.station_code] ?? "").trim().toUpperCase(),
  row[t2Index.station_name] ?? null,
  row[t2Index.division] ?? null,
  row[t2Index.zone] ?? null,
  row[t2Index.section] ?? null,
  row[t2Index.cmi] ?? null,
  row[t2Index.den] ?? null,
  row[t2Index.sr_den] ?? null,
  row[t2Index.categorisation] ?? null,
  row[t2Index.earnings_range] ?? null,
  row[t2Index.passenger_range] ?? null,
  asNumberOrNull(row[t2Index.passenger_footfall]),
  asNumberOrNull(row[t2Index.platforms]),
  asNumberOrNull(row[t2Index.number_of_platforms]),
  row[t2Index.platform_type] ?? null,
]);

const stationLookup = new Map(stationRows.map((row) => [row[0], row]));
const linkHeaders = [
  "project_id",
  "scope_sequence",
  "scope_type",
  "scope_value",
  "station_code",
  "station_name",
  "division",
  "zone",
  "match_status",
];
const linkRows = projectRecords.flatMap(({ projectId, parsed }) =>
  parsed.scopeItems.length
    ? parsed.scopeItems.map((item, index) => {
        const station = item.stationCode ? stationLookup.get(item.stationCode) : null;
        return [
          projectId,
          index + 1,
          item.scopeType,
          item.scopeValue,
          item.stationCode,
          station?.[1] ?? null,
          station?.[2] ?? null,
          station?.[3] ?? null,
          item.scopeType === "Station"
            ? station
              ? "Matched"
              : "Missing in station master"
            : "Not a station-master lookup",
        ];
      })
    : [[projectId, null, "Other", null, null, null, null, null, "No scope parsed"]],
);

const issueHeaders = ["issue_type", "record_key", "field", "detail"];
const validationIssues = [];
for (const { projectId, parsed } of projectRecords) {
  if (parsed.scopeItems.length === 0) {
    validationIssues.push(["Missing parsed scope", projectId, "stn_scope_raw", "No scope could be parsed from Block Section Station"]);
  }
  for (const item of parsed.scopeItems) {
    if (item.scopeType === "Station" && !stationCodes.has(item.stationCode)) {
      validationIssues.push(["Missing station master record", projectId, "station_code", `${item.stationCode} is not present in Stations`]);
    }
  }
}
const seenStations = new Set();
for (const row of stationRows) {
  if (!row[0]) validationIssues.push(["Missing station code", row[1] ?? "(blank)", "station_code", "Station master row has no station code"]);
  if (row[0] && seenStations.has(row[0])) validationIssues.push(["Duplicate station code", row[0], "station_code", "Station code appears more than once"]);
  seenStations.add(row[0]);
}

const workbook = Workbook.create();
const addSheet = (name, headers, rows, tableName) => {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  sheet.getRangeByIndexes(0, 0, rows.length + 1, headers.length).values = [headers, ...rows];
  const table = sheet.tables.add(
    sheet.getRangeByIndexes(0, 0, rows.length + 1, headers.length).address,
    true,
    tableName,
  );
  table.style = "TableStyleMedium2";
  sheet.freezePanes.freezeRows(1);
  sheet.getRangeByIndexes(0, 0, 1, headers.length).format = {
    fill: "#1F4E79",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  sheet.getUsedRange().format.autofitColumns();
  sheet.getUsedRange().format.autofitRows();
  return sheet;
};

const overview = workbook.worksheets.add("Overview");
overview.showGridLines = false;
overview.getRange("A1:B10").values = [
  ["Station Database", ""],
  ["Source workbook", "Untitled spreadsheet.xlsx"],
  ["Projects loaded", projectRows.length],
  ["Stations loaded", stationRows.length],
  ["Project scope links", linkRows.length],
  ["Validation issues", validationIssues.length],
  ["Primary project key", "project_id"],
  ["Primary station key", "station_code"],
  ["Scope rule", "Each parsed Stn item becomes one Project_Scope_Link row"],
  ["Station join rule", "Only scope_type = Station joins to Stations.station_code; Division, ABSS, and Other remain separate scope rows"],
];
overview.getRange("A1:B1").merge();
overview.getRange("A1").format = { fill: "#1F4E79", font: { bold: true, color: "#FFFFFF", size: 16 } };
overview.getRange("A2:A10").format = { font: { bold: true }, fill: "#D9EAF7" };
overview.getRange("A1:B10").format.autofitColumns();

const projectsSheet = addSheet("Projects", projectHeaders, projectRows, "Projects");
const stationsSheet = addSheet("Stations", stationHeaders, stationRows, "Stations");
const linkSheet = addSheet("Project_Scope_Link", linkHeaders, linkRows, "ProjectScopeLink");
const validationSheet = addSheet("Validation_Issues", issueHeaders, validationIssues.length ? validationIssues : [["No issues", "", "", "All parsed keys are present and unique."]], "ValidationIssues");
const raw1Sheet = addSheet(
  "Source_Table1",
  table1Headers.map(normalizeHeader),
  table1Rows.map((row) => row.slice(0, table1Headers.length)),
  "SourceTable1",
);
const raw2Sheet = addSheet(
  "Source_Table2",
  table2Headers.map(normalizeHeader),
  table2Rows.map((row) => row.slice(0, table2Headers.length)),
  "SourceTable2",
);

const columnLetter = (index) => {
  let n = index + 1;
  let letters = "";
  while (n > 0) {
    n -= 1;
    letters = String.fromCharCode(65 + (n % 26)) + letters;
    n = Math.floor(n / 26);
  }
  return letters;
};
const projectCol = (header) => columnLetter(projectHeaders.indexOf(header));
projectsSheet.getRange(`${projectCol("date_of_sanction")}2:${projectCol("date_of_sanction")}${projectRows.length + 1}`).format.numberFormat = "yyyy-mm-dd";
projectsSheet.getRange(`${projectCol("cost")}2:${projectCol("cost")}${projectRows.length + 1}`).format.numberFormat = "#,##0";
projectsSheet.getRange(`${projectCol("anticipated_expenditure_jan_mar_2025")}2:${projectCol("anticipated_expenditure_jan_mar_2025")}${projectRows.length + 1}`).format.numberFormat = "#,##0";
stationsSheet.getRange(`L2:N${stationRows.length + 1}`).format.numberFormat = "#,##0";

for (const sheet of [overview, projectsSheet, stationsSheet, linkSheet, validationSheet, raw1Sheet, raw2Sheet]) {
  const used = sheet.getUsedRange();
  used.format.wrapText = true;
  used.format.autofitColumns();
  used.format.autofitRows();
}

await fs.mkdir(outputDir, { recursive: true });

const checks = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 6000,
  tableMaxRows: 5,
  tableMaxCols: 8,
});
console.log(checks.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
});
console.log(errors.ndjson);

for (const sheetName of ["Overview", "Projects", "Stations", "Project_Scope_Link", "Validation_Issues"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(`${outputDir}/${sheetName}.png`, new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`Saved ${outputPath}`);
