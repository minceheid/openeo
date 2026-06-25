import { useState, useEffect, useRef, useCallback, Fragment } from "react";
import { getCurrencyConfig, formatCurrency } from '../utils/funcs';

// ── Currency detection ─────────────────────────────────────────────────────

const CURRENCY = getCurrencyConfig();


// ── Session table ──────────────────────────────────────────────────────────

export default function SessionTable({ tabledata, narrow }) {
  const [expandedKey, setExpandedKey] = useState(null);
  const wrapRef = useRef(null);

  // Tap/click outside the table collapses whichever row is open.
  useEffect(() => {
    if (expandedKey === null) return;
    const handleOutside = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setExpandedKey(null);
      }
    };
    document.addEventListener("mousedown", handleOutside);
    document.addEventListener("touchstart", handleOutside);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      document.removeEventListener("touchstart", handleOutside);
    };
  }, [expandedKey]);

  if (!tabledata.length) return null;

  const colSpan = narrow ? 5 : 7;
  const toggle = (key) => setExpandedKey((prev) => (prev === key ? null : key));
  return (
    <div ref={wrapRef} style={{ overflowX: "auto", width: "100%" }}>
      <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: "0 2px", fontSize: "0.78rem" }}>
        <thead>
          <tr>
            <Th>From</Th>
            {!narrow && <Th>To</Th>}
            <Th>Connected<br />(min)</Th>
            <Th>Delivered</Th>
            <Th>Charging<br />(min)</Th>
            {!narrow && <Th>Avg Power</Th>}
            <Th>Cost</Th>
          </tr>
        </thead>
        <tbody>
          {tabledata.map((row, i) => {
            const hasBreakdown = Object.values(row.cost_by_tariff || {}).some((j) => j > 0);
            const expanded = expandedKey === row.first_timestamp;
            return (
              <Fragment key={row.first_timestamp}>
                <tr style={{ background: i % 2 === 0 ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.02)" }}>
                  <Td>{row.timestamp}</Td>
                  {!narrow && <Td>{row.last_timestamp_str}</Td>}
                  <Td>{row.duration}</Td>
                  <Td style={{ color: "rgba(64,200,255,0.9)", fontWeight: 600 }}>{row.kwh}</Td>
                  <Td>{row.minutes_charged}</Td>
                  {!narrow && <Td style={{ color: "rgba(80,240,160,0.85)" }}>{row.average_power}</Td>}
                  <CostCell row={row} expanded={expanded} onToggle={toggle} />
                </tr>
                {hasBreakdown && (
                  <TariffBreakdownRow row={row} colSpan={colSpan} expanded={expanded} narrow={narrow} />
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}


// ── Cost cell + tariff breakdown ────────────────────────────────────────────

function CostCell({ row, expanded, onToggle }) {
  const entries = Object.entries(row.cost_by_tariff || {}).filter(
    ([, joules]) => joules > 0
  );
  const hasBreakdown = entries.length > 0;

  return (
    <td style={{
      padding: "7px 8px",
      textAlign: "center",
      color: "rgba(255,185,50,0.95)",
      fontWeight: 600,
    }}>
      <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
        <span>{formatCurrency(row.cost)}</span>
        {hasBreakdown && (
          <button
            onClick={() => onToggle(row.first_timestamp)}
            aria-label={expanded ? "Hide tariff breakdown" : "Show tariff breakdown"}
            aria-expanded={expanded}
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 2,
              width: 28,
              height: 20,
              borderRadius: 10,
              border: "1px solid rgba(255,185,50,0.5)",
              background: expanded ? "rgba(255,185,50,0.25)" : "rgba(255,185,50,0.1)",
              color: "rgba(255,185,50,0.95)",
              fontSize: "0.65rem",
              fontWeight: 700,
              lineHeight: 1,
              cursor: "pointer",
              flexShrink: 0,
              padding: 0,
              transition: "background 0.2s, border-color 0.2s",
            }}
          >
            <span>i</span>
            <svg
              width="7"
              height="7"
              viewBox="0 0 10 10"
              style={{
                transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
                transition: "transform 0.25s cubic-bezier(0.4,0,0.2,1)",
              }}
            >
              <path
                d="M1 3L5 7L9 3"
                stroke="currentColor"
                strokeWidth="1.5"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        )}
      </div>
    </td>
  );
}

function TariffBreakdownRow({ row, colSpan, expanded, narrow }) {
  const entries = Object.entries(row.cost_by_tariff || {}).filter(
    ([, joules]) => joules > 0
  );

  const fontSize = narrow ? "0.7rem" : "0.78rem";
  const headerFontSize = narrow ? "0.62rem" : "0.68rem";
  const rowGap = narrow ? 10 : 16;

  return (
    <tr>
      <td colSpan={colSpan} style={{ padding: 0, background: "rgba(255,255,255,0.03)" }}>
        <div style={{
          maxHeight: expanded ? 300 : 0,
          opacity: expanded ? 1 : 0,
          overflow: "hidden",
          padding: expanded ? "10px 16px" : "0 16px",
          borderTop: expanded ? "1px solid rgba(255,255,255,0.08)" : "1px solid transparent",
          borderBottom: expanded ? "1px solid rgba(255,255,255,0.08)" : "1px solid transparent",
          transition:
            "max-height 0.3s cubic-bezier(0.4,0,0.2,1), opacity 0.25s ease, padding 0.3s cubic-bezier(0.4,0,0.2,1), border-color 0.3s ease",
          display: "flex",
          justifyContent: "flex-end",
        }}>
          <div style={{
            display: "inline-flex",
            flexDirection: "column",
            gap: 4,
            maxWidth: "100%",
          }}>
            <div style={{
              fontSize: headerFontSize,
              color: "#8ba3b8",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              marginBottom: 2,
              fontWeight: 600,
              textAlign: "right",
            }}>
              Tariff breakdown
            </div>
            {entries.map(([rate, joules]) => {
              const kwh = Math.round(joules / 360000) / 10;
              const tariffCost = parseFloat(rate) * kwh;
              return (
                <div key={rate} style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: rowGap,
                  fontSize,
                  color: "#c8dde8",
                }}>
                  <span style={{ color: "rgba(255,185,50,0.85)" }}>
                    {CURRENCY.symbol}{parseFloat(rate).toFixed(3)}/kWh
                  </span>
                  <span>{kwh} kWh</span>
                  <span style={{ fontWeight: 600 }}>{formatCurrency(tariffCost)}</span>
                </div>
              );
            })}
          </div>
        </div>
      </td>
    </tr>
  );
}


const Th = ({ children, style }) => (
  <th style={{ padding: "10px 8px", textAlign: "center", color: "#8ba3b8", fontWeight: 500, letterSpacing: "0.06em", fontSize: "0.72rem", textTransform: "uppercase", background: "rgba(255,255,255,0.06)", borderBottom: "1px solid rgba(255,255,255,0.1)", ...style }}>
    {children}
  </th>
);

const Td = ({ children, style }) => (
  <td style={{ padding: "7px 8px", textAlign: "center", color: "#c8dde8", ...style }}>
    {children}
  </td>
);