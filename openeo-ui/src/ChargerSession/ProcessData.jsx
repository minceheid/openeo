import { useState, useEffect, useRef, useCallback, Fragment } from "react";
import { getCurrencyConfig, formatCurrency } from '../utils/funcs';



export default function processSessionData(raw) {

  // First pass of the raw data to add derived fields and format values for display. 
  // This is done before merging multi-day sessions so that the per-day entries can be 
  // displayed in the table with their own values, and the merged session summary can 
  // be displayed with its own values.
  const sessiondata = raw.map((x) => ({
    ...x,
    kwh: Math.round(x.joules / 360000) / 10 + " kWh",
    kwh_number: Math.round(x.joules / 360000) / 10,
    cost: x.cost ?? 0,
    cost_by_tariff: (() => { try { return JSON.parse(x.cost_by_tariff || "{}"); } catch { return {}; } })(),
    duration: Math.round(
      (x.last_timestamp - Math.max(x.first_timestamp, x.day_timestamp)) / 60
    ),
    timestamp: new Date(x.first_timestamp * 1000)
      .toLocaleString()
      .replace(",", ""),
    day_timestamp_str: new Date(x.day_timestamp * 1000)
      .toLocaleString()
      .replace(",", ""),
    last_timestamp_str: new Date(x.last_timestamp * 1000)
      .toLocaleString()
      .replace(",", ""),
    minutes_charged: Math.round(x.seconds_charged / 60),
  }));

  // Sort the session data by first_timestamp in descending order so that the most recent sessions are displayed first.
  sessiondata.sort((a, b) => b.first_timestamp - a.first_timestamp);

  // Merge multi-day sessions
  const tabledata = [];
  let last_entry = null;
  let sessiontariffs = {};

  const annotated = sessiondata.map((x) => ({ ...x }));

  annotated.forEach((x) => {
    if (last_entry === null || x.first_timestamp !== last_entry) {
      // Create a new table entry for this session
      
      // Clone cost_by_tariff here so the table-row summary doesn't share a
      // reference with this annotated (per-day) entry — otherwise mutating
      // one below silently mutates the other.
      tabledata.push({ ...x, cost_by_tariff: { ...x.cost_by_tariff } });
      last_entry = x.first_timestamp;
      sessiontariffs = { ...x.cost_by_tariff };

    } else {

      const row = tabledata[tabledata.length - 1];
      row.last_timestamp = x.last_timestamp;
      row.last_timestamp_str = x.last_timestamp_str;
      row.joules += x.joules;
      row.kwh = Math.round(row.joules / 360000) / 10 + " kWh";
      row.kwh_number = Math.round(row.joules / 360000) / 10;

      row.duration += x.duration;
      row.minutes_charged += x.minutes_charged;
      row.cost = (row.cost || 0) + (x.cost || 0);

      const currentTariffs = x.cost_by_tariff || {};
      Object.keys(currentTariffs).forEach((rate) => {
        row.cost_by_tariff[rate] = (row.cost_by_tariff[rate] || 0) + currentTariffs[rate];
        });
    }
  });

  tabledata.forEach((x) => {
    x.average_power =
      x.minutes_charged > 0
        ? Math.round((x.kwh_number / (x.minutes_charged / 60)) * 10) / 10 + " kW"
        : "";
  });

  return { tabledata, sessiondata: annotated };
}