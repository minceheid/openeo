import { useState } from "react";
import { buildUrl } from '../utils/funcs';
import { globalCss,styles } from '../utils/styles';

const CarIcon = ({ size = 40 }) => (
  <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
    <path d="M7 22l3-8h20l3 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    <rect x="5" y="22" width="30" height="11" rx="3" stroke="currentColor" strokeWidth="1.8" fill="none"/>
    <circle cx="12" cy="33" r="3" stroke="currentColor" strokeWidth="1.8" fill="none"/>
    <circle cx="28" cy="33" r="3" stroke="currentColor" strokeWidth="1.8" fill="none"/>
    <path d="M10 22l2-5h16l2 5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" fill="none" opacity="0.5"/>
    <rect x="13" y="15" width="14" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.2" fill="none" opacity="0.4"/>
  </svg>
);


const GridIcon = ({ size = 40 }) => (
<svg width="120" height="200" viewBox="0 0 120 200" xmlns="http://www.w3.org/2000/svg">
  <g stroke="currentColor" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round">
    <line x1="20" y1="45" x2="100" y2="45"/>

    <line x1="30" y1="45" x2="60" y2="80"/>
    <line x1="90" y1="45" x2="60" y2="80"/>

    <line x1="30" y1="80" x2="90" y2="80"/>

    <line x1="40" y1="80" x2="60" y2="130"/>
    <line x1="80" y1="80" x2="60" y2="130"/>

    <line x1="40" y1="130" x2="80" y2="130"/>

    <line x1="60" y1="80" x2="30" y2="190"/>
    <line x1="60" y1="80" x2="90" y2="190"/>

    <line x1="30" y1="190" x2="90" y2="190"/>
    <line x1="60" y1="30" x2="60" y2="190"/>
    <circle cx="30" cy="80" r="3"/>
    <circle cx="90" cy="80" r="3"/>
    <circle cx="40" cy="130" r="3"/>
    <circle cx="80" cy="130" r="3"/>

  </g>
</svg>)

const SolarIcon = ({ size = 40 }) => (
<svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" fill="none">
  <circle cx="32" cy="32" r="12" fill="currentColor"/>

  <g stroke="currentColor" strokeWidth="3" strokeLinecap="round">
    <line x1="32" y1="4"  x2="32" y2="14"/>
    <line x1="32" y1="50" x2="32" y2="60"/>
    <line x1="4"  y1="32" x2="14" y2="32"/>
    <line x1="50" y1="32" x2="60" y2="32"/>

    <line x1="12" y1="12" x2="19" y2="19"/>
    <line x1="45" y1="45" x2="52" y2="52"/>
    <line x1="12" y1="52" x2="19" y2="45"/>
    <line x1="45" y1="19" x2="52" y2="12"/>
  </g>
</svg>
);

const BoltIcon = ({ size = 30 }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none">
    <path d="M10 2L4 10h5l-1 6 6-8H9l1-6z" fill="currentColor"/>
  </svg>
);

function FlowLine({ x1, y1, x2, y2, color, speed, width = 2, active, amps }) {
  const dashLen = 10;
  const gapLen = Math.max(4, 18 - amps * 0.12);
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2}
        stroke={color} strokeWidth={width} strokeOpacity={0.18} strokeLinecap="round"/>
      {active && (
        <line x1={x1} y1={y1} x2={x2} y2={y2}
          stroke={color} strokeWidth={width} strokeLinecap="round"
          strokeDasharray={`${dashLen} ${gapLen}`} strokeOpacity={0.85}>
          <animate attributeName="stroke-dashoffset"
            from={0} to={-(dashLen + gapLen)}
            dur={`${speed}s`} repeatCount="indefinite"/>
        </line>
      )}
    </g>
  );
}

function Node({ cx, cy, icon, label, sublabel, color, size = 80 }) {
  return (
    <g>
      <circle cx={cx} cy={cy} r={size / 2 + 4} fill={color} fillOpacity={0.12}/>
      <circle cx={cx} cy={cy} r={size / 2} fill={color} fillOpacity={0.18}
        stroke={color} strokeWidth={1.5} strokeOpacity={0.4}/>
      <foreignObject x={cx - 22} y={cy - 22} width={44} height={44}>
        <div style={{ color, display: "flex", alignItems: "center", justifyContent: "center", width: 44, height: 44 }}>
          {icon}
        </div>
      </foreignObject>
      <text x={cx} y={cy + size / 2 + 18} textAnchor="middle"
        fontSize={17} fontWeight={600} fill={color} fontFamily="inherit">{label}</text>
      {sublabel && (
        <text x={cx} y={cy + size / 2 + 32} textAnchor="middle"
          fontSize={15} fill={color} fillOpacity={0.6} fontFamily="inherit">{sublabel}</text>
      )}
    </g>
  );
}

