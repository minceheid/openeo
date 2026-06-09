import { useState, useEffect, useRef, useCallback } from "react";
import { buildUrl,getCurrencyConfig } from './utils/funcs';
import { globalCss, styles } from './utils/styles';

// ── Currency detection ─────────────────────────────────────────────────────

const CURRENCY = getCurrencyConfig();

function formatCurrency(amount) {
  return new Intl.NumberFormat(CURRENCY.locale, {
    style: "currency",
    currency: CURRENCY.currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount ?? 0);
}

// ── Helpers ────────────────────────────────────────────────────────────────

function getDate(d) {
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
}

function getWeekCommencing(d) {
  const copy = new Date(d);
  const diff = copy.getDate() - copy.getDay() + (copy.getDay() === 0 ? -6 : 1);
  copy.setDate(diff);
  return getDate(copy);
}

function getMonth(d) {
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

function aggregate(data, keyFunc, valueKey = "kwh_number") {
  const totals = {};
  data.forEach((session) => {
    const date = new Date(session.first_timestamp * 1000);
    const key = keyFunc(date);
    totals[key] = (totals[key] || 0) + session[valueKey];
  });
  return totals;
}

function lastN(obj, n, mode) {
  const filled = { ...obj };
  let d = new Date();

  if (mode === "daily") {
    for (let i = 0; i < n; i++) {
      const key = getDate(d);
      if (!(key in filled)) filled[key] = 0;
      d.setDate(d.getDate() - 1);
    }
  } else if (mode === "weekly") {
    const diff = d.getDate() - d.getDay() + (d.getDay() === 0 ? -6 : 1);
    d = new Date(d.setDate(diff));
    d.setHours(0, 0, 0, 0);
    for (let i = 0; i < n; i++) {
      const key = getWeekCommencing(d);
      if (!(key in filled)) filled[key] = 0;
      d.setDate(d.getDate() - 7);
    }
  } else if (mode === "monthly") {
    const diff = d.getDate() - d.getDay() + (d.getDay() === 0 ? -6 : 1);
    d = new Date(d.setDate(diff));
    d.setHours(0, 0, 0, 0);
    for (let i = 0; i < n; i++) {
      const key = getMonth(d);
      if (!(key in filled)) filled[key] = 0;
      d.setMonth(d.getMonth() - 1);
    }
  }

  const keys = Object.keys(filled).sort();
  const slice = keys.slice(-n);
  return { labels: slice, values: slice.map((k) => filled[k]) };
}

function processSessionData(raw) {
  const sessiondata = raw.map((x) => ({
    ...x,
    kwh: Math.round(x.joules / 360000) / 10 + " kWh",
    kwh_number: Math.round(x.joules / 360000) / 10,
    cost: x.cost ?? 0,
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
    plugged_in_idle: Math.max(0, Math.round(
      (x.last_timestamp - Math.max(x.first_timestamp, x.day_timestamp) - x.seconds_charged) / 60
    )),
  }));

  sessiondata.sort((a, b) => b.first_timestamp - a.first_timestamp);

  // Merge multi-day sessions
  const tabledata = [];
  let last_entry = null;
  let sessionjoules = 0;
  let sessioncost = 0;

  const annotated = sessiondata.map((x) => ({ ...x }));

  annotated.forEach((x) => {
    if (last_entry === null || x.first_timestamp !== last_entry) {
      tabledata.push({ ...x });
      last_entry = x.first_timestamp;
      sessionjoules = x.joules;
      sessioncost = x.cost;
    } else {
      const row = tabledata[tabledata.length - 1];
      row.last_timestamp = x.last_timestamp;
      row.last_timestamp_str = x.last_timestamp_str;
      row.joules = x.joules;
      row.kwh = x.kwh;
      row.kwh_number = x.kwh_number;
      row.duration += x.duration;
      row.minutes_charged += x.minutes_charged;
      row.plugged_in_idle += x.plugged_in_idle;
      row.cost = (row.cost || 0) + (x.cost || 0);

      const nextJoules = x.joules;
      const nextCost = x.cost;
      x.joules -= sessionjoules;
      x.cost -= sessioncost;
      sessionjoules = nextJoules;
      sessioncost = nextCost;
      x.first_timestamp = x.day_timestamp;
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

function formatMinutes(minutes) {
  const safeMinutes = Number(minutes) || 0;
  const hours = Math.floor(safeMinutes / 60);
  const remainder = safeMinutes % 60;
  if (!hours) return `${remainder} min`;
  if (!remainder) return `${hours} h`;
  return `${hours} h ${remainder} min`;
}

function formatPower(row) {
  if (!row.minutes_charged) return "Not available";
  return row.average_power || "Not available";
}

function formatJoules(value) {
  return `${Math.round(value || 0).toLocaleString()} J`;
}

function downloadCSV(tabledata) {
  const rows = [
    [
      "From",
      "To",
      "Connected Duration (Minutes)",
      "Power Delivered (kWh)",
      "Charging Duration (Minutes)",
      "Average Power (kW)",
      `Cost (${CURRENCY.symbol})`,
    ],
  ];
  tabledata.forEach((x) => {
    const ap =
      x.minutes_charged > 0
        ? Math.round((x.joules / 360000) / (x.minutes_charged / 60)) /10
        : "";
    rows.push([
      x.timestamp,
      x.last_timestamp_str,
      x.duration,
      Math.round(x.joules / 360000) / 10,
      x.minutes_charged,
      ap,
      (x.cost ?? 0).toFixed(2),
    ]);
  });
  const csvContent =
    "data:text/csv;charset=utf-8," + rows.map((e) => e.join(",")).join("\n");
  const link = document.createElement("a");
  link.setAttribute("href", encodeURI(csvContent));
  link.setAttribute("download", "openeo_session_data.csv");
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// ── Toggle Switch ──────────────────────────────────────────────────────────

function MetricToggle({ showCost, onChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{
        fontSize: "0.75rem",
        fontWeight: 600,
        letterSpacing: "0.08em",
        color: !showCost ? "rgba(64,200,255,0.95)" : "#4a6a80",
        transition: "color 0.2s",
        textTransform: "uppercase",
      }}>
        kWh
      </span>

      {/* Track */}
      <div
        onClick={() => onChange(!showCost)}
        style={{
          position: "relative",
          width: 44,
          height: 24,
          borderRadius: 12,
          background: showCost
            ? "rgba(80,240,160,0.25)"
            : "rgba(64,200,255,0.18)",
          border: showCost
            ? "1px solid rgba(80,240,160,0.45)"
            : "1px solid rgba(64,200,255,0.35)",
          cursor: "pointer",
          transition: "background 0.25s, border-color 0.25s",
          flexShrink: 0,
        }}
      >
        {/* Thumb */}
        <div style={{
          position: "absolute",
          top: 3,
          left: showCost ? 23 : 3,
          width: 16,
          height: 16,
          borderRadius: "50%",
          background: showCost
            ? "rgba(80,240,160,0.95)"
            : "rgba(64,200,255,0.95)",
          boxShadow: showCost
            ? "0 0 6px rgba(80,240,160,0.6)"
            : "0 0 6px rgba(64,200,255,0.6)",
          transition: "left 0.22s cubic-bezier(0.4,0,0.2,1), background 0.25s, box-shadow 0.25s",
        }} />
      </div>

      <span style={{
        fontSize: "0.75rem",
        fontWeight: 600,
        letterSpacing: "0.08em",
        color: showCost ? "rgba(80,240,160,0.95)" : "#4a6a80",
        transition: "color 0.2s",
        textTransform: "uppercase",
      }}>
        {CURRENCY.symbol} Cost
      </span>
    </div>
  );
}

// ── Chart component (Plotly via CDN) ───────────────────────────────────────

function ChargingChart({ sessiondata, showCost }) {
  const chartRef = useRef(null);
  const plotlyReady = useRef(false);

  const renderChart = useCallback(() => {
    if (!chartRef.current || !window.Plotly || !sessiondata.length) return;

    const valueKey = showCost ? "cost" : "kwh_number";
    const yLabel = showCost ? CURRENCY.symbol : "kWh";

    const dailyTotals   = aggregate(sessiondata, getDate,           valueKey);
    const weeklyTotals  = aggregate(sessiondata, getWeekCommencing, valueKey);
    const monthlyTotals = aggregate(sessiondata, getMonth,          valueKey);

    const last7Days   = lastN(dailyTotals,   7, "daily");
    const last4Weeks  = lastN(weeklyTotals,  4, "weekly");
    const last4Months = lastN(monthlyTotals, 4, "monthly");

    const w = window.innerWidth;
    const titlefont =
      w >= 768 ? 18 : w < 375 ? 10 : 10 + ((18 - 10) * (w - 375)) / (768 - 375);
    const axisfont =
      w >= 768 ? 11 : w < 375 ? 6 : 6 + ((11 - 6) * (w - 375)) / (768 - 375);

    const BAR_OPACITY = 0.85;
    const colors = showCost
      ? [
          `rgba(255,185,50,${BAR_OPACITY})`,
          `rgba(255,130,60,${BAR_OPACITY})`,
          `rgba(255,210,80,${BAR_OPACITY})`,
        ]
      : [
          `rgba(64,200,255,${BAR_OPACITY})`,
          `rgba(80,240,160,${BAR_OPACITY})`,
          `rgba(200,100,255,${BAR_OPACITY})`,
        ];

    const annotationColors = showCost
      ? ["rgba(255,185,50,0.9)", "rgba(255,130,60,0.9)", "rgba(255,210,80,0.9)"]
      : ["rgba(64,200,255,0.9)",  "rgba(80,240,160,0.9)", "rgba(200,100,255,0.9)"];

    const traces = [
      {
        x: last7Days.labels,
        y: last7Days.values,
        type: "bar",
        marker: { color: colors[0], line: { width: 0 } },
        name: "Daily",
        legendgroup: "1",
      },
      {
        x: last4Weeks.labels,
        y: last4Weeks.values,
        type: "bar",
        marker: { color: colors[1], line: { width: 0 } },
        name: "Weekly",
        legendgroup: "2",
        xaxis: "x2",
        yaxis: "y2",
      },
      {
        x: last4Months.labels,
        y: last4Months.values,
        type: "bar",
        marker: { color: colors[2], line: { width: 0 } },
        name: "Monthly",
        legendgroup: "3",
        xaxis: "x3",
        yaxis: "y3",
      },
    ];

    const axisBase = {
      showgrid: true,
      gridcolor: "rgba(255,255,255,0.07)",
      zeroline: false,
      tickfont: { size: axisfont, color: "#8ba3b8" },
      titlefont: { size: axisfont + 1, color: "#8ba3b8" },
    };

    const layout = {
      margin: { l: 42, r: 12, t: 64 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      showlegend: false,
      grid: { rows: 1, columns: 3, pattern: "independent" },
      xaxis:  { ...axisBase, type: "category", tickangle: -45, title: "" },
      xaxis2: { ...axisBase, type: "category", tickangle: -45, title: "" },
      xaxis3: { ...axisBase, type: "category", tickangle: -45, title: "" },
      yaxis:  { ...axisBase, title: yLabel, minallowed: 0 },
      yaxis2: { ...axisBase, title: yLabel, minallowed: 0 },
      yaxis3: { ...axisBase, title: yLabel, minallowed: 0 },
      annotations: [
        { text: "DAILY",   font: { size: titlefont, color: annotationColors[0] }, showarrow: false, x: 0.115, y: 1.18, xref: "paper", yref: "paper", align: "center" },
        { text: "WEEKLY",  font: { size: titlefont, color: annotationColors[1] }, showarrow: false, x: 0.5,   y: 1.18, xref: "paper", yref: "paper", align: "center" },
        { text: "MONTHLY", font: { size: titlefont, color: annotationColors[2] }, showarrow: false, x: 0.895, y: 1.18, xref: "paper", yref: "paper", align: "center" },
      ],
    };

    window.Plotly.react(chartRef.current, traces, layout, {
      displayModeBar: false,
      responsive: true,
    });
  }, [sessiondata, showCost]);

  // Load Plotly from CDN once
  useEffect(() => {
    if (window.Plotly) {
      plotlyReady.current = true;
      renderChart();
      return;
    }
    const script = document.createElement("script");
    script.src = "https://cdn.plot.ly/plotly-2.35.2.min.js";
    script.onload = () => {
      plotlyReady.current = true;
      renderChart();
    };
    document.head.appendChild(script);
  }, [renderChart]);

  useEffect(() => {
    if (plotlyReady.current) renderChart();
  }, [renderChart]);

  return (
    <div
      ref={chartRef}
      style={{ width: "100%", height: "38vh", minHeight: 200 }}
    />
  );
}

// ── Session list ───────────────────────────────────────────────────────────

const sessionStyles = {
  list: {
    display: "grid",
    gap: 8,
    padding: 12,
  },
  card: {
    width: "100%",
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    gap: "8px 12px",
    alignItems: "center",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 6,
    background: "rgba(255,255,255,0.04)",
    color: "#c8dde8",
    padding: 12,
    textAlign: "left",
    cursor: "pointer",
  },
  cardSelected: {
    borderColor: "rgba(64,200,255,0.65)",
    background: "rgba(64,200,255,0.1)",
  },
  primaryDate: {
    minWidth: 0,
    overflowWrap: "anywhere",
    color: "#dcebf4",
    fontSize: "0.86rem",
    fontWeight: 650,
  },
  delivered: {
    color: "rgba(64,200,255,0.95)",
    fontSize: "0.95rem",
    fontWeight: 700,
    whiteSpace: "nowrap",
  },
  meta: {
    gridColumn: "1 / -1",
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: 8,
  },
  metaItem: {
    display: "grid",
    gap: 2,
    minHeight: 48,
    padding: "8px 10px",
    borderRadius: 4,
    background: "rgba(255,255,255,0.04)",
  },
  label: {
    color: "#8ba3b8",
    fontSize: "0.68rem",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
  },
  value: {
    color: "#c8dde8",
    fontSize: "0.82rem",
    fontWeight: 600,
    overflowWrap: "anywhere",
  },
  detail: {
    margin: "0 12px 8px",
    padding: 12,
    border: "1px solid rgba(80,240,160,0.3)",
    borderRadius: 6,
    background: "rgba(80,240,160,0.06)",
  },
  detailHead: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
    marginBottom: 10,
  },
  detailTitle: {
    margin: "2px 0 0",
    color: "#dcebf4",
    fontSize: "0.98rem",
  },
  closeButton: {
    border: "1px solid rgba(255,255,255,0.14)",
    borderRadius: 4,
    background: "rgba(255,255,255,0.05)",
    color: "#c8dde8",
    cursor: "pointer",
    padding: "7px 10px",
  },
  detailGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 8,
  },
  detailItem: {
    display: "grid",
    gap: 3,
    minHeight: 58,
    alignContent: "center",
    padding: "9px 10px",
    borderRadius: 4,
    background: "rgba(255,255,255,0.045)",
  },
};

function DetailItem({ label, value, tone }) {
  return (
    <div style={sessionStyles.detailItem}>
      <span style={sessionStyles.label}>{label}</span>
      <strong style={{ ...sessionStyles.value, color: tone || sessionStyles.value.color }}>{value}</strong>
    </div>
  );
}

function SessionDetail({ row, onClose }) {
  return (
    <div style={sessionStyles.detail}>
      <div style={sessionStyles.detailHead}>
        <div>
          <span style={sessionStyles.label}>Session detail</span>
          <h3 style={sessionStyles.detailTitle}>{row.timestamp}</h3>
        </div>
        <button type="button" style={sessionStyles.closeButton} onClick={onClose}>
          Close
        </button>
      </div>
      <div style={sessionStyles.detailGrid}>
        <DetailItem label="Energy" value={row.kwh} tone="rgba(64,200,255,0.95)" />
        <DetailItem label="Cost" value={formatCurrency(row.cost)} tone="rgba(255,185,50,0.95)" />
        <DetailItem label="Started" value={row.timestamp} />
        <DetailItem label="Ended" value={row.last_timestamp_str} />
        <DetailItem label="Connected" value={formatMinutes(row.duration)} />
        <DetailItem label="Charging" value={formatMinutes(row.minutes_charged)} />
        <DetailItem label="Plugged-in idle" value={formatMinutes(row.plugged_in_idle)} />
        <DetailItem label="Average power" value={formatPower(row)} tone="rgba(80,240,160,0.9)" />
        <DetailItem label="Log day" value={row.day_timestamp_str} />
        <DetailItem label="Raw energy" value={formatJoules(row.joules)} />
      </div>
    </div>
  );
}

function SessionTable({ tabledata, narrow }) {
  const [selectedSession, setSelectedSession] = useState(null);

  if (!tabledata.length) return null;

  const activeSession = tabledata.some((row) => row.first_timestamp === selectedSession)
    ? selectedSession
    : null;

  return (
    <div style={sessionStyles.list}>
      {tabledata.map((row) => {
        const isSelected = activeSession === row.first_timestamp;
        return (
          <div key={row.first_timestamp}>
            <button
              type="button"
              style={{
                ...sessionStyles.card,
                ...(isSelected ? sessionStyles.cardSelected : {}),
              }}
              onClick={() => setSelectedSession(isSelected ? null : row.first_timestamp)}
              aria-expanded={isSelected}
            >
              <span style={sessionStyles.primaryDate}>{row.timestamp}</span>
              <strong style={sessionStyles.delivered}>{row.kwh}</strong>
              <div style={{
                ...sessionStyles.meta,
                gridTemplateColumns: narrow ? "1fr" : sessionStyles.meta.gridTemplateColumns,
              }}>
                <span style={sessionStyles.metaItem}>
                  <span style={sessionStyles.label}>Connected</span>
                  <strong style={sessionStyles.value}>{formatMinutes(row.duration)}</strong>
                </span>
                <span style={sessionStyles.metaItem}>
                  <span style={sessionStyles.label}>Charging</span>
                  <strong style={sessionStyles.value}>{formatMinutes(row.minutes_charged)}</strong>
                </span>
                <span style={sessionStyles.metaItem}>
                  <span style={sessionStyles.label}>Average</span>
                  <strong style={{ ...sessionStyles.value, color: "rgba(80,240,160,0.9)" }}>{formatPower(row)}</strong>
                </span>
              </div>
            </button>
            {isSelected && (
              <SessionDetail row={row} onClose={() => setSelectedSession(null)} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Status / loading states ────────────────────────────────────────────────

function StatusMessage({ icon, title, sub, color = "#8ba3b8" }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 10, padding: "60px 20px", color }}>
      <span style={{ fontSize: "2.4rem" }}>{icon}</span>
      <span style={{ fontSize: "0.9rem", letterSpacing: "0.05em" }}>{title}</span>
      {sub && <span style={{ fontSize: "0.75rem", color: "#5a7080" }}>{sub}</span>}
    </div>
  );
}

// ── Root component ─────────────────────────────────────────────────────────

export default function ChargerSession() {
  const [tabledata, setTabledata] = useState([]);
  const [sessiondata, setSessiondata] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [narrow, setNarrow] = useState(window.innerWidth < 460);
  const [showCost, setShowCost] = useState(false);

  useEffect(() => {
    const onResize = () => setNarrow(window.innerWidth < 460);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    fetch(buildUrl("getsessiondata"), { method: "GET" })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((raw) => {
        const { tabledata, sessiondata } = processSessionData(raw);
        setTabledata(tabledata);
        setSessiondata(sessiondata);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  return (
    <div style={styles.page}>
      <style>{globalCss}</style>
      <div style={styles.pageTitle}>// Charging Log</div>

      {/* Toolbar */}
      <div style={styles.buttonRow}>
        <button
          style={styles.Btn}
          onClick={() => downloadCSV(tabledata)}
          disabled={!tabledata.length}
          onMouseEnter={(e) => {
            e.target.style.background = "#254870";
            e.target.style.borderColor = "#7ab8f0";
          }}
          onMouseLeave={(e) => {
            e.target.style.background = "#1e3a5f";
            e.target.style.borderColor = "#4a7ab8";
          }}
        >
          ↓ Download Charging Log
        </button>
      </div>

      {/* Chart */}
      <div style={styles.section}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, marginBottom: 4 }}>
          <div style={styles.sectionHeader}>Energy Delivered</div>
          {!loading && !error && sessiondata.length > 0 && (
            <MetricToggle showCost={showCost} onChange={setShowCost} />
          )}
        </div>
        {loading ? (
          <StatusMessage icon="⚡" title="Fetching session data…" />
        ) : error ? (
          <StatusMessage icon="⚠" title="Could not load data" sub={error} color="rgba(255,100,80,0.8)" />
        ) : sessiondata.length === 0 ? (
          <StatusMessage icon="🔌" title="No sessions recorded yet" />
        ) : (
          <ChargingChart sessiondata={sessiondata} showCost={showCost} />
        )}
      </div>

      {/* Table */}
      <div style={styles.section}>
        <div style={styles.sectionHeader}>Session History</div>
        {loading ? (
          <StatusMessage icon="⏳" title="Loading sessions…" />
        ) : error ? (
          <StatusMessage icon="⚠" title="Could not load sessions" sub={error} color="rgba(255,100,80,0.8)" />
        ) : tabledata.length === 0 ? (
          <StatusMessage icon="📋" title="No sessions to display" />
        ) : (
          <SessionTable tabledata={tabledata} narrow={narrow} />
        )}
      </div>
    </div>
  );
}
