"use client";

import { useEffect, useRef, useState } from "react";
import { loadRailDashboardData } from "../lib/api";

const cacheKey = "sbcnav-postgres-dashboard-snapshot-v3";
const oldCacheKeys = ["sbcnav-postgres-read-model-v1", "sbcnav-postgres-dashboard-snapshot-v2"];
const indexedDbName = "sbcnav-postgres-dashboard-cache";
const indexedDbStore = "snapshots";
const indexedDbEntryKey = "latest-v3";

const rows = (value) => Array.isArray(value) ? value : (value?.items || []);
const hasSnapshotData = (snapshot) => Boolean(
  snapshot?.stats
  || rows(snapshot?.stations).length
  || rows(snapshot?.units).length
  || rows(snapshot?.works).length
  || rows(snapshot?.commercialContracts).length
);

const scopeForView = (view) => ({
  stations: "stations",
  masters: "stations",
  contracts: "contracts",
  commercial: "contracts",
  units: "contracts",
  works: "works",
  amenities: "amenities",
  reports: "reports",
  earnings: "reports",
}[view] || "all");

function readSnapshot() {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(window.localStorage.getItem(cacheKey) || "null");
  } catch {
    return null;
  }
}

function snapshotOf(data) {
  const amenities = data.passengerAmenities || {};
  return {
    stats: data.stats,
    dataCentre: data.dataCentre,
    actionCentre: data.actionCentre,
    stations: rows(data.stations),
    units: rows(data.units),
    earnings: rows(data.earnings),
    works: rows(data.works),
    workMonitoring: data.workMonitoring ? {
      ...data.workMonitoring,
      items: rows(data.workMonitoring.items),
    } : null,
    commercialContracts: rows(data.commercialContracts),
    commercialContractReports: data.commercialContractReports,
    contractAlerts: data.contractAlerts,
    registryContracts: rows(data.registryContracts),
    reports: data.reports,
    passengerAmenities: {
      summary: rows(amenities.summary),
      infra: rows(amenities.infra),
      platforms: rows(amenities.platforms),
      wheelchairs: rows(amenities.wheelchairs),
      trolley: rows(amenities.trolley),
      works: rows(amenities.works),
      pfExtension: rows(amenities.pfExtension),
      norms: rows(amenities.norms),
      reports: amenities.reports || null,
    },
  };
}

function coreSnapshotOf(data) {
  return {
    stats: data.stats,
    dataCentre: data.dataCentre,
    actionCentre: data.actionCentre,
    stations: rows(data.stations),
    units: rows(data.units),
    works: rows(data.works),
    workMonitoring: data.workMonitoring,
    commercialContracts: rows(data.commercialContracts),
    commercialContractReports: data.commercialContractReports,
    contractAlerts: data.contractAlerts,
    registryContracts: rows(data.registryContracts),
  };
}