function ChargerHub({ cx, cy, status, totalAmps }) {
  const isActive = status === "charging";
  const color = isActive ? "#4ade80" : status === "connected" ? "#60a5fa" : "#94a3b8";
  return (
    <g>
      {isActive && (
        <>
          <circle cx={cx} cy={cy} r={52} fill="none" stroke={color} strokeWidth={1.5} strokeOpacity={0}>
            <animate attributeName="r" from={44} to={70} dur="2s" repeatCount="indefinite"/>
            <animate attributeName="stroke-opacity" from={0.5} to={0} dur="2s" repeatCount="indefinite"/>
          </circle>
          <circle cx={cx} cy={cy} r={52} fill="none" stroke={color} strokeWidth={1} strokeOpacity={0}>
            <animate attributeName="r" from={44} to={80} dur="2s" begin="0.6s" repeatCount="indefinite"/>
            <animate attributeName="stroke-opacity" from={0.3} to={0} dur="2s" begin="0.6s" repeatCount="indefinite"/>
          </circle>
        </>
      )}
      <circle cx={cx} cy={cy} r={44} fill={color} fillOpacity={0.1}
        stroke={color} strokeWidth={2} strokeOpacity={0.5}/>
      <circle cx={cx} cy={cy} r={36} fill={color} fillOpacity={0.15}/>
      <g transform={`translate(${cx - 9},${cy - 11})`} style={{ color }}>
        <BoltIcon size={20}/>
      </g>
      <text x={cx} y={cy + 18} textAnchor="middle" fontSize={11}
        fontWeight={700} fill={color} fontFamily="inherit">
        {totalAmps > 0 ? `${totalAmps} A` : "–"}
      </text>
    </g>
  );
}

function StatusBadge({ status, amps }) {
  const cfg = {
    idle:      { label: "Idle - Vehicle Disconnected",                         bg: "var(--color-background-secondary)", color: "var(--color-text-secondary)" },
    connected: { label: "Idle - Vehicle Connected",                    bg: "#1e3a5f", color: "#60a5fa" },
    charging:  { label: amps > 0 ? "Charging" : "Ready", bg: "#14532d", color: "#4ade80" },
  }[status] || {};
  return (
    <span style={{ fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 20,
      background: cfg.bg, color: cfg.color, letterSpacing: 0.5, display: "inline-flex", alignItems: "center", gap: 5 }}>
      {amps > 0 && status === "charging" && (
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: cfg.color,
          display: "inline-block", animation: "blink 1.4s infinite" }}/>
      )}
      {cfg.label}
    </span>
  );
}

const CHARGER_STATES = [
  { label: "Idle - Vehicle Disconnected",         status: "idle",      carConnected: false, solarEnabled: false},
  { label: "IDle - Vehicle Connected",status: "connected", carConnected: true,  solarEnabled: false},
  { label: "Grid only",    status: "charging",  carConnected: true,  solarEnabled: false},
  { label: "Solar only",   status: "charging",  carConnected: true,  solarEnabled: true },
  { label: "Solar + Grid", status: "charging",  carConnected: true,  solarEnabled: true},
];

const toRad = (deg) => (deg * Math.PI) / 180;

// Trim a line between two circle centres by their radii
function edgePts(ax, ay, bx, by, rA, rB) {
  const dx = bx - ax, dy = by - ay, d = Math.sqrt(dx * dx + dy * dy);
  const ux = dx / d, uy = dy / d;
  return { x1: ax + ux * rA, y1: ay + uy * rA, x2: bx - ux * rB, y2: by - uy * rB };
}

