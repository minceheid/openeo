import React, { useMemo, useRef, useState, useEffect } from "react";
import AmpSlider from "./openeo-AmpSlider";
import Toggle from "./openeo-Toggle";

export default function ManualControl({ schedule, onChange, onCommit,setTimersActive,active }) {

  return (
<div className="flex flex-col items-center p-5 gap-3 w-fit justify-center">

  <div className="absolute top-0  items-center justify-center text-white/80 text-3xl font-semibold unselectable mt-5">
  
    Manual Override
  </div>

  <Toggle
    enabled={schedule.scheduler_enabled}
    onChange={(v) => {
      if(active) {
        schedule.scheduler_enabled=v;
        onChange({ ...schedule, scheduler_enabled: v });
        setTimersActive(v)
        onCommit();
      }
    }}
  />
  <div className="text-white/80 mb-2">
    Timers {schedule.scheduler_enabled ? "Enabled" : "Disabled"}
  </div>
  
  <Toggle
    enabled={schedule.enabled}
    onChange={(v) => {
      if(active) {
        schedule.enabled=v;
        onChange({ ...schedule, enabled: v });
        onCommit();
      }
    }}
  />

  <div className="text-white/80 mb-3" > 
    Charging {schedule.enabled ? "Enabled" : "Disabled"}
  </div>

  <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[80%] mb-[15px]">
    <AmpSlider
      value={schedule.amps}
      min={0}
      max={32}
      onChange={(v) => { active &&  onChange({ ...schedule, amps: v })} }
      onCommit={active && onCommit}
      active={active}
    />
  </div>
</div>

  );
}
