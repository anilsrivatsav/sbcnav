import { promises as fs } from "fs";
import path from "path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const dataPath = path.join(process.cwd(), "data", "abss-station-output.json");

const hasText = (value) => String(value || "").trim().length > 0;
const hasDeficiency = (row) => String(row.Remarks || "").toLowerCase().includes("deficiency:");
const hasPoorQuality = (row) => String(row.Remarks || "").toLowerCase().includes("poor quality:");

function summarize(rows, existingStations = []) {
  const map = new Map();
  for (const station of existingStations) {
    map.set(station.Station, {
      Station: station.Station,
      Station_Name: station.Station_Name,
      row_count: 0,
      civil_rows: 0,
      electrical_rows: 0,
      st_rows: 0,
      deficiency_rows: 0,
      poor_quality_rows: 0,
    });
  }
  for (const row of rows) {
    const station = row.Station || "";
    if (!station) continue;
    const item = map.get(station) || {
      Station: station,
      Station_Name: row.Station_Name || station,
      row_count: 0,
      civil_rows: 0,
      electrical_rows: 0,
      st_rows: 0,
      deficiency_rows: 0,
      poor_quality_rows: 0,
    };
    item.row_count += 1;
    if (row.Department === "Civil") item.civil_rows += 1;
    if (row.Department === "Electrical") item.electrical_rows += 1;
    if (row.Department === "S&T") item.st_rows += 1;
    if (hasDeficiency(row)) item.deficiency_rows += 1;
    if (hasPoorQuality(row)) item.poor_quality_rows += 1;
    map.set(station, item);
  }
  return Array.from(map.values()).filter((item) => hasText(item.Station)).sort((a, b) => a.Station.localeCompare(b.Station));
}

async function readData() {
  const raw = await fs.readFile(dataPath, "utf8");
  return JSON.parse(raw);
}

export async function GET() {
  const data = await readData();
  return NextResponse.json(data);
}

export async function PUT(request) {
  const current = await readData();
  const body = await request.json();
  if (!Array.isArray(body.rows)) {
    return NextResponse.json({ error: "Rows are required" }, { status: 400 });
  }

  const rows = body.rows.map((row, index) => ({
    id: index + 1,
    Station: String(row.Station || "").trim(),
    Station_Name: String(row.Station_Name || row.Station || "").trim(),
    Department: String(row.Department || "Civil").trim(),
    Scope: String(row.Scope || "").trim(),
    Existing_Facility: String(row.Existing_Facility || "").trim(),
    Facility_Under_ABSS: String(row.Facility_Under_ABSS || "").trim(),
    Remarks: String(row.Remarks || "").trim(),
    TDC: String(row.TDC || "").trim(),
  }));

  const data = {
    metadata: {
      ...(current.metadata || {}),
      source: "frontend/data/abss-station-output.json",
      exported_at: new Date().toISOString(),
      row_count: rows.length,
      station_count: summarize(rows, current.stations || []).length,
    },
    stations: summarize(rows, current.stations || []),
    rows,
  };

  await fs.writeFile(dataPath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
  return NextResponse.json(data);
}
