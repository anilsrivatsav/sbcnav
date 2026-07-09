const SHEET_ID_STATIONS = "1UdRgQQPEkak1fUTuVH7jIn5R4sE3szAhM4VZJOdFIOU";
const SHEET_ID_WORKS = "1rJbfhcnEVuGMwGkT8yBObb9Bk5Hx0uU224EGxfplGRc";
const WORKS_GID = "590791228";

const stationHeaderMap = {
  "station code": "stationCode",
  "station name": "stationName",
  division: "division",
  zone: "zone",
  section: "section",
  cmi: "cmi",
  den: "den",
  "sr.den": "srDen",
  categorisation: "categorisation",
  "earnings range": "earningsRange",
  "passenger range": "passengerRange",
  "passenger footfall": "passengerFootfall",
  platforms: "platforms",
  "number of platforms": "numberOfPlatforms",
  "platform type": "platformType",
  parking: "parking",
  "pay-and-use": "payAndUse",
  "no of trains dealt": "trainsDealt",
  "tkts per day": "ticketsPerDay",
  "pass per day": "passengersPerDay",
  "earnings per day": "earningsPerDay",
  "footfalls per day": "footfallsPerDay",
};

const unitHeaderMap = {
  "sl no.": "slNo",
  "unit no.": "unitNo",
  "type of unit": "typeOfUnit",
  station: "stationCode",
  "station category": "stationCategory",
  "old category": "oldCategory",
  "pf no": "pfNo",
  "pegged location": "peggedLocation",
  "reservation category": "reservationCategory",
  "type of allotment": "allotmentType",
  "name of licensee": "licenseeName",
  "license fee": "licenseFee",
  "contract from": "contractFrom",
  "contract to": "contractTo",
  "unit status": "unitStatus",
};

const worksHeaderMap = {
  projectid: "projectId",
  "year of sanction": "yearOfSanction",
  "year ub works": "yearUbWorks",
  status: "status",
  "date of sanction": "dateOfSanction",
  "short name of work": "shortNameOfWork",
  "block section station": "blockSectionStation",
  allocation: "allocation",
  "engg. remarks (as on 06.08.24)": "enggRemarks",
  "if ub?": "ifUb",
  "parent work": "parentWork",
  section: "section",
  "anticipated expenditure for revised grant jan 2025 - mar2025": "anticipatedExpenditure",
  remarks: "remarks",
};

const numericFields = new Set([
  "passengerFootfall",
  "numberOfPlatforms",
  "trainsDealt",
  "ticketsPerDay",
  "passengersPerDay",
  "earningsPerDay",
  "footfallsPerDay",
  "slNo",
  "pfNo",
  "anticipatedExpenditure",
]);

const moneyFields = new Set(["licenseFee"]);

const state = {
  view: "stations",
  search: "",
  category: "All",
  division: "All",
  section: "All",
  platform: "All",
  unitCategory: "All",
  unitType: "All",
  unitStatus: "All",
  workScope: "All",
  workStatus: "All",
  sort: "name",
};

const els = {
  syncButton: document.querySelector("#syncButton"),
  syncStatus: document.querySelector("#syncStatus"),
  searchInput: document.querySelector("#searchInput"),
  categoryFilter: document.querySelector("#categoryFilter"),
  divisionFilter: document.querySelector("#divisionFilter"),
  sectionFilter: document.querySelector("#sectionFilter"),
  platformFilter: document.querySelector("#platformFilter"),
  categoryChips: document.querySelector("#categoryChips"),
  sortSelect: document.querySelector("#sortSelect"),
  results: document.querySelector("#results"),
  emptyState: document.querySelector("#emptyState"),
  resultCount: document.querySelector("#resultCount"),
  totalStations: document.querySelector("#totalStations"),
  totalCategories: document.querySelector("#totalCategories"),
  totalUnits: document.querySelector("#totalUnits"),
  totalFootfall: document.querySelector("#totalFootfall"),
  resultsTitle: document.querySelector("#resultsTitle"),
  viewEyebrow: document.querySelector("#viewEyebrow"),
  viewTitle: document.querySelector("#viewTitle"),
  viewHint: document.querySelector("#viewHint"),
  categoryLabel: document.querySelector("#categoryLabel"),
  divisionLabel: document.querySelector("#divisionLabel"),
  sectionLabel: document.querySelector("#sectionLabel"),
  platformLabel: document.querySelector("#platformLabel"),
  dialog: document.querySelector("#stationDialog"),
  dialogCode: document.querySelector("#dialogCode"),
  dialogTitle: document.querySelector("#dialogTitle"),
  dialogDetails: document.querySelector("#dialogDetails"),
  closeDialog: document.querySelector("#closeDialog"),
  navItems: Array.from(document.querySelectorAll(".nav-item")),
};

