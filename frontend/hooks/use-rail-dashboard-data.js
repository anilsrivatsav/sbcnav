"use client";

import { useState } from "react";
import { loadRailDashboardData } from "../lib/api";

export function useRailDashboardData() {
  const [stats, setStats] = useState(null);
  const [stations, setStations] = useState([]);
  const [units, setUnits] = useState([]);
  const [earnings, setEarnings] = useState([]);
  const [works, setWorks] = useState([]);
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
  const [loading, setLoading] = useState(false);
  const [activityStatus, setActivityStatus] = useState("Ready");
  const [lastRefreshAt, setLastRefreshAt] = useState(null);

  const loadFromDb = async () => {
    const data = await loadRailDashboardData();
    setStats(data.stats);
    setStations(data.stations);
    setUnits(data.units);
    setEarnings(data.earnings);
    setWorks(data.works);
    setReports(data.reports);
    setPaSummary(data.passengerAmenities.summary);
    setPaInfra(data.passengerAmenities.infra);
    setPaPlatforms(data.passengerAmenities.platforms);
    setPaWheelchairs(data.passengerAmenities.wheelchairs);
    setPaTrolley(data.passengerAmenities.trolley);
    setPaWorks(data.passengerAmenities.works);
    setPaPfExtension(data.passengerAmenities.pfExtension);
    setPaNorms(data.passengerAmenities.norms);
    setPaReports(data.passengerAmenities.reports);
    setLastRefreshAt(new Date().toLocaleString());
    return data.errors || [];
  };

  const loadData = async () => {
    setLoading(true);
    setActivityStatus("Refreshing database data...");
    try {
      const errors = await loadFromDb();
      setActivityStatus(errors.length ? `Data loaded with ${errors.length} warning(s)` : "Data refreshed successfully");
    } catch (error) {
      setActivityStatus(error?.message || "Refresh failed");
    } finally {
      setLoading(false);
    }
  };

  return {
    stats,
    stations,
    units,
    earnings,
    works,
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
