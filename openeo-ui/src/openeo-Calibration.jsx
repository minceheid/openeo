import React, { useEffect, useRef, useState,useCallback } from "react";
import { buildUrl } from './utils/funcs';
import { globalCss,styles } from './utils/styles';
import { useToastContext } from "./openeo-Toast";

const seriesMap = {
  eo_current_site: "Site",
  eo_current_vehicle: "Vehicle",
  eo_current_solar: "Solar",
};

const initialCalibrations = Object.fromEntries(
  Object.keys(seriesMap).map((k) => [k, { offset: 0, mult: 1 }])
);

export default function Calibration() {
  const addToast = useToastContext();

  const [calibrations, setCalibrations] = useState(initialCalibrations);
  const calibrationsRef = useRef(initialCalibrations);

  const [rawData, setRawData] = useState([]);

  const chartRef = useRef(null);   // DOM ref for the Plotly chart
  const timerRef = useRef(null);   // Ref to store the update timer
  const chartDataRef = useRef([]); // Ref to hold the current chart data for updates
  const plotlyRef = useRef(null);  // Ref to hold the Plotly library once loaded

  const url=`getchartdata?type=plotly&series=eo_current_raw_vehicle,eo_current_raw_site,eo_current_raw_solar`

  const layout = {
    margin: { l: 30, r: 0, b: 30, t: 0 },
      legend: {
        yanchor: "top",
        y: 0.99,
        xanchor: "left",
        x: 0.01,
      },
    xaxis: { title: "Time" },
    yaxis: { title: "Current (A)" },

    grid: { columns: 1, pattern: "independent" },
    showlegend: true,
    paper_bgcolor: "#282c34",
    plot_bgcolor: "#282c34",
    font: { color: "#eee" },
    y1: { rangemode: "tozero" },
  };


  // ---------------- Apply calibration to chart Data ----------------
  function applyCalibration(raw, cal) {
    return raw.map((v) => v * cal.mult + cal.offset);
  }

  function drawChart() {
    const plotly = plotlyRef.current;
    if (!plotly) return;
 
    const traces = chartDataRef.current.flatMap((trace) => {
      const realKey = trace.key.replace("_raw_", "_");
      const cal = calibrationsRef.current[realKey] || { offset: 0, mult: 1 };

      const xs = trace.x;
      const ys = applyCalibration(trace.y,cal);

      const baseTrace = {
        x: xs,
        y: ys,
        mode: "lines",
        name: seriesMap[realKey] || realKey,
      };

      //console.log("Processing trace", trace.key, "with calibration", cal);
      switch (trace.key) {
        case "eo_current_raw_vehicle":
          baseTrace.line = { color: "red", width: 3 };
          break;
        case "eo_current_raw_site":
          baseTrace.line = { color: "orange", width: 3 };
          break;
        case "eo_current_raw_solar":
          baseTrace.line = { color: "lime", width: 3 };
          break;
      }

      let labelTrace = null;
      if (xs.length > 0) {
        const lastX = xs[xs.length - 1];
        const lastY = ys[ys.length - 1];

        labelTrace = {
          x: [lastX],
          y: [lastY],
          mode: "markers+text",
          text: [lastY.toFixed(1)],
          textposition: "top right",
          marker: { size: 6 },
          showlegend: false,
          hoverinfo: "skip",
        };
      }

      return labelTrace ? [baseTrace, labelTrace] : [baseTrace];
    });
    
    window.Plotly.newPlot(chartRef.current, traces, layout, {  responsive: true});

  }

  // Streaming update
  function updateChart() {
    const plotly = plotlyRef.current;
    const chartData = chartDataRef.current;

    if (!plotly || !chartData.length) return;

    const maxTime = chartData[0].x_orig[chartData[0].x.length - 1];
    fetch(buildUrl(url + "&since=" + maxTime), { method: "GET" })
      .then((r) => r.json())
      .then((data) => {

        // Mutate X strings to Date objects for Plotly
        data.forEach(series => {
          series.x_orig = series.x; // keep original strings for maxTime calculation
          series.x = series.x.map(x => new Date(x));
        });
        data.forEach((series, i) => {

          let number_of_new_points = series.x.length;

          chartData[i].x_orig.push(...series.x_orig);
          chartData[i].x.push(...series.x);
          chartData[i].y.push(...series.y);

          for(let j=0;j<number_of_new_points;j++){
            chartData[i].x_orig.shift();
            chartData[i].x.shift();
            chartData[i].y.shift();
          }
        });

        chartDataRef.current = chartData;
        drawChart();
      })
      .catch((err) => console.log("Update error:", err));
  }


  useEffect(() => {
   
    // Dynamically load Plotly from CDN
    const script = document.createElement("script");
    script.src = "https://cdn.plot.ly/plotly-2.29.1.min.js";
    script.async = true;

    script.onload = () => {
      plotlyRef.current = window.Plotly;
    
      fetch(buildUrl("getconfig"))
        .then((r) => r.json())
        .then((config) => {
            const newCalibrations = {
              eo_current_site: {
                offset: config.loadmanagement.ct_offset_site,
                mult: config.loadmanagement.ct_calibration_site,
              },
              eo_current_vehicle: {
                offset: config.loadmanagement.ct_offset_vehicle,
                mult: config.loadmanagement.ct_calibration_vehicle,
              },
              eo_current_solar: {
                offset: config.loadmanagement.ct_offset_solar,
                mult: config.loadmanagement.ct_calibration_solar,
              },
            };
            calibrationsRef.current = newCalibrations;
            setCalibrations(newCalibrations);

            // Now get initial data
            fetch(buildUrl(url), { method: "GET" })
              .then((r) => r.json())
              .then((data) => {
                let trimmedData = data.map(trace => ({
                  ...trace,
                  x: trace.x.slice(-160),
                  y: trace.y.slice(-160),
                }));
                // Mutate X strings to Date objects for Plotly
                trimmedData.forEach(series => {
                  series.x_orig = series.x;
                  series.x = series.x.map(x => new Date(x));
                });
                chartDataRef.current = trimmedData;
                drawChart();
                timerRef.current = setInterval(updateChart, 5000);
                
              })
            .catch((err) => {
              console.log("Initial fetch error:", err);
              addToast({type: "error", title: "Data Fetch", message: "An error occurred while fetching chart data: " + err.message});
            });
        })
        .catch((err) => {
          console.log("Config fetch error:", err);
          addToast({type: "error", title: "Config Fetch", message: "An error occurred while fetching config: " + err.message});
        });
    };

    document.body.appendChild(script);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      document.body.removeChild(script);
    };
  }, []);


  const doReset = () => {
    calibrationsRef.current = initialCalibrations;
    setCalibrations(initialCalibrations);
    doSubmit(initialCalibrations);
  };

  const doSubmit = async (cal = calibrations) => {

    const params = {
      "loadmanagement:ct_offset_site": calibrations.eo_current_site.offset,
      "loadmanagement:ct_calibration_site": calibrations.eo_current_site.mult,
      "loadmanagement:ct_offset_vehicle": calibrations.eo_current_vehicle.offset,
      "loadmanagement:ct_calibration_vehicle": calibrations.eo_current_vehicle.mult,
      "loadmanagement:ct_offset_solar": calibrations.eo_current_solar.offset,
      "loadmanagement:ct_calibration_solar": calibrations.eo_current_solar.mult,
    };

    try {
      const res = await fetch(buildUrl("setsettings"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: new URLSearchParams(params),
      });

      if (!res.ok) throw new Error("Server error");

      addToast({ type: "success", title: "Update", message: "Update has started" });
    } catch (err) {
      console.error(err);
      addToast({type: "error", title: "Saving", message: "An error occurred (HTTP "+err.message+") - settings may have not been saved"});
    }
  };


  // ---------------- Handlers ----------------
  const updateCalibration = (key, field, value) => {
    const updated = {
      ...calibrationsRef.current,
      [key]: { ...calibrationsRef.current[key], [field]: parseFloat(value) },
    };
    calibrationsRef.current = updated;
    setCalibrations(updated);
    drawChart();
  };

  // ---------------- Render ----------------
  return (
    <div style={styles.page}>
      <style>{globalCss}</style>
      <div style={styles.pageTitle}>// CT Calibration</div>
      <div style={{ display: 'flex', flexDirection: 'row', gap: '16px', width: '100%' }}>
      {Object.entries(seriesMap).map(([key, label]) => (
        <div style={styles.section} key={label} >
          <div style={styles.sectionHeader}>{label}</div>
            <label>Offset:</label>
            <SliderInput 
              field={{
                range: [-2,2],
                step:0.01
              }}
              value={calibrations[key].offset} 
              onChange={(name, val) => updateCalibration(key,"offset",val)} />
            <label>Scaling:</label>
            <SliderInput 
              field={{
                range: [0.5,2],
                step:0.01
              }}
              value={calibrations[key].mult} 
              onChange={(name, val) => updateCalibration(key,"mult",val)} />
        </div>
      ))}
      </div>

      <div style={styles.section}>
        <div style={styles.sectionHeader}>Real Time Data</div>
        <div ref={chartRef} style={{ marginTop: "20px" }} />
      </div>

      {/* Toolbar */}
      <div style={styles.buttonRow} >
        <button style={styles.Btn} 
          onClick={doSubmit}
          onMouseEnter={(e) => {
            e.target.style.background = "#254870";
            e.target.style.borderColor = "#7ab8f0";
          }}
          onMouseLeave={(e) => {
            e.target.style.background = "#1e3a5f";
            e.target.style.borderColor = "#4a7ab8";
          }}
        >
          Save Settings
        </button>
        <button style={styles.Btn} 
          onClick={doReset}
          onMouseEnter={(e) => {
            e.target.style.background = "#254870";
            e.target.style.borderColor = "#7ab8f0";
          }}
          onMouseLeave={(e) => {
            e.target.style.background = "#1e3a5f";
            e.target.style.borderColor = "#4a7ab8";
          }}
        >
          Reset Settings
        </button>
      </div>

    </div>

  );
}


