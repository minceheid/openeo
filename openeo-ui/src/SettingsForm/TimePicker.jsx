import { useCallback,useState } from "react";
import { styles } from "../utils/styles";

import { useEffect, useRef } from "react";

const ITEM_H = 30;

function Drum({ items, selected, onSelect }) {
  const ref = useRef(null);

  useEffect(() => {
    const idx = items.indexOf(selected);
    if (ref.current && idx >= 0) {
      ref.current.scrollTop = idx * ITEM_H;
    }
  }, [selected, items]);

  return (
    <div ref={ref} style={{
      height: 120, overflowY: "scroll", scrollSnapType: "y mandatory",
      scrollbarWidth: "none", border: "0.5px solid #2a2f3d", borderRadius: 6,
      background: "#10141e", width: 56,
    }}>
      {items.map(v => (
        <div key={v} onClick={() => onSelect(v)} style={{
          height: ITEM_H, display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: "monospace", fontSize: 15, scrollSnapAlign: "start", cursor: "pointer",
          color: v === selected ? "#378ADD" : "#6b7280",
          fontWeight: v === selected ? 700 : 400,
          background: v === selected ? "#1e3a5f" : "transparent",
          borderRadius: 5,
        }}>
          {String(v).padStart(2, "0")}
        </div>
      ))}
    </div>
  );
}

export default function TimePicker({ periodIndex, currentMins, minMins, onConfirm, onCancel }) {
  const initHH = Math.floor(currentMins / 60);
  const initMM = currentMins % 60;
  const [hh, setHH] = useState(initHH);
  const [mm, setMM] = useState(initMM);

  // Need useState — import it at top of this file
  const minHH = Math.floor(minMins / 60);
  const hours = Array.from({ length: 24 - minHH }, (_, i) => i + minHH);
  const mins  = Array.from({ length: 60 }, (_, i) => i);

  function handleSetHH(h) {
    setHH(h);
    if (h * 60 + mm < minMins) setMM(minMins % 60);
  }

  function handleOk() {
    const val = hh * 60 + mm;
    if (val >= minMins && val <= 1439) onConfirm(val);
  }

  return (
    <div onClick={e => e.target === e.currentTarget && onCancel()} style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
      zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div style={{
        background: "#1a1f2e", border: "0.5px solid #383e4d", borderRadius: 10,
        padding: 16, width: 240, boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
      }}>
        <div style={{ fontSize: 12, color: "#6b7280", textAlign: "center", marginBottom: 12 }}>
          Set end time for period {periodIndex + 1}
        </div>
        <div style={{ fontFamily: "monospace", fontSize: 28, fontWeight: 600,
          color: "#e0e4ef", textAlign: "center", marginBottom: 14, letterSpacing: 2 }}>
          {String(hh).padStart(2,"0")}:{String(mm).padStart(2,"0")}
        </div>
        <div style={{ display: "flex", gap: 8, justifyContent: "center", marginBottom: 14,
          alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 10, color: "#6b7280", textAlign: "center", marginBottom: 3 }}>HH</div>
            <Drum items={hours} selected={hh} onSelect={handleSetHH} />
          </div>
          <div style={{ fontSize: 22, color: "#4b5563", marginTop: 18 }}>:</div>
          <div>
            <div style={{ fontSize: 10, color: "#6b7280", textAlign: "center", marginBottom: 3 }}>MM</div>
            <Drum items={mins} selected={mm} onSelect={setMM} />
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={onCancel} style={{
            flex: 1, padding: 7, borderRadius: 6, cursor: "pointer", fontSize: 13,
            background: "#1a1f2e", color: "#6b7280", border: "0.5px solid #2a2f3d",
          }}>Cancel</button>
          <button onClick={handleOk} style={{
            flex: 1, padding: 7, borderRadius: 6, cursor: "pointer", fontSize: 13,
            background: "#1e3a5f", color: "#7ab8f0", border: "0.5px solid #4a7ab8",
          }}>Set</button>
        </div>
      </div>
    </div>
  );
}