import React, { useEffect, useRef } from "react";
import { buildUrl } from './utils/funcs';
import { globalCss,styles } from './utils/styles';

export default function StatisticsOS() {
  const chartRef = useRef(null);
  const timerRef = useRef(null);
  const chartDataRef = useRef([]);
  const plotlyRef = useRef(null);

  const url='getchartdata?type=plotly&series=sys_cpu_temperature:sys_wifi_strength,sys_1m_load_average,sys_free_memory:sys_available_memory,eo_serial_errors';

  const layout = {
    grid: { rows: 4, columns: 1, pattern: "independent" },
    showlegend: true,
    margin: { t: 30 },
    paper_bgcolor: "#282c34",
    plot_bgcolor: "#282c34",
    font: { color: "#eee" },
    y1: { rangemode: "tozero" },
    y2: { rangemode: "tozero" },
    y3: { rangemode: "tozero" },
    y4: { rangemode: "tozero" },
  };

  const legends = ["legend1", "legend2", "legend3","legend4"];
  legends.forEach((x, i) => {
    layout[x] = {
      y: (legends.length - i) * (1 / legends.length) - 0.03,
      yanchor: "top",
    };
  });

  // Map Plotly styling
  function processData(data) {
    data.forEach((item) => {
      switch (item.key) {
        case "eo_power_requested":
        case "eo_amps_requested":
          item.line = { color: "orange", dash: "dot", width: 4 };
          break;
        case "eo_power_delivered":
        case "eo_amps_delivered":
          item.line = { color: "red", width: 4 };
          break;
        case "eo_power_requested_grid":
        case "eo_amps_requested_grid":
          item.fillcolor = "lightblue";
          item.line = { color: "black", width: 0.25 };
          item.stackgroup = "power_areastack";
          delete item.mode;
          delete item.type;
          break;
        case "eo_power_requested_solar":
        case "eo_amps_requested_solar":
          item.fillcolor = "lightgreen";
          item.line = { color: "black", width: 0.25 };
          item.stackgroup = "power_areastack";
          delete item.mode;
          delete item.type;
          break;
        case "eo_power_requested_site_limit":
        case "eo_amps_requested_site_limit":
          item.fillcolor = "darkgrey";
          item.line = { color: "black", width: 0.25 };
          item.stackgroup = "power_areastack";
          delete item.mode;
          delete item.type;
          break;
        case "eo_current_vehicle":
          item.line = { color: "red", width: 2 };
          break;
        case "eo_current_site":
          item.line = { color: "orange", width: 2 };
          break;
        case "eo_current_solar":
          item.line = { color: "lime", width: 2 };
          break;
      }
    });
  }

  // Streaming update
  function updateChart() {
    const plotly = plotlyRef.current;
    const chartData = chartDataRef.current;
    if (!plotly || !chartData.length) return;

    const maxTime = chartData[0].x[chartData[0].x.length - 1];
    fetch(buildUrl(url + "&since=" + maxTime), { method: "GET" })
      .then((r) => r.json())
      .then((data) => {
        data.forEach((series, i) => {
          chartData[i].x.push(...series.x);
          chartData[i].y.push(...series.y);
        });

        const update = {
          x: data.map((s) => s.x),
          y: data.map((s) => s.y),
        };

        plotly.extendTraces(
          chartRef.current,
          update,
          data.map((_, i) => i),
          2000 // keep last 2000 points
        );
      })
      .catch((err) => console.log("Update error:", err));
  }

  useEffect(() => {
    // Dynamically load Plotly from CDN
    const script = document.createElement("script");
    script.src = "https://cdn.plot.ly/plotly-2.29.1.min.js"; // latest 2.x version
    script.async = true;

    script.onload = () => {
      plotlyRef.current = window.Plotly; // Plotly is global

      fetch(buildUrl(url), { method: "GET" })
        .then((r) => r.json())
        .then((data) => {
          processData(data);
          chartDataRef.current = data;

          window.Plotly.newPlot(chartRef.current, data, layout, {
            responsive: true,
          });

          timerRef.current = setInterval(updateChart, 30000);
        })
        .catch((err) => console.log("Initial fetch error:", err));
    };

    document.body.appendChild(script);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      document.body.removeChild(script);
    };
  }, []);

  return (
    <div style={styles.page}>
    <style>{globalCss}</style>
    <div style={styles.pageTitle}>// Charger Stats</div>
      <div ref={chartRef} style={{ marginTop: "20px" }} />
    </div>
  );
}