const setSyncStatus = (message, tone = "neutral") => {
  els.syncStatus.textContent = message;
  els.syncStatus.dataset.tone = tone;
};

let db = null;
let SQL = null;
let currentResults = [];

const sql = {
  stations: [],
  units: [],
  works: [],
  workLinks: [],
};

const cleanValue = (value) => {
  const text = String(value ?? "").trim();
  if (!text || text.toUpperCase() === "#N/A") return "";
  return text;
};

const normalizeHeader = (value) => cleanValue(value).toLowerCase();

const toNumber = (value) => {
  const text = cleanValue(value).replace(/[₹?,]/g, "");
  if (!text) return null;
  const numeric = Number(text);
  return Number.isFinite(numeric) ? numeric : null;
};

const formatNumber = (value) => (value === null || value === undefined || value === "" ? "Not available" : new Intl.NumberFormat("en-IN").format(value));
const formatDate = (value) => value || "Not available";
const getCellValue = (cell) => (cell ? cell.v ?? cell.f ?? "" : "");

const parseCSVRows = (csv) => {
  const lines = csv.trim().split(/\r?\n/);
  const rows = [];
  let current = "";
  let inQuotes = false;
  for (const line of lines) {
    current += (current ? "\n" : "") + line;
    for (const ch of line) {
      if (ch === '"') inQuotes = !inQuotes;
    }
    if (!inQuotes) {
      rows.push(current);
      current = "";
    }
  }
  if (current) rows.push(current);
  return rows.map((row) => {
    const cells = [];
    let cell = "";
    let quoted = false;
    for (let i = 0; i < row.length; i++) {
      const ch = row[i];
      if (ch === '"') {
        if (quoted && row[i + 1] === '"') {
          cell += '"';
          i++;
        } else {
          quoted = !quoted;
        }
      } else if (ch === "," && !quoted) {
        cells.push(cell);
        cell = "";
      } else {
        cell += ch;
      }
    }
    cells.push(cell);
    return cells.map((value) => value.replace(/^"|"$/g, ""));
  });
};

const fetchCsv = async (sheetId, query) => {
  const response = await fetch(`https://docs.google.com/spreadsheets/d/${sheetId}/gviz/tq?tqx=out:csv&${query}`);
  return await response.text();
};

const mapSheetRows = (table, headerMap) => {
  const headers = (table.cols ?? []).map((col) => headerMap[normalizeHeader(col.label ?? col.id ?? "")] ?? null);
  return (table.rows ?? [])
    .map((row) => {
      const item = {};
      headers.forEach((key, index) => {
        if (!key) return;
        const rawValue = getCellValue(row.c[index]);
        item[key] = numericFields.has(key) ? toNumber(rawValue) : moneyFields.has(key) ? cleanValue(rawValue).replace(/[₹?]/g, "").trim() : cleanValue(rawValue);
      });
      return item;
    })
    .filter((item) => Object.values(item).some(Boolean));
};

const fetchTabJson = async (sheetId, sheetName = "", gid = "") => {
  const url = new URL(`https://docs.google.com/spreadsheets/d/${sheetId}/gviz/tq`);
  if (sheetName) url.searchParams.set("sheet", sheetName);
  if (gid) url.searchParams.set("gid", gid);
  url.searchParams.set("tqx", "out:json");
  const response = await fetch(url);
  const text = await response.text();
  const json = text.replace(/^\/\*O_o\*\/\s*/, "").replace(/^google\.visualization\.Query\.setResponse\(/, "").replace(/\);?\s*$/, "");
  return JSON.parse(json).table;
};