function SliderInput({ field, value, onChange }) {
  const min = field.range?.[0] ?? 0;
  const max = field.range?.[1] ?? 100;
  const step = field.step ?? 1;
  const trackRef = useRef(null);
 
  const calcValueFromTouch = useCallback((touch) => {
    const rect = trackRef.current.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (touch.clientX - rect.left) / rect.width));
    const raw = min + ratio * (max - min);
    const stepped = Math.round(raw / step) * step;
    return Math.max(min, Math.min(max, stepped));
  }, [min, max, step]);
 
  const handleTouchMove = useCallback((e) => {
    onChange(field.name, calcValueFromTouch(e.touches[0]));
  }, [field.name, onChange, calcValueFromTouch]);
 
  const handleTouchStart = useCallback((e) => {
    onChange(field.name, calcValueFromTouch(e.touches[0]));
  }, [field.name, onChange, calcValueFromTouch]);
 
  // Must attach touchmove as non-passive so preventDefault works on iOS
  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    el.addEventListener("touchmove", handleTouchMove, { passive: false });
    return () => el.removeEventListener("touchmove", handleTouchMove);
  }, [handleTouchMove]);
 
  return (
    <div style={styles.sliderWrap}>
      <span style={styles.sliderValue}>
        {value}
        {field.value_unit ? ` ${field.value_unit}` : ""}
      </span>
      <input
        ref={trackRef}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(field.name, Number(e.target.value))}
        onTouchStart={handleTouchStart}
        style={styles.rangeInput}
      />
    </div>
  );
}