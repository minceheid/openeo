// TariffInput.jsx
import { useCallback,useState } from "react";
import { buildUrl,getCurrencyConfig } from '../utils/funcs';
import { styles } from "../utils/styles";
import TimePicker from "./TimePicker";
import { FaTrashAlt } from 'react-icons/fa'; // FontAwesome version

// ── Currency detection ─────────────────────────────────────────────────────

const CURRENCY = getCurrencyConfig();

const COLORS = ["#378ADD","#1D9E75","#D85A30","#7F77DD","#BA7517","#D4537E","#639922","#888780"];

function minsToHHMM(m) {
  return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
}

function toInternal(periods) {
  return periods.map(p => {
    const endStr = String(p.end ?? "2359").replace(":", "");
    const endMins = typeof p.end === "number"
      ? p.end
      : parseInt(endStr.slice(0, 2), 10) * 60 + parseInt(endStr.slice(2, 4), 10);
    return { end: endMins, cost: p.cost };
  });
}

function toExternal(internal) {
  let cursor = 0;
  return internal.map(p => {
    const start = minsToHHMM(cursor).replace(":", "");
    const end   = minsToHHMM(p.end).replace(":", "");
    cursor = p.end + 1;
    return { start, end, cost: p.cost };
  });
}

function periodStart(periods, i) {
  return i === 0 ? 0 : periods[i - 1].end + 1;
}

export default function TariffInput({ field, value, onChange }) {
  const raw = Array.isArray(value) ? value : (field.default || []);
  const periods = toInternal(raw);

  const [pickerIndex, setPickerIndex] = useState(null);

  const commit = useCallback((next) => {
    onChange(field.name, toExternal(next));
  }, [field.name, onChange]);

  const isLast = (i) => i === periods.length - 1;
  const fullyCovers = periods.length > 0 && periods[periods.length - 1].end === 1439;
  const canAdd = !fullyCovers;

  function handlePickerConfirm(newMins) {
    const next = periods.map((p, i) =>
      i === pickerIndex ? { ...p, end: newMins } : p
    );
    commit(next);
    setPickerIndex(null);
  }

  function setCost(i, val) {
    const next = periods.map((p, idx) =>
      idx === i ? { ...p, cost: parseFloat(val) || 0 } : p
    );
    commit(next);
  }

  function addPeriod() {
    const last = periods[periods.length - 1];
    const newStart = last ? last.end + 1 : 0;
    if (newStart > 1439) return;
    commit([...periods, { end: Math.min(newStart + 119, 1439), cost: 0.27048 }]);
  }

  function removePeriod(i) {
    commit(periods.filter((_, idx) => idx !== i));
  }

  const chipStyle = (locked, color) => ({
    fontFamily: "monospace", fontSize: 12, whiteSpace: "nowrap",
    padding: "3px 5px", borderRadius: 5,
    color: locked ? "#9ca3af" : color,
    background: locked ? "transparent" : "#1a1f2e",
    border: locked ? "none" : "0.5px solid #383e4d",
    cursor: locked ? "default" : "pointer",
    userSelect: "none",
  });

  return (
    <div >

      {periods.map((p, i) => {
        const start = periodStart(periods, i);
        const locked = !isLast(i);
        const color = COLORS[i % COLORS.length];

        return (
          <div key={i} style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "5px 8px", borderRadius: 7, marginBottom: 5,
            border: "0.5px solid #2a2f3d", borderLeft: `3px solid ${color}`,
            background: "#10141e", opacity: locked ? 0.75 : 1,
          }}>
            {/* Start (always derived) */}
            <span style={{ fontFamily: "monospace", fontSize: 12,
              color: "#6b7280", minWidth: 38 }}>
              {minsToHHMM(start)}
            </span>

            <span style={{ color: "#4b5563", fontSize: 11 }}>→</span>

            {/* End — tappable chip if last, static if locked */}
            <span
              style={chipStyle(locked, color)}
              onClick={() => !locked && setPickerIndex(i)}
              title={locked ? undefined : "Tap to change"}
            >
              {minsToHHMM(p.end)}
            </span>

            {/* Cost */}
            <div style={{ display: "flex", alignItems: "center",
              gap: 2, marginLeft: "auto" }}>
              <span style={{ fontSize: 12, color: "#6b7280" }}>
                {CURRENCY.symbol}
              </span>
              <input
                type="number" value={p.cost.toFixed(5)}
                step="0.00001" min="0"
                onChange={e => setCost(i, e.target.value)}
                style={{
                  width: 80, padding: "3px 5px", borderRadius: 5,
                  border: "0.5px solid #383e4d", background: "#1a1f2e",
                  color: "#e0e4ef", fontSize: 12, fontFamily: "monospace",
                  textAlign: "right",
                }}
              />
            </div>

            {/* Delete — last period only */}
            <button
              onClick={() => removePeriod(i)}
              disabled={locked}
              style={{ ...styles.Btn,
                background: locked ? "none" : styles.Btn.background,
                border: locked ? "none" : styles.Btn.border,
                cursor: locked ? "default" : "pointer",
                color: locked ? "transparent" : styles.Btn.color, 
                padding: "4px 4px"
              }}
            > <FaTrashAlt size={14} /></button>
          </div>
        );
      })}

      {/* Timeline bar */}
      <div style={{ height: 18, borderRadius: 6, overflow: "hidden", display: "flex",
        border: "0.5px solid #2a2f3d", margin: "10px 0 3px" }}>
        {periods.map((p, i) => {
          const s = periodStart(periods, i);
          const pct = (p.end - s + 1) / 1440 * 100;
          return (
            <div key={i} style={{ flex: pct.toFixed(2), background: COLORS[i % COLORS.length],
              height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 9, color: "#fff", overflow: "hidden", whiteSpace: "nowrap" }}
              title={`${minsToHHMM(s)}–${minsToHHMM(p.end)}: ${CURRENCY.symbol}${p.cost.toFixed(5)}/kWh`}>
              {pct > 10 ? `${CURRENCY.symbol}${p.cost.toFixed(3)}` : ""}
            </div>
          );
        })}
      </div>
      <div style={{ fontSize: 10, color: "#6b7280", textAlign: "right", marginBottom: 8 }}>
        {Math.round(periods.reduce((acc, p, i) =>
          acc + p.end - periodStart(periods, i) + 1, 0) / 1440 * 100)}% of day covered
      </div>

      {!fullyCovers && (
        <div style={{ fontSize: 11, color: "#f87171", marginBottom: 5 }}>
          ⚠ Periods must cover through 23:59
        </div>
      )}


      <button disabled={!canAdd} onClick={addPeriod} 
        style={{ ...styles.Btn,
        display: 'block', 
        margin: "0 auto",
        background: canAdd ? styles.Btn.background : "none",
        border: canAdd ? styles.Btn.border : "none",
        cursor: canAdd ? "pointer" : "default",
        color: canAdd ? styles.Btn.color : "transparent",
        visibility: canAdd ? "visible" : "hidden",
        }}>
        + Add period
      </button>

      {/* Time picker modal */}
      {pickerIndex !== null && (
        <TimePicker
          periodIndex={pickerIndex}
          currentMins={periods[pickerIndex].end}
          minMins={periodStart(periods, pickerIndex)}
          onConfirm={handlePickerConfirm}
          onCancel={() => setPickerIndex(null)}
        />
      )}
    </div>
  );
}