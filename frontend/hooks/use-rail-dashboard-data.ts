"use client";

import { useEffect, useState } from "react";
import { loadRailDashboardData } from "../lib/api";

export function useRailDashboardData() {
  const cacheKey = "sbcnav-postgres-read-model-v1";
  const [stats, setStats] = useState(null);
  const [dataCentre, setDataCentre] = useState(null);
  const [actionCentre, setActionCentre] = useState(null);
  const [stations, setStations] = useState([]);
  const [units, setUnits] = useState([]);
  const [earnings, setEarnings] = useState([]);
  const [works, setWorks] = useState([]);
  const [workMonitoring, setWorkMonitoring] = useState(null);
  const [commercialContracts, setCommercialContracts] = useState([]);
  const [commercialContractReports, setCommercialContractReports] = useState(null);
  const [contractAlerts, setContractAlerts] = useState(null);
  const [registryContracts, setRegistryContracts] = useState([]);
  const [paSummary, setPaSummary] = useState([]);
  const [paInfra, setPaInfra] = useState([]);
  const [paPlatforms, setPaPlatforms] = useState([]);
  const [paWheelchairs, setPaWheelchairs] = useState([]);
  const [paTrolley, setPaTrolley] = useState([]);
  const [paWorks, setPaWorks] = useState([]);
  const [paPfExtension, setPaPfExtension] = useState([]);
  const [paNorms, setPaNorms] = useState([]);
  const [paReports, setPaReports] = useState(null);
  const [reports, setReports] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activityStatus, setActivityStatus] = useState("Loading PostgreSQL data...");
  const [lastRefreshAt, setLastRefreshAt] = useState(null);

  const applyData = (data) => {
    const rows = (value) => Array.isArray(value) ? value : (value?.items || []);
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
    setPaSummary(rows(data.passengerAmenities.summary));
    setPaInfra(rows(data.passengerAmenities.infra));
    setPaPlatforms(rows(data.passengerAmenities.platforms));
    setPaWheelchairs(rows(data.passengerAmenities.wheelchairs));
    setPaTrolley(rows(data.passengerAmenities.trolley));
    setPaWorks(rows(data.passengerAmenities.works));
    setPaPfExtension(rows(data.passengerAmenities.pfExtension));
    setPaNorms(rows(data.passengerAmenities.norms));
    setPaReports(data.passengerAmenities.reports);
    setLastRefreshAt(new Date().toLocaleString());
  };

  const loadFromDb = async () => {
    const data = await loadRailDashboardData();
    applyData(data);
    try {
      window.localStorage.setItem(cacheKey, JSON.stringify(data));
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
    try {
      const cached = JSON.parse(window.localStorage.getItem(cacheKey) || "null");
      if (cached?.stats && cached?.passengerAmenities) {
        applyData(cached);
        setActivityStatus("Showing last PostgreSQL snapshot; checking latest data...");
      }
    } catch {
      // Ignore an unavailable or invalid local snapshot.
    }
    loadData();
  }, []);

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
