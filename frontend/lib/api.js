function resolveApiUrl() {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined" && ["127.0.0.1", "localhost"].includes(window.location.hostname)) {
    return "http://127.0.0.1:8000";
  }
  return "https://sbcnav.onrender.com";
}

export const API_URL = resolveApiUrl();

const defaultPage = { items: [], pagination: { total: 0, page: 1, page_size: 0 } };

export async function fetchJson(url, options) {
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
  const results = await Promise.all([
    fetchOrDefault(`${API_URL}/api/stats`, {}),
    fetchOrDefault(`${API_URL}/api/stations?page=1&page_size=5000&sort_by=station_name`, defaultPage),
    fetchOrDefault(`${API_URL}/api/units?page=1&page_size=5000&sort_by=unit_no`, defaultPage),
    fetchOrDefault(`${API_URL}/api/earnings?page=1&page_size=5000&sort_by=date_of_receipt&sort_order=desc`, defaultPage),
    fetchOrDefault(`${API_URL}/api/works?page=1&page_size=5000&sort_by=project_id`, defaultPage),
    fetchOrDefault(`${API_URL}/api/commercial-contracts?page=1&page_size=5000&sort_by=contract_name`, defaultPage),
    fetchOrDefault(`${API_URL}/api/commercial-contracts/reports`, {}),
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
    stationsData,
    unitsData,
    earningsData,
    worksData,
    commercialContractsData,
    commercialContractReportsData,
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
    stations: stationsData.items || [],
    units: unitsData.items || [],
    earnings: earningsData.items || [],
    works: worksData.items || [],
    commercialContracts: commercialContractsData.items || [],
    commercialContractReports: commercialContractReportsData,
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

export function stationDetailUrl(stationCode) {
  return `${API_URL}/api/stations/${encodeURIComponent(stationCode)}/detail`;
}

export function importPassengerAmenitiesUrl() {
  return `${API_URL}/api/passenger-amenities/import`;
}

export function importPfExtensionUrl() {
  return `${API_URL}/api/passenger-amenities/import-pf-extension`;
}

export function commercialContractDetailUrl(contractKey) {
  return `${API_URL}/api/commercial-contracts/${encodeURIComponent(contractKey)}`;
}

export function importCommercialContractsUrl() {
  return `${API_URL}/api/commercial-contracts/import`;
}

export function importSanctionedWorksUrl() {
  return `${API_URL}/api/works/import-sanctioned`;
}

export function aiQueryUrl() {
  return `${API_URL}/api/ai/query`;
}