export default function EVChargerStatus(
  status
) {
  const [customAmps, setCustomAmps] = useState(null);

  var gridAmps=0;
  var solarAmps=0;
  var stateIdx=0;
  if (status==null || status.status==null || status.status.eo_serial_number==null) {

    function WaitingForConnection() {

      const styles = {
        container: {
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",        // or 100vh if full screen
          width: "100%",
        },
        text: {
          fontSize: "2rem",      // big friendly text
          fontWeight: 600,
          color: "#ccc",         // soft, friendly tone
          textAlign: "center",
        },
      };
      return (
        <div style={styles.container}>
          <div style={styles.text}>
            Waiting For Serial Connection
          </div>
        </div>
      );
    };

    return (
      <WaitingForConnection/>
    );
  }
  
  const openeo_state=Number(status.status.eo_charger_state_id);

  if (openeo_state<9) {
    stateIdx=0; // Idle
  } else if (openeo_state!=99 && (openeo_state<11 || openeo_state>12)) {
    stateIdx=1; // Car Connected
  } else {
    if (status.status.eo_current_vehicle - status.status.eo_current_solar <2 ) {
      stateIdx=3; // Solar only
      solarAmps=status.status.eo_current_vehicle;
      gridAmps=0;
    } else if (status.status.eo_current_solar<2) {
      stateIdx=2; // Grid only
      solarAmps=0;
      gridAmps=status.status.eo_current_vehicle;
    } else {
      stateIdx=4; // Solar + Grid
      gridAmps=status.status.eo_current_vehicle-status.status.eo_current_solar;
      solarAmps=status.status.eo_current_vehicle-gridAmps;
    }
  }


  const state = CHARGER_STATES[stateIdx];
  const totalAmps = gridAmps + solarAmps;

  const flowSpeed  = totalAmps > 0 ? Math.max(0.4, 2.5 - totalAmps * 0.06) : 9999;
  const lineWidth  = totalAmps > 0 ? Math.min(4, 1.5 + totalAmps * 0.5) : 1.5;
  const isCharging = state.status === "charging" && totalAmps > 0;

  // ── Layout ───────────────────────────────────────────────────────────────
  const W = 420, H = 320, CX = 210, CY = 160;
  const ORBIT  = 160;  // hub-centre to node-centre distance
  const NODE_R = 34;   // node circle radius
  const HUB_R  = 46;   // hub circle radius

  // Build ordered list of visible nodes
  const nodeKeys = [
    "grid",
    ...(state.solarEnabled ? ["solar"] : []),
    ...(state.carConnected ? ["car"]   : []),
  ];
  const n = nodeKeys.length;

  // Starting angle per node count so the layout always looks balanced:
  //   1 node  → grid at left  (180°)
  //   2 nodes → grid left, car right  (180° + 180°)
  //   3 nodes → grid bottom-left, solar top, car bottom-right  (210°, 330°, 90°)
  const startAngle = { 1: 180, 2: 180, 3: 210 }[n] ?? 180;

  const nodePos = (i) => ({
    x: CX + ORBIT * Math.cos(toRad(startAngle + i * (360 / n))),
    y: CY + ORBIT * Math.sin(toRad(startAngle + i * (360 / n))),
  });

  const positions = Object.fromEntries(nodeKeys.map((k, i) => [k, nodePos(i)]));
  const gp = positions.grid;
  const sp = positions.solar;
  const cp = positions.car;

  const gridLine  = edgePts(gp.x, gp.y, CX, CY, NODE_R, HUB_R);
  const solarLine = sp ? edgePts(sp.x, sp.y, CX, CY, NODE_R, HUB_R) : null;
  const carLine   = cp ? edgePts(CX, CY, cp.x, cp.y, HUB_R, NODE_R) : null;

  return (
    <>
    <div className="absolute top-0  items-center justify-center text-white/80 text-3xl font-semibold unselectable mt-5">
        Status
    </div>

    <div style={{ fontFamily: "'Inter','Segoe UI',sans-serif",
      background: "var(--color-background-primary)",
      border: "0.5px solid var(--color-border-tertiary)",
      borderRadius: 16, padding: "24px 20px 20px",
      maxWidth: 460, margin: "0 auto" }}>

      <style>{`@keyframes blink{0%,100%{opacity:1}50%{opacity:0.2}}`}</style>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 4 }}>
        <StatusBadge status={state.status} amps={totalAmps}/>
      </div>

      {/* Diagram */}
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ overflow: "visible", display: "block" }}>

        {(gridAmps > 0 || !isCharging) && (
          <FlowLine {...gridLine} color="#60a5fa"
            speed={flowSpeed * 1.1} width={lineWidth}
            active={isCharging && gridAmps > 0} amps={gridAmps}/>
        )}

        {solarLine && (
          <FlowLine {...solarLine} color="#facc15"
            speed={flowSpeed * 0.9} width={lineWidth}
            active={isCharging && solarAmps > 0} amps={solarAmps}/>
        )}

        {carLine && (
          <FlowLine {...carLine} color="#4ade80"
            speed={flowSpeed} width={lineWidth + 0.5}
            active={isCharging} amps={totalAmps}/>
        )}

        <ChargerHub cx={CX} cy={CY} status={state.status} totalAmps={totalAmps}/>

        <Node cx={gp.x} cy={gp.y} icon={<GridIcon size={32}/>}
          label="Grid" sublabel={gridAmps > 0 ? `${gridAmps} A` : "standby"}
          color="#60a5fa"/>

        {sp && (
          <Node cx={sp.x} cy={sp.y} icon={<SolarIcon size={32}/>}
            label="Solar" sublabel={solarAmps > 0 ? `${solarAmps} A` : "0 A"}
            color="#facc15"/>
        )}

        {cp && (
          <Node cx={cp.x} cy={cp.y} icon={<CarIcon size={32}/>}
            label="Vehicle" sublabel={totalAmps > 0 ? `${totalAmps} A` : "connected"}
            color="#4ade80"/>
        )}
      </svg>
    </div>
    </>
  );
}