import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/CMI PA/OneDrive - PRAGNA VIDYANIKETAN/Documents/Works - PH-53/Untitled spreadsheet.xlsx";
const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const summary = await workbook.inspect({
  kind: "workbook,sheet,table,region",
  maxChars: 12000,
  tableMaxRows: 20,
  tableMaxCols: 20,
  tableMaxCellChars: 120,
});

await fs.writeFile(
  "C:/Users/CMI PA/OneDrive - PRAGNA VIDYANIKETAN/Documents/Works - PH-53/outputs/station_db/inspect.ndjson",
  summary.ndjson,
  "utf8",
);
console.log(summary.ndjson);