const loadSqlJs = () =>
  new Promise((resolve, reject) => {
    if (window.initSqlJs) {
      resolve(window.initSqlJs);
      return;
    }
    const script = document.createElement("script");
    script.src = "https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.11.0/sql-wasm.js";
    script.onload = () => resolve(window.initSqlJs);
    script.onerror = () => reject(new Error("Could not load SQL runtime."));
    document.head.append(script);
  });

const initDatabase = async () => {
  const initSqlJs = await loadSqlJs();
  SQL = await initSqlJs({
    locateFile: (file) => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.11.0/${file}`,
  });
  db = new SQL.Database();
  db.run(`
    CREATE TABLE stations (
      station_code TEXT PRIMARY KEY,
      station_name TEXT,
      division TEXT,
      zone TEXT,
      section TEXT,
      cmi TEXT,
      den TEXT,
      sr_den TEXT,
      categorisation TEXT,
      earnings_range TEXT,
      passenger_range TEXT,
      passenger_footfall INTEGER,
      platforms TEXT,
      number_of_platforms INTEGER,
      platform_type TEXT,
      parking TEXT,
      pay_and_use TEXT,
      trains_dealt INTEGER,
      tickets_per_day INTEGER,
      passengers_per_day INTEGER,
      earnings_per_day INTEGER,
      footfalls_per_day INTEGER
    );
    CREATE TABLE units (
      sl_no INTEGER,
      unit_no TEXT PRIMARY KEY,
      type_of_unit TEXT,
      station_code TEXT,
      station_category TEXT,
      old_category TEXT,
      pf_no TEXT,
      pegged_location TEXT,
      reservation_category TEXT,
      allotment_type TEXT,
      licensee_name TEXT,
      license_fee TEXT,
      contract_from TEXT,
      contract_to TEXT,
      unit_status TEXT
    );
    CREATE TABLE works (
      project_id TEXT PRIMARY KEY,
      year_of_sanction TEXT,
      year_ub_works TEXT,
      status TEXT,
      date_of_sanction TEXT,
      short_name_of_work TEXT,
      block_section_station TEXT,
      allocation TEXT,
      engg_remarks TEXT,
      if_ub TEXT,
      parent_work TEXT,
      section TEXT,
      anticipated_expenditure INTEGER,
      remarks TEXT
    );
    CREATE TABLE work_links (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_id TEXT,
      scope_type TEXT,
      scope_value TEXT,
      station_code TEXT,
      match_status TEXT
    );
  `);
};

const insertRows = (tableName, rows) => {
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  const placeholders = cols.map(() => "?").join(",");
  const stmt = db.prepare(`INSERT INTO ${tableName} (${cols.join(",")}) VALUES (${placeholders})`);
  db.run("BEGIN");
  for (const row of rows) {
    stmt.run(cols.map((col) => row[col] ?? null));
  }
  db.run("COMMIT");
  stmt.free();
};

const parseStationCsv = (csv) => {
  const rows = parseCSVRows(csv);
  const headers = rows.shift().map((h) => stationHeaderMap[normalizeHeader(h)] ?? null);
  return rows
    .map((row) => {
      const item = {};
      headers.forEach((key, index) => {
        if (!key) return;
        item[key] = numericFields.has(key) ? toNumber(row[index]) : moneyFields.has(key) ? cleanValue(row[index]).replace(/[₹?]/g, "").trim() : cleanValue(row[index]);
      });
      return item;
    })
    .filter((item) => item.stationCode);
};

const parseUnitsCsv = (csv) => {
  const rows = parseCSVRows(csv);
  const headers = rows.shift().map((h) => unitHeaderMap[normalizeHeader(h)] ?? null);
  return rows
    .map((row) => {
      const item = {};
      headers.forEach((key, index) => {
        if (!key) return;
        item[key] = numericFields.has(key) ? toNumber(row[index]) : moneyFields.has(key) ? cleanValue(row[index]).replace(/[₹?]/g, "").trim() : cleanValue(row[index]);
      });
      return item;
    })
    .filter((item) => item.unitNo);
};

const parseWorksCsv = (csv) => {
  const rows = parseCSVRows(csv);
  const headerRowIndex = rows.findIndex((row) => row.includes("PROJECTID"));
  const headers = rows[headerRowIndex].map((h) => worksHeaderMap[normalizeHeader(h)] ?? null);
  return rows.slice(headerRowIndex + 1).map((row) => {
    const item = {};
    headers.forEach((key, index) => {
      if (!key) return;
      item[key] = numericFields.has(key) ? toNumber(row[index]) : cleanValue(row[index]);
    });
    return item;
  }).filter((item) => item.projectId);
};

const expandWorkScopes = (work) => {
  const raw = cleanValue(work.blockSectionStation);
  const stnMatch = raw.match(/Stn:\s*([^]*)/i);
  const scopeText = stnMatch ? stnMatch[1].trim() : raw;
  const items = scopeText
    .replace(/\r?\n/g, ",")
    .split(/,|;|&|\//)
    .map((part) => part.trim())
    .filter(Boolean);
  if (!items.length) return [{ scopeType: "Other", scopeValue: raw, stationCode: null }];
  return items.map((item) => {
    const upper = item.toUpperCase();
    if (upper.includes("ABSS")) return { scopeType: "ABSS", scopeValue: item, stationCode: null };
    if (/\bDIV(ISION)?\b/i.test(item)) return { scopeType: "Division", scopeValue: item, stationCode: null };
    const codes = item.replace(/^Stn:\s*/i, "").split(/\s*&\s*|\s+AND\s+|,\s*/i).map((s) => s.trim()).filter(Boolean);
    if (!codes.length) return { scopeType: "Other", scopeValue: item, stationCode: null };
    return codes.map((code) => ({ scopeType: "Station", scopeValue: code, stationCode: code }))[0];
  }).flat();
};

const buildDb = () => {
  db.run("DELETE FROM stations; DELETE FROM units; DELETE FROM works; DELETE FROM work_links;");
  insertRows("stations", sql.stations);
  insertRows("units", sql.units);
  insertRows("works", sql.works);
  insertRows("work_links", sql.workLinks);
};

const queryAll = (sqlText, params = []) => {
  const stmt = db.prepare(sqlText);
  stmt.bind(params);
  const out = [];
  while (stmt.step()) out.push(stmt.getAsObject());
  stmt.free();
  return out;
};

const getCounts = () => ({
  stations: queryAll("SELECT COUNT(*) AS c FROM stations")[0].c,
  categories: queryAll("SELECT COUNT(DISTINCT categorisation) AS c FROM stations")[0].c,
  units: queryAll("SELECT COUNT(*) AS c FROM units")[0].c,
  footfall: queryAll("SELECT COALESCE(SUM(passenger_footfall),0) AS c FROM stations")[0].c,
  works: queryAll("SELECT COUNT(*) AS c FROM works")[0].c,
});

const optionList = (select, values, selected = "All") => {
  select.innerHTML = values.map((value) => `<option value="${value}">${value}</option>`).join("");
  select.value = values.includes(selected) ? selected : "All";
};

const setModeUi = () => {
  const labels = {
    stations: ["Category", "Division", "Section", "Platform", "Station dashboard", "Find stations", "Search stations, inspect units, and switch between operating views from one place."],
    units: ["Station category", "Unit type", "Station", "Unit status", "Catering units", "Analyze catering units", "Search units and see which station each license links to."],
    works: ["Scope", "Work status", "Station", "Scope type", "Sanctioned works", "Station works", "Search works, including multi-station `Stn:` entries, ABSS, and Division scopes."],
  };
  const [cLabel, dLabel, sLabel, pLabel, eyebrow, title, hint] = labels[state.view];
  els.categoryLabel.textContent = cLabel;
  els.divisionLabel.textContent = dLabel;
  els.sectionLabel.textContent = sLabel;
  els.platformLabel.textContent = pLabel;
  els.viewEyebrow.textContent = eyebrow;
  els.viewTitle.textContent = title;
  els.viewHint.textContent = hint;
  els.resultsTitle.textContent = title;
  const placeholders = {
    stations: "Search code, name, section, category...",
    units: "Search unit no, station, licensee, status...",
    works: "Search project id, station code, work name, ABSS, division...",
  };
  els.searchInput.placeholder = placeholders[state.view];
};

const rebuildFilters = () => {
  if (!db) {
    optionList(els.categoryFilter, ["All"], "All");
    optionList(els.divisionFilter, ["All"], "All");
    optionList(els.sectionFilter, ["All"], "All");
    optionList(els.platformFilter, ["All"], "All");
    els.totalStations.textContent = "0";
    els.totalCategories.textContent = "0";
    els.totalUnits.textContent = "0";
    els.totalFootfall.textContent = "0";
    els.resultCount.textContent = "0 found";
    return;
  }
  const count = getCounts();
  if (state.view === "stations") {
    optionList(els.categoryFilter, ["All", ...new Set(sql.stations.map((r) => r.categorisation).filter(Boolean).sort())], state.category);
    optionList(els.divisionFilter, ["All", ...new Set(sql.stations.map((r) => r.division).filter(Boolean).sort())], state.division);
    optionList(els.sectionFilter, ["All", ...new Set(sql.stations.map((r) => r.section).filter(Boolean).sort())], state.section);
    optionList(els.platformFilter, ["All", ...new Set(sql.stations.map((r) => r.platformType).filter(Boolean).sort())], state.platform);
  } else if (state.view === "units") {
    optionList(els.categoryFilter, ["All", ...new Set(sql.units.map((r) => r.stationCategory).filter(Boolean).sort())], state.unitCategory);
    optionList(els.divisionFilter, ["All", ...new Set(sql.units.map((r) => r.typeOfUnit).filter(Boolean).sort())], state.unitType);
    optionList(els.sectionFilter, ["All", ...new Set(sql.units.map((r) => r.stationCode).filter(Boolean).sort())], state.section);
    optionList(els.platformFilter, ["All", ...new Set(sql.units.map((r) => r.unitStatus).filter(Boolean).sort())], state.unitStatus);
  } else {
    optionList(els.categoryFilter, ["All", "Station", "Division", "ABSS", "Other"], state.workScope);
    optionList(els.divisionFilter, ["All", ...new Set(sql.works.map((r) => r.status).filter(Boolean).sort())], state.workStatus);
    optionList(els.sectionFilter, ["All", ...new Set(sql.workLinks.map((r) => r.station_code).filter(Boolean).sort())], state.section);
    optionList(els.platformFilter, ["All"], "All");
  }
  els.totalStations.textContent = count.stations;
  els.totalCategories.textContent = count.categories;
  els.totalUnits.textContent = count.units;
  els.totalFootfall.textContent = formatNumber(count.footfall);
  els.resultCount.textContent = `${getResults().length} found`;
};

const buildFilters = () => {
  setModeUi();
  rebuildFilters();
};

const whereContains = (fields) => fields.map((field) => `${field} LIKE ?`).join(" OR ");

const getResults = () => {
  if (!db) return [];
  const q = `%${state.search}%`;
  if (state.view === "stations") {
    const filters = [
      "stations",
      "COALESCE(station_code,'') LIKE ? OR COALESCE(station_name,'') LIKE ? OR COALESCE(section,'') LIKE ? OR COALESCE(categorisation,'') LIKE ? OR COALESCE(division,'') LIKE ?",
      [q, q, q, q, q],
    ];
    const rows = queryAll(
      `SELECT s.*, COUNT(wl.id) AS linked_works
       FROM stations s
       LEFT JOIN work_links wl ON wl.station_code = s.station_code
       WHERE (${filters[1]})
         AND (? = 'All' OR s.categorisation = ?)
         AND (? = 'All' OR s.division = ?)
         AND (? = 'All' OR s.section = ?)
         AND (? = 'All' OR s.platform_type = ?)
       GROUP BY s.station_code
       ORDER BY ${state.sort === "code" ? "s.station_code" : state.sort === "footfall" ? "s.passenger_footfall DESC" : state.sort === "platforms" ? "s.number_of_platforms DESC" : "s.station_name"}`,
      [q, q, q, q, q, state.category, state.category, state.division, state.division, state.section, state.section, state.platform, state.platform],
    );
    return rows;
  }
  if (state.view === "units") {
    return queryAll(
      `SELECT u.*, s.station_name, s.categorisation, s.division AS station_division, s.zone
       FROM units u
       LEFT JOIN stations s ON s.station_code = u.station_code
       WHERE (COALESCE(u.unit_no,'') LIKE ? OR COALESCE(u.licensee_name,'') LIKE ? OR COALESCE(u.station_code,'') LIKE ? OR COALESCE(u.unit_status,'') LIKE ?)
         AND (? = 'All' OR u.station_category = ?)
         AND (? = 'All' OR u.type_of_unit = ?)
         AND (? = 'All' OR u.station_code = ?)
         AND (? = 'All' OR u.unit_status = ?)
       ORDER BY u.unit_no`,
      [q, q, q, q, state.unitCategory, state.unitCategory, state.unitType, state.unitType, state.section, state.section, state.unitStatus, state.unitStatus],
    );
  }
  return queryAll(
    `SELECT w.*, wl.scope_type, wl.scope_value, wl.station_code, s.station_name, s.categorisation, s.division
     FROM works w
     LEFT JOIN work_links wl ON wl.project_id = w.project_id
     LEFT JOIN stations s ON s.station_code = wl.station_code
     WHERE (COALESCE(w.project_id,'') LIKE ? OR COALESCE(w.short_name_of_work,'') LIKE ? OR COALESCE(w.block_section_station,'') LIKE ? OR COALESCE(w.status,'') LIKE ? OR COALESCE(wl.scope_value,'') LIKE ? OR COALESCE(wl.scope_type,'') LIKE ?)
       AND (? = 'All' OR wl.scope_type = ?)
       AND (? = 'All' OR w.status = ?)
       AND (? = 'All' OR COALESCE(wl.station_code,'') = ?)
     ORDER BY w.date_of_sanction DESC, w.project_id`,
    [q, q, q, q, q, q, state.workScope, state.workScope, state.workStatus, state.workStatus, state.section, state.section],
  );
};

const detailRow = (label, value, numeric = false) => `<div class="detail-item${label === "Linked station codes" ? " detail-span" : ""}"><span>${label}</span><strong>${numeric ? formatNumber(value) : value || "Not available"}</strong></div>`;

const openStationDetails = (row) => {
  const linked = queryAll("SELECT station_code, COUNT(*) AS c FROM work_links WHERE station_code = ? GROUP BY station_code", [row.station_code])[0]?.c ?? 0;
  els.dialogCode.textContent = row.station_code;
  els.dialogTitle.textContent = row.station_name || "Unnamed station";
  els.dialogDetails.innerHTML = stationFields.map(([label, key]) => detailRow(label, row[key], numericFields.has(key))).join("") + detailRow("Linked works", linked, true);
  els.dialog.showModal();
};

const openUnitDetails = (row) => {
  els.dialogCode.textContent = row.unit_no;
  els.dialogTitle.textContent = `${row.type_of_unit || "Unit"} at ${row.station_code || "Unknown station"}`;
  els.dialogDetails.innerHTML = [
    ["Unit no.", row.unit_no],
    ["Type", row.type_of_unit],
    ["Station", `${row.station_code || "Not available"} ${row.station_name ? `- ${row.station_name}` : ""}`],
    ["Station category", row.station_category],
    ["Old category", row.old_category],
    ["PF no", row.pf_no],
    ["Pegged location", row.pegged_location],
    ["Reservation category", row.reservation_category],
    ["Allotment type", row.allotment_type],
    ["Licensee", row.licensee_name],
    ["License fee", row.license_fee],
    ["Contract from", row.contract_from],
    ["Contract to", row.contract_to],
    ["Unit status", row.unit_status],
  ].map(([label, value]) => detailRow(label, value)).join("");
  els.dialog.showModal();
};

const openWorkDetails = (row) => {
  const linked = queryAll("SELECT station_code, scope_type, scope_value, match_status FROM work_links WHERE project_id = ?", [row.project_id]);
  els.dialogCode.textContent = row.project_id;
  els.dialogTitle.textContent = row.short_name_of_work || "Sanctioned work";
  els.dialogDetails.innerHTML = [
    ["Project ID", row.project_id],
    ["Year of sanction", row.year_of_sanction],
    ["Year UB works", row.year_ub_works],
    ["Status", row.status],
    ["Date of sanction", formatDate(row.date_of_sanction)],
    ["Block Section Station", row.block_section_station],
    ["Allocation", row.allocation],
    ["Parent work", row.parent_work],
    ["Section", row.section],
    ["Anticipated expenditure", row.anticipated_expenditure, true],
    ["Remarks", row.remarks],
  ].map(([label, value, numeric]) => detailRow(label, value, numeric)).join("") +
    `<div class="detail-item detail-span"><span>Linked scopes</span><strong>${linked.map((item) => `${item.scope_type}: ${item.scope_value}${item.station_code ? ` (${item.station_code})` : ""}`).join("<br>") || "Not available"}</strong></div>`;
  els.dialog.showModal();
};

const stationCard = (row) => `
  <article class="station-card">
    <button type="button" class="card-button" data-station="${row.station_code}">
      <div class="card-topline"><span class="code-badge">${row.station_code || "NA"}</span><span class="category-badge">${row.categorisation || "Uncategorised"}</span></div>
      <h3>${row.station_name || "Unnamed station"}</h3>
      <div class="station-meta"><span>${row.section || "No section"}</span><span>${row.division || "No division"} / ${row.zone || "No zone"}</span></div>
      <div class="metric-row">
        <div><span>Works</span><strong>${row.linked_works || 0}</strong></div>
        <div><span>Footfall</span><strong>${formatNumber(row.passenger_footfall)}</strong></div>
        <div><span>Type</span><strong>${row.platform_type || "NA"}</strong></div>
      </div>
    </button>
  </article>`;

const unitCard = (row) => `
  <article class="station-card">
    <button type="button" class="card-button" data-unit="${row.unit_no}">
      <div class="card-topline"><span class="code-badge">${row.unit_no}</span><span class="category-badge">${row.unit_status || "Status"}</span></div>
      <h3>${row.licensee_name || "Unnamed licensee"}</h3>
      <div class="station-meta"><span>${row.station_code || "No station"}${row.station_name ? ` / ${row.station_name}` : ""}</span><span>${row.station_category || "No category"}</span></div>
      <div class="metric-row">
        <div><span>Fee</span><strong>${row.license_fee || "Not available"}</strong></div>
        <div><span>PF</span><strong>${row.pf_no || "NA"}</strong></div>
        <div><span>Type</span><strong>${row.type_of_unit || "NA"}</strong></div>
      </div>
    </button>
  </article>`;

const workCard = (row) => `
  <article class="station-card">
    <button type="button" class="card-button" data-work="${row.project_id}">
      <div class="card-topline"><span class="code-badge">${row.project_id}</span><span class="category-badge">${row.scope_type || row.status || "Work"}</span></div>
      <h3>${row.short_name_of_work || "Sanctioned work"}</h3>
      <div class="station-meta"><span>${row.scope_value || row.block_section_station || "No scope"}</span><span>${row.station_code ? `${row.station_code}${row.station_name ? ` / ${row.station_name}` : ""}` : "No station code"}</span></div>
      <div class="metric-row">
        <div><span>Status</span><strong>${row.status || "NA"}</strong></div>
        <div><span>Date</span><strong>${formatDate(row.date_of_sanction)}</strong></div>
        <div><span>Link</span><strong>${row.match_status || "NA"}</strong></div>
      </div>
    </button>
  </article>`;

const renderChips = () => {
  const values =
    state.view === "stations"
      ? ["All", ...new Set(sql.stations.map((r) => r.categorisation).filter(Boolean).sort())]
      : state.view === "units"
        ? ["All", ...new Set(sql.units.map((r) => r.stationCategory).filter(Boolean).sort())]
        : ["All", "Station", "Division", "ABSS", "Other"];
  els.categoryChips.innerHTML = values.map((v) => `<button type="button" class="chip ${(state.view === "stations" && state.category === v) || (state.view === "units" && state.unitCategory === v) || (state.view === "works" && state.workScope === v) ? "is-active" : ""}" data-category="${v}">${v}</button>`).join("");
};

const render = () => {
  buildFilters();
  renderChips();
  currentResults = getResults();
  els.resultCount.textContent = `${currentResults.length} found`;
  els.results.innerHTML = currentResults.map((row) => (state.view === "stations" ? stationCard(row) : state.view === "units" ? unitCard(row) : workCard(row))).join("");
  els.emptyState.hidden = currentResults.length > 0;
};

const syncAll = async () => {
  els.syncButton.disabled = true;
  setSyncStatus("Fetching latest sheets...", "neutral");
  try {
    await initDatabase();
    const [stationsCsv, unitsCsv, worksCsv] = await Promise.all([
      fetchCsv(SHEET_ID_STATIONS, "sheet=stations"),
      fetchCsv(SHEET_ID_STATIONS, "sheet=Units"),
      fetchCsv(SHEET_ID_WORKS, `gid=${WORKS_GID}`),
    ]);
    sql.stations = parseStationCsv(stationsCsv);
    sql.units = parseUnitsCsv(unitsCsv);
    sql.works = parseWorksCsv(worksCsv);
    sql.workLinks = [];
    const stationCodes = new Set(sql.stations.map((s) => s.stationCode));
    for (const work of sql.works) {
      for (const scope of expandWorkScopes(work)) {
        if (scope.scopeType === "Station") {
          const codes = scope.scopeValue.split(/\s*&\s*|\s+AND\s+|,\s*/i).map((s) => s.trim()).filter(Boolean);
          for (const code of codes) {
            sql.workLinks.push({
              project_id: work.projectId,
              scope_type: "Station",
              scope_value: code,
              station_code: code,
              match_status: stationCodes.has(code) ? "Matched" : "Missing station",
            });
          }
        } else {
          sql.workLinks.push({
            project_id: work.projectId,
            scope_type: scope.scopeType,
            scope_value: scope.scopeValue,
            station_code: null,
            match_status: scope.scopeType,
          });
        }
      }
    }
    buildDb();
    state.search = "";
    els.searchInput.value = "";
    render();
    setSyncStatus(`Synced ${sql.stations.length} stations, ${sql.units.length} units, and ${sql.works.length} works`, "success");
  } catch (error) {
    setSyncStatus(error.message, "error");
  } finally {
    els.syncButton.disabled = false;
  }
};

const setMode = (view) => {
  state.view = view;
  state.search = "";
  els.searchInput.value = "";
  els.navItems.forEach((button) => button.classList.toggle("is-active", button.dataset.view === view));
  render();
};

els.syncButton.addEventListener("click", syncAll);
els.navItems.forEach((button) => button.addEventListener("click", () => setMode(button.dataset.view)));
els.searchInput.addEventListener("input", (event) => {
  state.search = event.target.value.trim();
  render();
});
els.categoryFilter.addEventListener("change", (event) => {
  if (state.view === "stations") state.category = event.target.value;
  else if (state.view === "units") state.unitCategory = event.target.value;
  else state.workScope = event.target.value;
  render();
});
els.divisionFilter.addEventListener("change", (event) => {
  if (state.view === "stations") state.division = event.target.value;
  else if (state.view === "units") state.unitType = event.target.value;
  else state.workStatus = event.target.value;
  render();
});
els.sectionFilter.addEventListener("change", (event) => {
  state.section = event.target.value;
  render();
});
els.platformFilter.addEventListener("change", (event) => {
  if (state.view === "stations") state.platform = event.target.value;
  else if (state.view === "units") state.unitStatus = event.target.value;
  render();
});
els.sortSelect.addEventListener("change", (event) => {
  state.sort = event.target.value;
  render();
});
els.categoryChips.addEventListener("click", (event) => {
  const button = event.target.closest("[data-category]");
  if (!button) return;
  if (state.view === "stations") state.category = button.dataset.category;
  else if (state.view === "units") state.unitCategory = button.dataset.category;
  else state.workScope = button.dataset.category;
  render();
});
els.results.addEventListener("click", (event) => {
  const stationButton = event.target.closest("[data-station]");
  const unitButton = event.target.closest("[data-unit]");
  const workButton = event.target.closest("[data-work]");
  if (stationButton) openStationDetails(currentResults.find((row) => row.station_code === stationButton.dataset.station));
  if (unitButton) openUnitDetails(currentResults.find((row) => row.unit_no === unitButton.dataset.unit));
  if (workButton) openWorkDetails(currentResults.find((row) => row.project_id === workButton.dataset.work));
});
els.closeDialog.addEventListener("click", () => els.dialog.close());

render();
setSyncStatus("Ready to fetch sheets", "neutral");
