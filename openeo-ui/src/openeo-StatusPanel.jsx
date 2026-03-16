import React, { useMemo, useRef, useState, useEffect } from "react";
import { Sun, CloudSun } from "lucide-react";

export default function StatusPanel() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);


  function FriendlyState(status) {
    let state=status.eo_charger_state;
    /* Convert the state into a user-friendly message, that summarises roughly
    what is going on. */
    if (state == 'car-connected') {
      if (status.eo_amps_requested == 0) {
        state = 'charge-suspended';
      }
    } else if (state == 'charge-complete') {
      /* The EO controller reports the charge is complete after any session is 
      stopped by the vehicle, but realistically this is wrong.  We have no idea 
      why the car stopped charging.  Correct this to 'car-connected' if we are
      requesting current and 'charge-suspended' if we aren't.  If we are requesting
      current then the EVSE is ready to charge, but the car -isn't- for whatever 
      reason.   Could be a full battery, could be a schedule, could be a fault, 
      could be Octopii interference;  we have no idea, and neither does EO! */
      if (status.eo_amps_requested > 0) {
        state = 'car-connected';
      } else {
        state = 'charge-suspended';
      }
    }
    
    if (state == 'idle' || state == 'plug-present' ) {
      state = "Idle"; 
    } else if (state == 'car-connected') {
      state = "Connected";
    } else if (state == 'mains-fault') {
      state = "Error";
    } else if (state == 'charging' && status.eo_amps_requested > 0) {
      state = "Charging";
    } else if (state == 'charging' || state == 'charge-complete' || state == 'charge-suspended' || state== 'charge-paused') {
      state = "Paused";
    } else {
      state = "Unknown";
    }
    return state;
  }

  useEffect(() => {
    let cancelled = false;
    const isVite = !!import.meta.env.DEV;
    let URL="getstatus";
    // This is just for dev/test
    if (isVite) { URL="http://192.168.123.50/"+URL }
    const fetchStatus = async () => {
      try {
        const res = await fetch(URL); // your URL
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

  //console.log("blah",status.eo_solar_charge_current);
  return (
    <>
      {error && <p style={{ color: "red" }}>Error: {error}</p>}

      {!status ? ( <p>Loading…</p> ) : (

      <>
        <div className="status-info">
          {!status.eo_connected_to_controller ? (
            <span className="status-item">Waiting..</span>
          ) : (
            <span
              className={`status-item flex items-center gap-1 ${
                FriendlyState(status) === "Charging" ? "status-charging" : "status-other"
              }`}
            >
              {FriendlyState(status)}
              {status.eo_solar_active}
              <div className="relative group inline-block">
              {status.eo_solar_active == true && status.eo_solar_charge_current > 0 && (<Sun size={18} className="text-yellow-400 cursor-help" />)}
                <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 
                   w-max max-w-xs bg-gray-800 text-white text-xs rounded px-2 py-1
                   opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                Solar charging active
                </span>
              </div>

              <div className="relative group inline-block">
              {status.eo_solar_active == true && status.eo_solar_charge_current == 0 && (<CloudSun size={18} className="text-yellow-500 cursor-help" />)}
                <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 
                   w-max max-w-xs bg-gray-800 text-white text-xs rounded px-2 py-1
                   opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                Solar Charging enabled, but generated output not sufficient - check charging statistics page.
                </span>
              </div>
            </span>
          )}

          <span className="status-item">{Math.round(status.eo_current_vehicle)}/{Math.round(status.eo_amps_requested)}A</span>
          <span className="status-item">{Math.round(status.eo_live_voltage)}V</span>
          <span className="status-item">{Number(status.eo_power_delivered).toFixed(2)}kW</span>
          <span className="status-item">{Number(status.eo_session_kwh).toFixed(2)}kWh</span>
          <span className="status-item">{status.eo_localtime}</span>
        </div>
        <div id="version-info" className="version-info">
          {status.openeo_latest_version === undefined || status.app_version === status.openeo_latest_version ? (
            <span id="statusVersion">openeo {status.app_version}</span>
          ) : (
            <span id="statusVersion" style={{color: "red"}} onClick={() => (window.location.href="update.html")}>openeo {status.app_version} (Update Available)</span>
          )}
        </div>
      </>
    )}
  </>
  );
}