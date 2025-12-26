import React, { useMemo, useRef, useState, useEffect } from "react";


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
    
    if (state == 'idle') {
      state = "Idle"; 
    } else if (state == 'plug-present') {
      state = "Waiting for Connection";
    } else if (state == 'car-connected') {
      state = "Waiting for Vehicle";
    } else if (state == 'mains-fault') {
      state = "Error";
    } else if (state == 'charging' && status.eo_amps_requested > 0) {
      state = "Charging";
    } else if (state == 'charging' || state == 'charge-complete' || state == 'charge-suspended' || state== 'charge-paused') {
      // If car is still charging, show 'Pausing'
      if (status.eo_current_vehicle > 3) {
        state = "Pausing (Waiting for Vehicle)";
      } else {
          state = "Paused";
      }
    } else {
      state = "Unknown";
    }
    return state;
  }



  useEffect(() => {
    let cancelled = false;

    const fetchStatus = async () => {
      try {
        const res = await fetch("http://192.168.123.28/getstatus"); // your URL
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

    // Poll every 1 second
    const intervalId = setInterval(fetchStatus, 1000);

    // Cleanup on unmount
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, []);

  return (
    <div>
      {error && <p style={{ color: "red" }}>Error: {error}</p>}

      {!status ? ( <p>Loading…</p> ) : (
      <div>
      <div className="status-info" id="statusInfo">
          
          {
          !status.eo_connected_to_controller ? (
            <span className="status-item" id="statusWhatDoing">Waiting..</span>
           ) : (
            <span
              className={`status-item ${FriendlyState(status) === "charging" ? "status-charging" : "status-other"}`}
              id="statusWhatDoing"
            >         
            {FriendlyState(status)}</span>
           )
        }
        <span className="status-break"></span> 
        <span className="status-item" id="statusChargeCurrent">{Math.round(status.eo_current_vehicle, 0) + "/" + Math.round(status.eo_amps_requested, 0) + "A"}</span>
        <span className="status-break"></span>
        <span className="status-item" id="statusChargeVolt">{Math.round(status.eo_live_voltage, 0) + "V"}</span>
        <span className="status-break"></span>
        <span className="status-item" id="statusChargePower">{Number(status.eo_power_delivered).toFixed(2) + "kW"}</span>
        <span className="status-break"></span>
        <span className="status-item" id="statusChargeSession">{Number(status.eo_session_kwh).toFixed(2) + "kWh"}</span>
        <span className="status-break"></span>
        <span className="status-item" id="statusLocaltime">{status.eo_localtime}</span>
      </div>
      <div id="version-info" className="version-info">
          {status.app_version==status.openeo_latest_version ? (
            <span id="statusVersion">openeo {status.app_version}</span>
          ) : (
            <span id="statusVersion" style={{color: "red"}} onClick={() => (window.location.href="update.html")}>openeo {status.app_version} (Update Available)</span>
          )}
      </div>
      </div>
    )}
  </div>
  );
}