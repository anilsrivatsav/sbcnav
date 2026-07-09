const url = new URL("https://docs.google.com/spreadsheets/d/1UdRgQQPEkak1fUTuVH7jIn5R4sE3szAhM4VZJOdFIOU/gviz/tq");
url.searchParams.set("sheet", "stations");
url.searchParams.set("tqx", "out:json;responseHandler:stationSheetVerify");

const response = await fetch(url);
const text = await response.text();
const json = text
  .replace(/^\/\*O_o\*\/\s*/, "")
  .replace(/^stationSheetVerify\(/, "")
  .replace(/\);?$/, "");
const payload = JSON.parse(json);
const headers = payload.table.cols.map((col) => col.label ?? col.id ?? "");
const rows = payload.table.rows.filter((row) => row.c.some((cell) => cell?.v || cell?.f));

console.log(JSON.stringify({ status: payload.status, rows: rows.length, headers: headers.slice(0, 22) }, null, 2));
