"use client";

import { useEffect, useState } from "react";
import { loadRailDashboardData } from "../lib/api";

const cacheKey = "sbcnav-postgres-dashboard-snapshot-v2";
const oldCacheKey = "sbcnav-postgres-read-model-v1";

const rows = (value) => Array.isArray(value) ? value : (value?.items || []);

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

export function useRailDashboardData() {
  const [initialSnapshot] = useState(readSnapshot);
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

  const applyData = (data) => {
    setStats(data.stats);
    setDataCentre(data.dataCentre);
    setActionCentre(data.actionCentre);
    setStations(rows(data.stations));
    setUnits(rows(data.units));
    setEarnings(rows(data.earnings));
    setWorks(rows(data.works));
    setWorkMonitoring(data.workMonitoring);
    setCommercialContracts(rows(data.commercialContracts));
    setCommercialContractReports(data.commercialContractReports);
    setContractAlerts(data.contractAlerts);
    setRegistryContracts(rows(data.registryContracts));
    setReports(data.reports);
    const amenities = data.passengerAmenities || {};
    setPaSummary(rows(amenities.summary));
    setPaInfra(rows(amenities.infra));
    setPaPlatforms(rows(amenities.platforms));
    setPaWheelchairs(rows(amenities.wheelchairs));
    setPaTrolley(rows(amenities.trolley));
    setPaWorks(rows(amenities.works));
    setPaPfExtension(rows(amenities.pfExtension));
    setPaNorms(rows(amenities.norms));
    setPaReports(amenities.reports);
    setLastRefreshAt(new Date().toLocaleString());
  };

  const loadFromDb = async () => {
    const data = await loadRailDashboardData();
    applyData(data);
    try {
      window.localStorage.setItem(cacheKey, JSON.stringify(snapshotOf(data)));
    } catch {
      // A browser storage limit must not prevent the live PostgreSQL refresh.
    }
    return data.errors || [];
  };

  const loadData = async () => {
    setLoading(true);
    setActivityStatus("Refreshing database data...");
    try {
      const errors = await loadFromDb();
      setActivityStatus(errors.length ? `Data loaded with ${errors.length} warning(s)` : "Data refreshed successfully");
      return errors;
    } catch (error) {
      setActivityStatus(error?.message || "Refresh failed");
      return [error?.message || "Refresh failed"];
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    try { window.localStorage.removeItem(oldCacheKey); } catch { /* Ignore storage cleanup failures. */ }
    if (initialSnapshot?.stats) setActivityStatus("Showing last PostgreSQL snapshot; checking latest data...");
    loadData();
  }, [initialSnapshot]);

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
