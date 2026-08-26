function resolveApiUrl() {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined" && ["127.0.0.1", "localhost"].includes(window.location.hostname)) {
    return "http://127.0.0.1:8000";
  }
  return "https://sbcnav.onrender.com";
}

export const API_URL = resolveApiUrl();

export async function fetchJson(url: string, options?: RequestInit) {
  let response;
  try {
    response = await fetch(url, { cache: "no-store", ...(options || {}) });
  } catch (error) {
    throw new Error(`Network error while reaching API: ${error?.message || "request failed"}`);
  }

  let json;
  const text = await response.text();
  try {
    json = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`API returned invalid JSON from ${new URL(url).pathname}`);
  }

  if (!response.ok || json.success === false) {
    const detail = typeof json.detail === "string" ? json.detail : json.detail?.message || json.message;
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return json.data;
}

export async function loadRailDashboardData() {
  // One PostgreSQL-backed read model avoids waiting on twenty separate API
  // requests. The backend caches this response in Redis (or a short-lived
  // process cache when Redis is not configured). It never imports source sheets.
  const data = await fetchJson(dashboardBootstrapUrl());
  return { ...data, errors: [] };
}

export function dashboardBootstrapUrl({ refresh = false } = {}) {
  return `${API_URL}/api/dashboard-bootstrap${refresh ? "?refresh=true" : ""}`;
}

export function contractAlertsUrl(stationCode?: string) {
  const query = stationCode && stationCode !== "All" ? `?station_code=${encodeURIComponent(stationCode)}` : "";
  return `${API_URL}/api/contracts/alerts${query}`;
}

export function stationDetailUrl(stationCode) {
  return `${API_URL}/api/stations/${encodeURIComponent(stationCode)}/detail`;
}

export function amenityFindingsUrl(stationCode) {
  return `${API_URL}/api/mobile/v1/stations/${encodeURIComponent(stationCode)}/amenity-findings`;
}

export function importPassengerAmenitiesUrl() {
  return `${API_URL}/api/passenger-amenities/import`;
}

export function previewPassengerAmenitiesUrl() {
  return `${API_URL}/api/passenger-amenities/preview`;
}

export function importPfExtensionUrl() {
  return `${API_URL}/api/passenger-amenities/import-pf-extension`;
}

export function commercialContractDetailUrl(contractKey) {
  return `${API_URL}/api/commercial-contracts/${encodeURIComponent(contractKey)}`;
}

export function commercialContractStatementUrl(contractKey) {
  return `${API_URL}/api/commercial-contracts/${encodeURIComponent(contractKey)}/statement`;
}

export function importCommercialContractsUrl() {
  return `${API_URL}/api/commercial-contracts/import`;
}

export function contractsUrl({ status = "all", search = "", page = 1, pageSize = 100 } = {}) {
  const params = new URLSearchParams({ status, page: String(page), page_size: String(pageSize) });
  if (search.trim()) params.set("search", search.trim());
  return `${API_URL}/api/contracts?${params.toString()}`;
}

export function contractSummaryUrl() {
  return `${API_URL}/api/contracts/summary`;
}

export function contractRegistryDetailUrl(contractId) {
  return `${API_URL}/api/contracts/${encodeURIComponent(contractId)}`;
}

export function cateringSyncUrl({ dryRun = false } = {}) {
  return `${API_URL}/api/catering/sync?dry_run=${dryRun ? "true" : "false"}`;
}

export function cateringSyncHistoryUrl() {
  return `${API_URL}/api/catering/sync-history`;
}

export function importSanctionedWorksUrl() {
  return `${API_URL}/api/works/import-sanctioned`;
}

export function previewSanctionedWorksUrl() {
  return `${API_URL}/api/works/import-sanctioned/preview`;
}

export function workProgressUrl(projectId) {
  return `${API_URL}/api/works/${encodeURIComponent(projectId)}/progress`;
}

export function workExpenditureUrl(projectId) {
  return `${API_URL}/api/works/${encodeURIComponent(projectId)}/expenditure`;
}

export function aiQueryUrl() {
  return `${API_URL}/api/ai/query`;
}

export function reportPresetsUrl() {
  return `${API_URL}/api/report-presets`;
}

export function reportPresetRunUrl(presetId) {
  return `${API_URL}/api/report-presets/${encodeURIComponent(presetId)}/run`;
}