function openIndexedCache() {
  return new Promise<any>((resolve) => {
    if (typeof window === "undefined" || !window.indexedDB) return resolve(null);
    const request = window.indexedDB.open(indexedDbName, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(indexedDbStore);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => resolve(null);
  });
}

async function readIndexedSnapshot() {
  const db = await openIndexedCache();
  if (!db) return null;
  return new Promise<any>((resolve) => {
    const request = db.transaction(indexedDbStore, "readonly").objectStore(indexedDbStore).get(indexedDbEntryKey);
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => resolve(null);
  });
}

async function writeIndexedSnapshot(snapshot) {
  const db = await openIndexedCache();
  if (!db) return;
  await new Promise((resolve) => {
    const request = db.transaction(indexedDbStore, "readwrite").objectStore(indexedDbStore).put(snapshot, indexedDbEntryKey);
    request.onsuccess = resolve;
    request.onerror = resolve;
  });
}

export function useRailDashboardData({ view = "dashboard", enabled = true } = {}) {
  // Keep the server and first client render identical. Browser snapshots are
  // applied immediately after hydration to avoid React text mismatches.
  const [initialSnapshot] = useState(null);
  const [stats, setStats] = useState(() => initialSnapshot?.stats || null);
  const [dataCentre, setDataCentre] = useState(() => initialSnapshot?.dataCentre || null);
  const [actionCentre, setActionCentre] = useState(() => initialSnapshot?.actionCentre || null);
  const [stations, setStations] = useState(() => initialSnapshot?.stations || []);
  const [units, setUnits] = useState(() => initialSnapshot?.units || []);
  const [earnings, setEarnings] = useState(() => initialSnapshot?.earnings || []);
  const [works, setWorks] = useState(() => initialSnapshot?.works || []);
  const [workMonitoring, setWorkMonitoring] = useState(() => initialSnapshot?.workMonitoring || null);
  const [commercialContracts, setCommercialContracts] = useState(() => initialSnapshot?.commercialContracts || []);
  const [commercialContractReports, setCommercialContractReports] = useState(() => initialSnapshot?.commercialContractReports || null);
  const [contractAlerts, setContractAlerts] = useState(() => initialSnapshot?.contractAlerts || null);
  const [registryContracts, setRegistryContracts] = useState(() => initialSnapshot?.registryContracts || []);
  const [paSummary, setPaSummary] = useState(() => initialSnapshot?.passengerAmenities?.summary || []);
  const [paInfra, setPaInfra] = useState(() => initialSnapshot?.passengerAmenities?.infra || []);
  const [paPlatforms, setPaPlatforms] = useState(() => initialSnapshot?.passengerAmenities?.platforms || []);
  const [paWheelchairs, setPaWheelchairs] = useState(() => initialSnapshot?.passengerAmenities?.wheelchairs || []);
  const [paTrolley, setPaTrolley] = useState(() => initialSnapshot?.passengerAmenities?.trolley || []);
  const [paWorks, setPaWorks] = useState(() => initialSnapshot?.passengerAmenities?.works || []);
  const [paPfExtension, setPaPfExtension] = useState(() => initialSnapshot?.passengerAmenities?.pfExtension || []);
  const [paNorms, setPaNorms] = useState(() => initialSnapshot?.passengerAmenities?.norms || []);
  const [paReports, setPaReports] = useState(() => initialSnapshot?.passengerAmenities?.reports || null);
  const [reports, setReports] = useState(() => initialSnapshot?.reports || null);
  const [loading, setLoading] = useState(true);
  const [activityStatus, setActivityStatus] = useState("Loading PostgreSQL data...");
  const [lastRefreshAt, setLastRefreshAt] = useState(null);
  const [cacheReady, setCacheReady] = useState(false);
  const dataRef = useRef<any>({});
  const loadedScopesRef = useRef<Set<string>>(new Set());
  const activeScope = scopeForView(view);

  const rememberSnapshotScopes = (snapshot) => {
    if (rows(snapshot?.stations).length) loadedScopesRef.current.add("stations");
    if (rows(snapshot?.units).length || rows(snapshot?.commercialContracts).length || rows(snapshot?.registryContracts).length) loadedScopesRef.current.add("contracts");
    if (rows(snapshot?.works).length || snapshot?.workMonitoring) loadedScopesRef.current.add("works");
    if (snapshot?.passengerAmenities) loadedScopesRef.current.add("amenities");
    if (rows(snapshot?.earnings).length || snapshot?.reports) loadedScopesRef.current.add("reports");
    if (snapshot?.stats && snapshot?.dataCentre && snapshot?.actionCentre && snapshot?.reports && snapshot?.passengerAmenities) {
      loadedScopesRef.current.add("all");
    }
  };

  const applyData = (data) => {
    const merged = {
      ...dataRef.current,
      ...data,
      passengerAmenities: data.passengerAmenities
        ? { ...(dataRef.current.passengerAmenities || {}), ...data.passengerAmenities }
        : dataRef.current.passengerAmenities,
    };
    dataRef.current = merged;
    if (data.stats !== undefined) setStats(data.stats);
    if (data.dataCentre !== undefined) setDataCentre(data.dataCentre);
    if (data.actionCentre !== undefined) setActionCentre(data.actionCentre);
    if (data.stations !== undefined) setStations(rows(data.stations));
    if (data.units !== undefined) setUnits(rows(data.units));
    if (data.earnings !== undefined) setEarnings(rows(data.earnings));
    if (data.works !== undefined) setWorks(rows(data.works));
    if (data.workMonitoring !== undefined) setWorkMonitoring(data.workMonitoring);
    if (data.commercialContracts !== undefined) setCommercialContracts(rows(data.commercialContracts));
    if (data.commercialContractReports !== undefined) setCommercialContractReports(data.commercialContractReports);
    if (data.contractAlerts !== undefined) setContractAlerts(data.contractAlerts);
    if (data.registryContracts !== undefined) setRegistryContracts(rows(data.registryContracts));
    if (data.reports !== undefined) setReports(data.reports);
    if (data.passengerAmenities !== undefined) {
      const amenities = data.passengerAmenities || {};
      if (amenities.summary !== undefined) setPaSummary(rows(amenities.summary));
      if (amenities.infra !== undefined) setPaInfra(rows(amenities.infra));
      if (amenities.platforms !== undefined) setPaPlatforms(rows(amenities.platforms));
      if (amenities.wheelchairs !== undefined) setPaWheelchairs(rows(amenities.wheelchairs));
      if (amenities.trolley !== undefined) setPaTrolley(rows(amenities.trolley));
      if (amenities.works !== undefined) setPaWorks(rows(amenities.works));
      if (amenities.pfExtension !== undefined) setPaPfExtension(rows(amenities.pfExtension));
      if (amenities.norms !== undefined) setPaNorms(rows(amenities.norms));
      if (amenities.reports !== undefined) setPaReports(amenities.reports);
    }
    setLastRefreshAt(new Date().toLocaleString());
    return merged;
  };

  const loadFromDb = async ({ refresh = false, scope = activeScope } = {}) => {
    let data;
    let lastError;
    // Render can take a few seconds to wake from idle. Retry the single
    // PostgreSQL bootstrap request so the UI does not remain on an empty
    // snapshot after a normal cold start.
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        data = await loadRailDashboardData({ refresh, scope });
        break;
      } catch (error) {
        lastError = error;
        if (attempt < 2) await new Promise((resolve) => setTimeout(resolve, 1200 * (attempt + 1)));
      }
    }
    if (!data) throw lastError || new Error("Unable to load PostgreSQL data");
    const merged = applyData(data);
    loadedScopesRef.current.add(scope);
    try {
      window.localStorage.setItem(cacheKey, JSON.stringify(coreSnapshotOf(merged)));
    } catch {
      // A browser storage limit must not prevent the live PostgreSQL refresh.
    }
    await writeIndexedSnapshot(snapshotOf(merged));
    return data.errors || [];
  };

  const loadData = async ({ refresh = true, scope = activeScope, background = false } = {}) => {
    if (!background) {
      setLoading(true);
      setActivityStatus("Refreshing database data...");
    }
    try {
      const errors = await loadFromDb({ refresh, scope });
      setActivityStatus(errors.length ? `Data loaded with ${errors.length} warning(s)` : "Data refreshed successfully");
      return errors;
    } catch (error) {
      setActivityStatus(error?.message || "Refresh failed");
      return [error?.message || "Refresh failed"];
    } finally {
      if (!background) setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    try { oldCacheKeys.forEach((key) => window.localStorage.removeItem(key)); } catch { /* Ignore storage cleanup failures. */ }
    (async () => {
      const localSnapshot = readSnapshot();
      if (active && hasSnapshotData(localSnapshot)) {
        applyData(localSnapshot);
        rememberSnapshotScopes(localSnapshot);
        setLoading(false);
        setActivityStatus("Showing last PostgreSQL snapshot; checking latest data...");
      }
      const cached = await readIndexedSnapshot();
      if (active && hasSnapshotData(cached)) {
        applyData(cached);
        rememberSnapshotScopes(cached);
        setLoading(false);
        setActivityStatus("Showing last PostgreSQL snapshot; checking latest data...");
      }
      if (active) setCacheReady(true);
    })();
    return () => { active = false; };
  }, [initialSnapshot]);

  useEffect(() => {
    if (!enabled || !cacheReady) return;
    loadData({
      refresh: false,
      scope: activeScope,
      background: loadedScopesRef.current.has("all") || loadedScopesRef.current.has(activeScope),
    });
  }, [activeScope, cacheReady, enabled]);

  return {
    stats,
    dataCentre,
    actionCentre,
    stations,
    units,
    earnings,
    works,
    workMonitoring,
    commercialContracts,
    commercialContractReports,
    contractAlerts,
    registryContracts,
    paSummary,
    paInfra,
    paPlatforms,
    paWheelchairs,
    paTrolley,
    paWorks,
    paPfExtension,
    paNorms,
    paReports,
    reports,
    loading,
    setLoading,
    activityStatus,
    setActivityStatus,
    lastRefreshAt,
    loadFromDb,
    loadData,
  };
}
