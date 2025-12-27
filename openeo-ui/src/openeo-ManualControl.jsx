import React, { useMemo, useRef, useState, useEffect } from "react";
import AmpSlider from "./openeo-AmpSlider";
import Toggle from "./openeo-Toggle";

export default function ManualControl({ schedule, onChange, onCommit,setTimersActive }) {

  return (
<div className="flex flex-col items-center p-5 gap-3">

  <div className="text-white/80 text-3xl font-semibold unselectable">
    Manual Override
  </div>

  <Toggle
    enabled={schedule.scheduler_enabled}
    onChange={(v) => {
      schedule.scheduler_enabled=v;
      onChange({ ...schedule, scheduler_enabled: v });
      setTimersActive(v)
      onCommit();
    }}
  />
  <div className="text-white/80 mb-3">
    Timers {schedule.scheduler_enabled ? "Enabled" : "Disabled"}
  </div>
  
  <Toggle
    enabled={schedule.enabled}
    onChange={(v) => {
      schedule.enabled=v;
      onChange({ ...schedule, enabled: v });
      onCommit();
    }}
  />
  <div className="text-white/80 mb-3" > 
    Charging {schedule.enabled ? "Enabled" : "Disabled"}
  </div>



    <div className="absolute bottom-0 w-[80%]" style={{marginBottom: "20px"}}>

    <AmpSlider
      value={schedule.amps}
      min={0}
      max={32}
      onChange={(v) => onChange({ ...schedule, amps: v })}
      onCommit={onCommit}
    />
  </div>
</div>


  );
}
