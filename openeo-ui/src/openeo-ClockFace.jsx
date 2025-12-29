import React, { useMemo, useRef, useState, useEffect } from "react";
import AmpSlider from "./openeo-AmpSlider";


function hexToRgb(hex) {
  const clean = hex.replace("#", "");
  const bigint = parseInt(clean, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return [r, g, b];
}

function lerpColor(rgbStart, rgbEnd, t) {
  const r = Math.round(rgbStart[0] + (rgbEnd[0] - rgbStart[0]) * t);
  const g = Math.round(rgbStart[1] + (rgbEnd[1] - rgbStart[1]) * t);
  const b = Math.round(rgbStart[2] + (rgbEnd[2] - rgbStart[2]) * t);
  return `rgb(${r},${g},${b})`;
}


function gradientArcSegments(cx, cy, r, startMin, endMin, steps = 120) {
  const segs = [];
  const total = (endMin - startMin + 1440) % 1440;

  const colorStart = hexToRgb("#4dabf7");
  const colorEnd = hexToRgb("#f74d4d");

  for (let i = 0; i < steps; i++) {
    const t0 = i / steps;
    const t1 = (i + 1) / steps;

    const m0 = startMin + total * t0;
    const m1 = startMin + total * t1;

    const color = lerpColor(colorStart, colorEnd, t0);

    segs.push(
      <path
        key={i}
        d={arcPath(cx, cy, r, m0, m1)}
        stroke={color}
        strokeWidth={10}
        fill="none"
        strokeLinecap="round"
      />
    );
  }
  return segs;
}


// --- Utility helpers ---
const clamp = (n, min, max) => Math.min(max, Math.max(min, n));
const pad2 = (n) => n.toString().padStart(2, "0");
const minutesToHHMM = (m) => `${pad2(Math.floor(m / 60))}${pad2(m % 60)}`;

const snap = (m, step = 5) => Math.round(m / step) * step; // snap to 5-minute increments

const minutesToAngle = (m) => (m / 1440) * 360 - 90; // 0 minutes -> top
const angleToMinutes = (deg,step) => {
  let a = (deg + 90) % 360;
  if (a < 0) a += 360;
  return snap(Math.round((a / 360) * 1440),step);
};

// SVG Arc path from start minutes to end minutes, always clockwise, wrapping over midnight when needed
function arcPath(cx, cy, r, startMin, endMin) {
  const startA = (minutesToAngle(startMin) * Math.PI) / 180;
  const endA = (minutesToAngle(endMin) * Math.PI) / 180;
  const sx = cx + r * Math.cos(startA);
  const sy = cy + r * Math.sin(startA);
  const ex = cx + r * Math.cos(endA);
  const ey = cy + r * Math.sin(endA);

  // Clockwise sweep length (0..360)
  let diff = ((endMin - startMin + 1440) % 1440) * (360 / 1440); // degrees
  const largeArc = diff > 180 ? 1 : 0;
  const sweep = 1; // clockwise

  return `M ${sx} ${sy} A ${r} ${r} 0 ${largeArc} ${sweep} ${ex} ${ey}`;
}

// --- ClockFace component ---
export default function ClockFace({
  schedule,
  onChange,
  onCommit,
  snapStep,
  timersActive,
  active
}) {
  const size = 360;
  const cx = size / 2;
  const cy = size / 2;
  const radius = 140;
  const handleRadius = 12;

  const svgRef = useRef(null);
  const dragging = useRef(null); // "start" | "end" | null

  const startAngle = minutesToAngle(schedule.start);
  const endAngle = minutesToAngle(schedule.end);

  const handleDrag = (e) => {
    if (!dragging.current) return;
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const cursor = pt.matrixTransform(svg.getScreenCTM().inverse());
    const dx = cursor.x - cx;
    const dy = cursor.y - cy;
    let deg = (Math.atan2(dy, dx) * 180) / Math.PI; // -180..180, 0 at +x axis
    // Convert so 0 is at top
    deg = deg; // minutes conversion handles top offset
    const minutes = clamp(angleToMinutes(deg,snapStep), 0, 1439);

    if (dragging.current === "start") {
      onChange({ ...schedule, start: minutes });
    } else if (dragging.current === "end") {
      onChange({ ...schedule, end: minutes });
    }
  };

  const stopDrag = () => (dragging.current = null);

  // Called when user releases mouse
  //const handleMouseUp = () => {
  //  onCommit(); // triggers POST in parent
  //};
  useEffect(() => {
    window.addEventListener("pointerup", stopDrag);
    window.addEventListener("pointermove", handleDrag);
    return () => {
      window.removeEventListener("pointerup", stopDrag);
      window.removeEventListener("pointermove", handleDrag);
    };
  });

  const startPos = useMemo(() => {
    const a = (startAngle * Math.PI) / 180;
    return { x: cx + radius * Math.cos(a), y: cy + radius * Math.sin(a) };
  }, [startAngle]);

  const endPos = useMemo(() => {
    const a = (endAngle * Math.PI) / 180;
    return { x: cx + radius * Math.cos(a), y: cy + radius * Math.sin(a) };
  }, [endAngle]);

  const pathD = arcPath(cx, cy, radius, schedule.start, schedule.end);

  return (

    <div className="flex flex-col items-center p-5 gap-3 w-fit justify-start">

      { !timersActive ? (<h1>INACTIVE</h1>) : (<></>)}
      <svg
        ref={svgRef}
        viewBox={`0 0 ${size} ${size}`}
        className="w-[320px] sm:w-[360px] drop-shadow-xl
        absolute top-0 left-1/2 -translate-x-1/2 translate-y-1/10
        "
      >
        <defs>
          <radialGradient id="glow" r="60%">
            <stop offset="60%" stopColor="#ffffff11" />
            <stop offset="100%" stopColor="#ffffff00" />
          </radialGradient>

        </defs>

        {/* soft backdrop */}
        <circle cx={cx} cy={cy} r={radius + 40} fill="url(#glow)" />

        {/* base ring */}
        <circle cx={cx} cy={cy} r={radius} className="stroke-white" strokeWidth={4} fill="none" />

        {/* active arc */}
        {gradientArcSegments(cx, cy, radius, schedule.start, schedule.end, 120)}

        {/* start handle */}
    <g
  className={`cursor-pointer ${!active ? "cursor-not-allowed" : ""}`}
  {...(active
    ? {
        onPointerDown: () => (dragging.current = "start"),
        onMouseUp: () => onCommit(),
        onTouchEnd: () => onCommit(),
      }
    : {})}
>
          <circle cx={startPos.x} cy={startPos.y} r={handleRadius} fill="#4dabf7" />
        </g>

        {/* end handle */}
<g
  className={`cursor-pointer ${!active ? "cursor-not-allowed" : ""}`}
  {...(active
    ? {
        onPointerDown: () => (dragging.current = "end"),
        onPointerUp: () => onCommit(),
        onTouchEnd: () => onCommit(),
      }
    : {})}
>
          <circle cx={endPos.x} cy={endPos.y} r={handleRadius} fill="#f74d4d" />
        </g>

        {/* center text */}
        <g>
          <text x={cx} y={cy - 6} textAnchor="middle" className="fill-white/80 unselectable" style={{ fontSize: 30, fontWeight: 600 }}>
            Start: <tspan className="fill-white unselectable" style={{ fontWeight: 800 }}>{minutesToHHMM(schedule.start)}</tspan>
          </text>
          <text x={cx} y={cy + 28} textAnchor="middle" className="fill-white/80 unselectable" style={{ fontSize: 30, fontWeight: 600 }}>
            End: <tspan className="fill-white unselectable" style={{ fontWeight: 800 }}>{minutesToHHMM(schedule.end)}</tspan>
          </text>
        </g>
      </svg>

      {/* Amps slider */}
     <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[80%] mb-[15px]">
        <AmpSlider
        value={schedule.amps}
        min={6}
        max={32}
        onChange={(v) => onChange({ ...schedule, amps: v })}
        onCommit={onCommit}
        active={active}
        />
      </div>
    </div>
  );
}
