import React, { useMemo, useRef, useState, useEffect } from "react";
import StatusPanel from "./openeo-StatusPanel";
import ManualControl from "./Carousel/openeo-ManualControl";
import ClockFace from "./Carousel/openeo-ClockFace";
import SolarTimer from "./Carousel/openeo-SolarTimer";
import EVChargerStatus from "./Carousel/openeo-Status";
import { useToastContext } from "./openeo-Toast";
import { buildUrl } from './utils/funcs';
import { uiCss,globalCss,styles } from './utils/styles';


// Define constants for Carousel types, to also allow correct sorting
const STATUS_TYPE=0;
const SWITCH_TYPE=1;
const TIMER_TYPE=2;
const SOLAR_TYPE=3;



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
  const addToast = useToastContext();

  const [schedules, setSchedules] = useState(() => []);
  const [error, setError] = useState(null);
  const [config, setConfig] = useState(null);
  const [active, setActive] = useState(0);
  const [timersActive, setTimersActive] = useState(0);
  const [solarActive, setSolarActive] = useState(0);
  const [snapStep, setSnapStep] = useState(0);
  const [status, setStatus] = useState(null);



  useEffect(() => {
    let cancelled = false;

    const fetchStatus = async () => {
      try {
        const res = await fetch(buildUrl("getstatus")); // your URL
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!cancelled) {
          setStatus(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    };

    // Initial fetch
    fetchStatus();

    let pollinterval=1000 // 1 second
    if (typeof(statusUpdateInterval)!='undefined') {
      pollinterval=statusUpdateInterval
    }
    console.log("Status Update interval",pollinterval);
    const intervalId = setInterval(fetchStatus, pollinterval);

    // Cleanup on unmount
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    const handleTouchMove = (e) => {
      if (Math.abs(e.touches[0].clientX) > 10) {
        e.preventDefault();
      }
    };

    document.addEventListener('touchmove', handleTouchMove, { passive: false });

    // Cleanup: runs when component unmounts (or before effect re-runs)
    return () => {
      document.removeEventListener('touchmove', handleTouchMove, { passive: false });
    };
  }, []); // Empty array = run once on mount, clean up on unmount


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
    const fetchConfig = async () => {
      try {
        const res = await fetch(buildUrl("getconfig")); // your URL
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!cancelled) {
          setConfig(data);
          setError(null);

          let mySchedule=[{id:"status",type: STATUS_TYPE},{id:"switch", type: SWITCH_TYPE, amps: data.switch.amps, enabled:data.switch.on,scheduler_enabled:data.scheduler.enabled}]
          let schedules=[];


          // Standard timers
          schedules=data.scheduler.schedule
          schedules.forEach((x,i) => {
            let obj={ 
              type:TIMER_TYPE,
              id:uuid(), 
              start:TimeStringToMinutes(x.start), 
              end:TimeStringToMinutes(x.end), 
              amps:x.amps,}
            mySchedule.push(obj)
          });

          if (data.loadmanagement.solar_enable) {

              // Solar control
            schedules=data.loadmanagement.schedule

            schedules.forEach((x,i) => {
              let obj={ 
                type:SOLAR_TYPE,
                id:uuid(), 
                start:TimeStringToMinutes(x.start), 
                end:TimeStringToMinutes(x.end), 
                amps:x.amps,}
              mySchedule.push(obj)
            });
          }
          
          setSchedules(mySchedule); // update state -> triggers re-render
          setTimersActive(data.scheduler.enabled); // update state -> triggers re-render
          setSolarActive(data.loadmanagement.solar_enable); // update state -> triggers re-render
          setSnapStep(data.scheduler.scheduler_granularity);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
        console.log(err);
      }
    };

    // Initial fetch
    fetchConfig();


    let pollinterval=30000 // 30 seconds
    if (typeof(configUpdateInterval)!='undefined') {
      pollinterval=configUpdateInterval
    }
    console.log("Config update interval",pollinterval);    
    const intervalId = setInterval(fetchConfig, pollinterval);

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
    let schedulelist_solar=[]

    updatedSchedules.forEach((x,i) => {
      console.log(x);
      if (x.type==STATUS_TYPE) {
        // do nothing
      } else  if (x.type==SWITCH_TYPE) {
        obj["switch:on"]=x.enabled;
        obj["switch:amps"]=x.amps;
        obj["scheduler:enabled"]=x.scheduler_enabled;
      } else if (x.type==SOLAR_TYPE) {
          schedulelist_solar.push({start:MinutesToTimeString(x.start),end:MinutesToTimeString(x.end),amps:x.amps})
      } else {
          schedulelist.push({start:MinutesToTimeString(x.start),end:MinutesToTimeString(x.end),amps:x.amps})
      }
    })
    obj["scheduler:schedule"]=JSON.stringify(schedulelist);
    obj["loadmanagement:schedule"]=JSON.stringify(schedulelist_solar);
    console.log(obj);
  try {

    const res = await fetch(buildUrl("setsettings"), {
      method: "POST",
		  headers: {'Content-Type': 'application/json'},
      body: new URLSearchParams(obj),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    addToast({ type: "success", title: "Success", message: "Schedule Saved" });

  } catch (err) {
    addToast({ type: "error", title: "Failure", message: "Save Error: "+err });

    console.error("Failed to save schedule:", err);
    setError(err.message);
  }
};
const debouncedPostSchedule = debounce(postSchedule, 1000); // 500ms delay


const updateSchedule = (idx, next) => {
    setSchedules(prev => prev.map((s, i) => i === idx ? next : s));
};


const addSchedule = () => {
  setSchedules((prev) => {
    const updated = [
      ...prev,
      { id: uuid(), start: 8 * 60, end: 17 * 60, amps: 16,type:TIMER_TYPE },
    ];
    setActive(updated.length - 1);
    debouncedPostSchedule(updated);
    return updated;
  });
};

const addSchedule_solar = () => {
  setSchedules((prev) => {
    const updated = [
      ...prev,
      { id: uuid(), start: 0 * 60, end: 23 * 60 + 59, amps: 0,type:SOLAR_TYPE },
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
  sch => !(sch.type === TIMER_TYPE && !timersActive)
);


{/* Carousel Calcs */}

const itemWidth = 340; // or 380 for sm
const gap = 24; // 6 * 4px (Tailwind spacing)
const offset = active * (itemWidth + gap);
const translateX = `calc(50% - ${offset + itemWidth/2}px)`;



  return (
    <>
    <style>{uiCss}</style>
    <div className="min-h-screen w-full bg-[#1e242b] text-white flex justify-center p-6 " id="mainDiv">

      <div className="w-full max-w-5xl">

          {/* Carousel rail */}
          <div className="flex items-center gap-6 items-stretch transition-transform duration-500 ease-out mt-[10vh]" id="carouselRail"
            style={{ transform: `translateX(${translateX})` }}
          >
                
            {visibleSchedules.map((sch, i) => (
            <div key={sch.id} 
                className={`flex items-center justify-center max-width shrink-0 w-[340px] sm:w-[380px] min-h-[442px] rounded-3xl bg-[#2b3139] ring-1 ring-white/10 p-5 backdrop-blur shadow-lg transition-all duration-500 ${i === active ? "scale-100 opacity-100" : "scale-90 brightness-60 cursor-pointer"}`}
                onClick={() => { if (i !== active) setActive(i); }}
            >
                {sch.type === STATUS_TYPE ? (
                  <EVChargerStatus
                    status={status}
                  />
                ) : sch.type === SWITCH_TYPE ? (
                <ManualControl
                    schedule={sch}
                    onChange={(next) => updateSchedule(i, next)}
                    onCommit={() => debouncedPostSchedule(schedules)} // only POST on commit
                    setTimersActive={setTimersActive}
                    active={i === active}
                />
                ) : sch.type === TIMER_TYPE ? (
                  <ClockFace
                      schedule={sch}
                      onChange={(next) => updateSchedule(i, next)}
                      onCommit={() => debouncedPostSchedule(schedules)} // only POST on commit
                      snapStep={snapStep}
                      timersActive={timersActive}
                      active={i === active}

                  />
                ) : sch.type === SOLAR_TYPE ? (
                  <SolarTimer
                      schedule={sch}
                      onChange={(next) => updateSchedule(i, next)}
                      onCommit={() => debouncedPostSchedule(schedules)} // only POST on commit
                      snapStep={snapStep}
                      timersActive={timersActive}
                      active={i === active}

                  />
                ) : (
                  <h1>Invalid Type</h1>
                )}
              </div>
            ))}
          </div>

          

          {/* Prev/Next controls */}
          <div className="absolute inset-y-0 -left-3 flex items-center">
{ timersActive && (

            <button
              onClick={() => go(-1)}
              className={`h-12 w-12 rounded-full grid place-items-center bg-white/10 hover:bg-white/20 transition ${hasPrev ? '' : 'opacity-40 pointer-events-none'}`}
              aria-label="Previous schedule"
            >
              ‹
            </button>
)}

          </div>
          <div className="absolute inset-y-0 -right-3 flex items-center">
{ timersActive && (

            <button
              onClick={() => go(1)}
              className={`h-12 w-12 rounded-full grid place-items-center bg-white/10 hover:bg-white/20 transition ${hasNext ? '' : 'opacity-40 pointer-events-none'}`}
              aria-label="Next schedule"
            >
              ›
            </button>
)}
        </div>

        {/* Dots */}
        <div className="mt-1 flex justify-center gap-2 h-auto">
          {timersActive && visibleSchedules.map((_, i) => (
            <button key={i} onClick={() => setActive(i)} className={`h-2.5 w-2.5 rounded-full ${i === active ? 'bg-white' : 'bg-white/30 hover:bg-white/50'}`} />
          ))}
        </div>

        {/* Add / Delete buttons */}

        <div className="mt-1 flex items-center justify-center gap-2 h-auto">


{ timersActive && (
          <button
            onClick={addSchedule}
            className="px-5 py-3 rounded-2xl bg-gradient-to-r from-blue-500 to-fuchsia-500 text-white font-semibold shadow-lg hover:opacity-95 active:scale-98"
          >
            + New Charge Timer
          </button>
)}

{ solarActive && (
          <button
            onClick={addSchedule_solar}
            className="px-5 py-3 rounded-2xl bg-gradient-to-r from-yellow-500 to-orange-500 text-black font-semibold shadow-lg hover:opacity-95 active:scale-98"
          >
            + New Solar Timer
          </button>
)}

{ schedules[active]?.type !== SWITCH_TYPE  && (

            <button
            onClick={removeActive}
            className="px-5 py-3 rounded-2xl bg-white/10 text-white font-semibold shadow-lg hover:bg-white/20 disabled:opacity-40"
            disabled={
                schedules[active]?.type === "switch" || schedules.length === 0
            }
            >
            Delete Timer
            </button>
)}
        </div>
      </div>

      <div className="statusPanelDiv">
        <StatusPanel status={status}></StatusPanel>
      </div>
  </div>
  </>

    
  );
}

