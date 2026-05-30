import { useState, useEffect, useRef } from "react";
import { buildUrl } from './utils/funcs';
import { globalCss,styles } from './utils/styles';
import { useToastContext } from "./openeo-Toast";

export default function Update({ status = {} }) {
  const addToast = useToastContext();

  const [log, setLog] = useState("");
  const [running, setRunning] = useState(false);
  const [versionInfo, setVersionInfo] = useState(null);
  const timerRef = useRef(null);
  const outputRef = useRef(null);

  const fetchVersionInfo = () => {
    fetch(buildUrl("getstatus"))
      .then((r) => r.json())
      .then((data) => {
        setVersionInfo({
          current: data["app_version"] ?? "Unknown",
          latest: data["openeo_latest_version"] ?? null,
          lastCheck: data["openeo_last_version_check"] ?? null,
        });
      })
      .catch((err) => console.log("Error fetching version info:", err));
  };

  const refreshStatus = () => {
    fetch(buildUrl("update"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "status" }),
      signal: AbortSignal.timeout(850),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data["openeo_upgrade_running"] === true) {
          if (!timerRef.current) {
            timerRef.current = setInterval(refreshStatus, 1000);
          }
          setRunning(true);
        } else if (data["openeo_upgrade_running"] === false) {
          clearInterval(timerRef.current);
          timerRef.current = null;
          setRunning(false);
        }
        setLog(data["openeo_upgrade_log"] ?? "");
      })
      .catch((err) => console.log("Error fetching status:", err));
  };

  const beginUpdate = (actionType) => {
    if (
      actionType === "raspberrypi" &&
      !confirm("This action can take a long time (30mins+). Are you sure?")
    ) {
      console.log("aborting action");
      return;
    }

    if (actionType === "reboot") {
      window.location.href = "/";
    }

    fetch(buildUrl("update"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: actionType }),
    })
      .then((r) => r.json())
      .then((data) => {
        console.log(data);
        addToast({ type: "success", title: "Update", message: "Update has started" });
        refreshStatus();
      });
  };

  useEffect(() => {
    fetchVersionInfo();
    refreshStatus();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [log]);

  const versionPanelStyle = {
    display: "inline-block",  // ← add this

    //position: "fixed",
    //top: "12px",
    //left: "12px",
    background: "#0d1f33",
    border: "1px solid #2a4a6e",
    borderRadius: "6px",
    padding: "8px 12px",
    fontSize: "11px",
    color: "#7ab8f0",
    lineHeight: "1.7",
    zIndex: 1000,
    //minWidth: "180px",
  };

  const versionLabelStyle = {
    color: "#4a7ab8",
    marginRight: "6px",
  };

  const versionValueStyle = {
    color: "#c8dff5",
    fontFamily: "monospace",
  };

  const outdatedStyle = {
    color: "#f0a07a",
    fontFamily: "monospace",
  };

  const isOutdated =
    versionInfo?.latest &&
    versionInfo?.current &&
    versionInfo.current !== versionInfo.latest;

  return (
    <div style={styles.page}>
      <style>{globalCss}</style>
      <div style={styles.pageTitle}>// Update OpenEO</div>

<div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>

      {/* Version Info Panel */}
      {versionInfo && (
        <div style={versionPanelStyle}>
          <div>
            <span style={versionLabelStyle}>Current:</span>
            <span style={versionValueStyle}>{versionInfo.current}</span>
          </div>
          <div>
            <span style={versionLabelStyle}>Latest:</span>
            {versionInfo.latest ? (
              <span style={isOutdated ? outdatedStyle : versionValueStyle}>
                {versionInfo.latest}
              </span>
            ) : (
              <span style={{ color: "#666", fontStyle: "italic" }}>not checked</span>
            )}
          </div>
          <div>
            <span style={versionLabelStyle}>Checked:</span>
            <span style={{ color: "#556b7a", fontFamily: "monospace" }}>
              {versionInfo.lastCheck ?? "—"}
            </span>
          </div>
        </div>
      )}


      {/* Toolbar */}
  <div style={{ ...styles.buttonRow, flex: 1, justifyContent: "flex-end" }}>
        <button style={styles.Btn}
          onClick={() => beginUpdate("openeo")}
          onMouseEnter={(e) => {
            e.target.style.background = "#254870";
            e.target.style.borderColor = "#7ab8f0";
          }}
          onMouseLeave={(e) => {
            e.target.style.background = "#1e3a5f";
            e.target.style.borderColor = "#4a7ab8";
          }}
        >
          Update OpenEO
        </button>
        <button style={styles.Btn}
          onClick={() => beginUpdate("raspberrypi")}
          onMouseEnter={(e) => {
            e.target.style.background = "#254870";
            e.target.style.borderColor = "#7ab8f0";
          }}
          onMouseLeave={(e) => {
            e.target.style.background = "#1e3a5f";
            e.target.style.borderColor = "#4a7ab8";
          }}
        >
          Update Raspberry Pi
        </button>
        <button style={styles.Btn}
          onClick={() => beginUpdate("reboot")}
          onMouseEnter={(e) => {
            e.target.style.background = "#254870";
            e.target.style.borderColor = "#7ab8f0";
          }}
          onMouseLeave={(e) => {
            e.target.style.background = "#1e3a5f";
            e.target.style.borderColor = "#4a7ab8";
          }}
        >
          Reboot
        </button>
      </div>
</div>
      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          <span className={`update-status-dot ${running ? "active" : ""}`} />
          {running ? "Update in progress…" : "Idle"}
        </div>
        <textarea
          ref={outputRef}
          className="update-log"
          readOnly
          value={log}
          style={{ height: '75vh', width: '100%', boxSizing: 'border-box' }}
        />
      </div>
    </div>
  );
}