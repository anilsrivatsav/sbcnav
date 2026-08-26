function resolveApiUrl() {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined" && ["127.0.0.1", "localhost"].includes(window.location.hostname)) {
    return "http://127.0.0.1:8000";
  }
  return "https://sbcnav.onrender.com";
}

export const API_URL = resolveApiUrl();

const defaultPage = { items: [], pagination: { total: 0, page: 1, page_size: 0 } };

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
    const detail = typeof json.detail === "string" ? json.detail : json.message;
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return json.data;
}

async function fetchOrDefault(url, fallback) {
  try {
    const data = await fetchJson(url);
    return { data: data ?? fallback, error: null };
  } catch (error) {
    return { data: fallback, error: error?.message || "Request failed" };
  }
}

export async function loadRailDashboardData() {
  // One PostgreSQL-backed read model avoids waiting on twenty separate API
  // requests. The backend caches this response in Redis (or a short-lived
  // process cache when Redis is not configured). It never imports source sheets.
  const bootstrap = await fetchOrDefault(dashboardBootstrapUrl(), null);
  if (!bootstrap.error && bootstrap.data?.stats && bootstrap.data?.passengerAmenities) {
    return { ...bootstrap.data, errors: [] };
  }

  // Compatibility fallback while an older backend instance is still deploying.
  const results = await Promise.all([
    fetchOrDefault(`${API_URL}/api/stats`, {}),
    fetchOrDefault(`${API_URL}/api/data-centre`, {}),
    fetchOrDefault(`${API_URL}/api/action-centre?limit=500`, {}),
    fetchOrDefault(`${API_URL}/api/stations?page=1&page_size=5000&sort_by=station_name`, defaultPage),
    fetchOrDefault(`${API_URL}/api/units?page=1&page_size=5000&sort_by=unit_no`, defaultPage),
    fetchOrDefault(`${API_URL}/api/earnings?page=1&page_size=5000&sort_by=date_of_receipt&sort_order=desc`, defaultPage),
    fetchOrDefault(`${API_URL}/api/works?page=1&page_size=5000&sort_by=project_id`, defaultPage),
    fetchOrDefault(`${API_URL}/api/works/monitoring?page=1&page_size=5000`, {}),
    fetchOrDefault(`${API_URL}/api/commercial-contracts?page=1&page_size=5000&sort_by=contract_name`, defaultPage),
    fetchOrDefault(`${API_URL}/api/commercial-contracts/reports`, {}),
    fetchOrDefault(`${API_URL}/api/contracts/alerts`, {}),
    fetchOrDefault(`${API_URL}/api/contracts?status=all&page=1&page_size=5000`, defaultPage),
    fetchOrDefault(`${API_URL}/api/reports`, {}),
    fetchOrDefault(`${API_URL}/api/passenger-amenities?kind=summary&page=1&page_size=5000&sort_by=station_code`, defaultPage),
    fetchOrDefault(`${API_URL}/api/passenger-amenities?kind=infra&page=1&page_size=5000&sort_by=station_code`, defaultPage),
    fetchOrDefault(`${API_URL}/api/passenger-amenities?kind=platforms&page=1&page_size=5000&sort_by=station_code`, defaultPage),
    fetchOrDefault(`${API_URL}/api/passenger-amenities?kind=wheelchairs&page=1&page_size=5000&sort_by=station_code`, defaultPage),
    fetchOrDefault(`${API_URL}/api/passenger-amenities?kind=trolley&page=1&page_size=5000&sort_by=station_code`, defaultPage),
    fetchOrDefault(`${API_URL}/api/passenger-amenities?kind=pa_works&page=1&page_size=5000&sort_by=station_code`, defaultPage),
    fetchOrDefault(`${API_URL}/api/passenger-amenities?kind=pf_extension&page=1&page_size=5000&sort_by=station_code`, defaultPage),
    fetchOrDefault(`${API_URL}/api/passenger-amenities?kind=norms&page=1&page_size=5000&sort_by=category`, defaultPage),
    fetchOrDefault(`${API_URL}/api/passenger-amenities/reports`, {}),
  ]);
  const [
    statsData,
    dataCentreData,
    actionCentreData,
    stationsData,
    unitsData,
    earningsData,
    worksData,
    workMonitoringData,
    commercialContractsData,
    commercialContractReportsData,
    contractAlertsData,
    registryContractsData,
    reportsData,
    paSummaryData,
    paInfraData,
    paPlatformData,
    paWheelData,
    paTrolleyData,
    paWorksData,
    paPfExtensionData,
    paNormData,
    paReportData,
  ] = results.map((result) => result.data);
  const errors = results.map((result) => result.error).filter(Boolean);

  return {
    stats: statsData,
    dataCentre: dataCentreData,
    actionCentre: actionCentreData,
    stations: stationsData.items || [],
    units: unitsData.items || [],
    earnings: earningsData.items || [],
    // The monitoring projection is the complete 152-row sanctioned register;
    // the basic works endpoint may only contain station-linked rows in older deployments.
    works: workMonitoringData.items?.length ? workMonitoringData.items : (worksData.items || []),
    workMonitoring: workMonitoringData,
    commercialContracts: commercialContractsData.items || [],
    commercialContractReports: commercialContractReportsData,
    contractAlerts: contractAlertsData,
    registryContracts: registryContractsData.items || [],
    reports: reportsData,
    passengerAmenities: {
      summary: paSummaryData.items || [],
      infra: paInfraData.items || [],
      platforms: paPlatformData.items || [],
      wheelchairs: paWheelData.items || [],
      trolley: paTrolleyData.items || [],
      works: paWorksData.items || [],
      pfExtension: paPfExtensionData.items || [],
      norms: paNormData.items || [],
      reports: paReportData,
    },
    errors,
  };
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
