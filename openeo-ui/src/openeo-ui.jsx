import React, { useMemo, useRef, useState, useEffect } from "react";
import StatusPanel from "./openeo-StatusPanel";
import ManualControl from "./openeo-ManualControl";
import ClockFace from "./openeo-ClockFace";

let updateTick = 0;
let updateFreq = 1;

// Interval timers
var statusUpdateInterval=10000;
var configUpdateInterval=30000;


/////////////////////////////////
// On mobile phones, disable left/right swipe, if we can
document.addEventListener('touchmove', e => {
  if (Math.abs(e.touches[0].clientX) > 10) {
    e.preventDefault();
  }
}, { passive: false });



// Draw Page
/////////////////////////////////

function uuid() {
  if (crypto?.randomUUID) {
    return crypto.randomUUID();
  }
  // RFC4122-ish fallback
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// --- Carousel wrapper ---
export default function ScheduleCarousel() {
  const [schedules, setSchedules] = useState(() => []);
  const [error, setError] = useState(null);
  const [config, setConfig] = useState(null);
  const [active, setActive] = useState(0);
  const [timersActive, setTimersActive] = useState(0);



  //
  function TimeStringToMinutes(hhmm) {
    // Validate input
    if (!/^\d{4}$/.test(hhmm)) {
      throw new Error("Invalid format, expected 'HHMM'");
    }

    const hours = parseInt(hhmm.slice(0, 2), 10);
    const minutes = parseInt(hhmm.slice(2, 4), 10);

    if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
      throw new Error("Invalid time");
    }

    return hours * 60 + minutes;
  }

  function MinutesToTimeString(minutes) {
  if (typeof minutes !== "number" || minutes < 0 || minutes >= 24 * 60) {
    throw new Error("Invalid minutes, must be between 0 and 1439");
  }

  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;

  // Pad with leading zeros to always get two digits
  const hh = String(hours).padStart(2, "0");
  const mm = String(mins).padStart(2, "0");

  return hh + mm;
}
  
  useEffect(() => {
    let cancelled = false;
    const isVite = !!import.meta.env;
    let URL="getconfig";
    // This is just for dev/test
    if (isVite) { URL="http://192.168.123.28/"+URL }
    const fetchConfig = async () => {
      try {
        const res = await fetch(URL); // your URL
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!cancelled) {
          setConfig(data);
          setError(null);
          let schedules=data.scheduler.schedule

          let mySchedule=[{id:"switch", type: "switch", amps: data.switch.amps, enabled:data.switch.on,scheduler_enabled:data.scheduler.enabled}]

          schedules.forEach((x,i) => {
            let obj={ 
              type:"scheduler",
              id:uuid(), 
              start:TimeStringToMinutes(x.start), 
              end:TimeStringToMinutes(x.end), 
              amps:x.amps,}
              mySchedule.push(obj)
          });
        
          setSchedules(mySchedule); // update state -> triggers re-render
          setTimersActive(data.scheduler.enabled); // update state -> triggers re-render
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
        console.log(err);
      }
    };

    // Initial fetch
    fetchConfig();

    // Poll every 1 second
    const intervalId = setInterval(fetchConfig, 30000);

    // Cleanup on unmount
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, []);

function debounce(func, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      func(...args);
    }, delay);
  };
}


  // Post changes
  const postSchedule = async (updatedSchedules) => {

    //console.log("postSchedule",updatedSchedules);

    let obj={}
    let schedulelist=[]

    updatedSchedules.forEach((x,i) => {
      if (x.id=="switch") {
        obj["switch:on"]=x.enabled;
        obj["switch:amps"]=x.amps;
        obj["scheduler:enabled"]=x.scheduler_enabled;
      } else {
          schedulelist.push({start:MinutesToTimeString(x.start),end:MinutesToTimeString(x.end),amps:x.amps})
      }
    })
    obj["scheduler:schedule"]=JSON.stringify(schedulelist);

  try {
    const isVite = !!import.meta.env;
    let URL="setsettings";
    // This is just for dev/test
    if (isVite) { URL="http://192.168.123.28/"+URL }

    const res = await fetch(URL, {
      method: "POST",
		  headers: {'Content-Type': 'application/json'},
      body: new URLSearchParams(obj),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    makeToastExt("Schedule Saved");
  } catch (err) {
    console.error("Failed to save schedule:", err);
    setError(err.message);
  }
};
  const debouncedPostSchedule = debounce(postSchedule, 1000); // 500ms delay

  // Functions
function makeToastExt(msg) {
  if (typeof makeToast==="function") {
    /* function is defined, so let's use it */
    makeToast(msg);
  } else {
    console.log("makeToast external function not defined");
    console.log(msg);
  }
}

const updateSchedule = (idx, next) => {
    setSchedules(prev => prev.map((s, i) => i === idx ? next : s));
};


const addSchedule = () => {
  setSchedules((prev) => {
    const updated = [
      ...prev,
      { id: uuid(), start: 8 * 60, end: 17 * 60, amps: 16,type:"scheduler" },
    ];
    setActive(updated.length - 1);
    debouncedPostSchedule(updated);
    return updated;
  });
};

const clamp = (n, min, max) => Math.min(max, Math.max(min, n));

const removeActive = () => {
  setSchedules((prev) => {
    if (prev.length === 0) return prev;
    const next = prev.filter((_, i) => i !== active);
    const nextIndex = clamp(active, 0, next.length - 1);
    setActive(nextIndex);
    debouncedPostSchedule(next);
    return next;
  });
};


  const go = (dir) => {
    setActive((a) => (a + dir + schedules.length) % schedules.length);
  };


  // Hint for more schedules
  const hasPrev = active > 0;
  const hasNext = active < schedules.length - 1;

  const renderCard = (status) => {
  switch (status) {
    case "loading":
      return <span className="loading">Loading…</span>;
    case "success":
      return <span className="success">Operation successful!</span>;
    case "error":
      return <span className="error">Something went wrong!</span>;
    default:
      return <span>Unknown status</span>;
  }
};

function StatusMessage({ status }) {
  return <div>{renderStatus(status)}</div>;
}

const visibleSchedules = schedules.filter(
  sch => !(sch.type === "scheduler" && !timersActive)
);

  return (
    <div className="min-h-screen w-full bg-[#1e242b] text-white flex items-center justify-center p-6">
      <div className="w-full max-w-5xl">


        <div className="relative">
          {/* Carousel rail */}
          <div className="flex gap-6 items-stretch transition-transform duration-500 ease-out"
               style={{ transform: `translateX(calc(50% - ${(active + 0.5) * 360}px))` }}>
            {visibleSchedules.map((sch, i) => (
            <div key={sch.id} 
                className={`shrink-0 w-[340px] sm:w-[380px] min-h-[462px] rounded-3xl bg-[#2b3139] ring-1 ring-white/10 p-5 backdrop-blur shadow-lg transition-all duration-500 ${i === active ? "scale-100 opacity-100" : "scale-95 opacity-60"}`}
            >
                {sch.type === "switch" ? (
                <ManualControl
                    schedule={sch}
                    onChange={(next) => updateSchedule(i, next)}
                    onCommit={() => debouncedPostSchedule(schedules)} // only POST on commit
                    setTimersActive={setTimersActive}
                />
                ) : sch.type === "scheduler" ? (
                  <ClockFace
                      schedule={sch}
                      onChange={(next) => updateSchedule(i, next)}
                      onCommit={() => debouncedPostSchedule(schedules)} // only POST on commit
                      snapStep={config.scheduler.scheduler_granularity}
                      timersActive={timersActive}
                  />
                ) : (
                  <h1>Invalid Type</h1>
                )}
              </div>
            ))}
          </div>

          {/* Prev/Next controls */}
          <div className="absolute inset-y-0 -left-3 flex items-center">
            <button
              onClick={() => go(-1)}
              className={`h-12 w-12 rounded-full grid place-items-center bg-white/10 hover:bg-white/20 transition ${hasPrev ? '' : 'opacity-40 pointer-events-none'}`}
              aria-label="Previous schedule"
            >
              ‹
            </button>
          </div>
          <div className="absolute inset-y-0 -right-3 flex items-center">
            <button
              onClick={() => go(1)}
              className={`h-12 w-12 rounded-full grid place-items-center bg-white/10 hover:bg-white/20 transition ${hasNext ? '' : 'opacity-40 pointer-events-none'}`}
              aria-label="Next schedule"
            >
              ›
            </button>
          </div>
        </div>

        {/* Dots */}
        <div className="mt-3 flex justify-center gap-2">
          {schedules.map((_, i) => (
            <button key={i} onClick={() => setActive(i)} className={`h-2.5 w-2.5 rounded-full ${i === active ? 'bg-white' : 'bg-white/30 hover:bg-white/50'}`} />
          ))}
        </div>

        {/* Add / Delete buttons */}
        <div className="mt-3 flex items-center justify-center gap-2">
          <button
            onClick={addSchedule}
            className="px-5 py-3 rounded-2xl bg-gradient-to-r from-blue-500 to-fuchsia-500 text-white font-semibold shadow-lg hover:opacity-95 active:scale-98"
          >
            + New Schedule
          </button>
{ schedules[active]?.type !== "switch" && (

            <button
            onClick={removeActive}
            className="px-5 py-3 rounded-2xl bg-white/10 text-white font-semibold shadow-lg hover:bg-white/20 disabled:opacity-40"
            disabled={
                schedules[active]?.type === "switch" || schedules.length === 0
            }
            >
            Delete
            </button>
)}

        </div>


        <div className="bottom-objects-flex">
          <StatusPanel></StatusPanel>
        </div>
    </div>
  </div>

    
  );
}

