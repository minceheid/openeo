import React, { useEffect, useRef } from "react";
import { buildUrl,getCurrencyConfig } from './utils/funcs';
import { globalCss,styles } from './utils/styles';

// ── Currency detection ─────────────────────────────────────────────────────

const CURRENCY = getCurrencyConfig();

function formatCurrency(amount) {
  return new Intl.NumberFormat(CURRENCY.locale, {
    style: "currency",
    currency: CURRENCY.currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount ?? 0);
}

// ──────────────────────────────────────────────────────────────────

export default function StatisticsSession() {
  const chartRef = useRef(null);
  const timerRef = useRef(null);
  const chartDataRef = useRef([]);
  const plotlyRef = useRef(null);

  const url='getchartdata?type=plotly&series=eo_session_current_tariff:eo_session_current_tariff,eo_session_kwh:,eo_session_cost:';

  const layout = {
    grid: { rows: 3, columns: 1, pattern: "independent" },
    showlegend: true,
    margin: { t: 30 },
    paper_bgcolor: "#282c34",
    plot_bgcolor: "#282c34",
    font: { color: "#eee" },
    yaxis1: { rangemode: "tozero" },
    yaxis2: { rangemode: "tozero" },
    yaxis3: { rangemode: "tozero" },
    yaxis4: { rangemode: "tozero" },
    xaxis1: {},
    xaxis2: { matches: "x" },
    xaxis3: { matches: "x" },
    xaxis4: { matches: "x" },
  };

  const legends = ["legend1", "legend2","legend3"];
  legends.forEach((x, i) => {
    layout[x] = {
      y: (legends.length - i) * (1 / legends.length) - 0.03,
      yanchor: "top",
    };
  });

  // Map Plotly styling
  function processData(data) {
    data.forEach((item) => {
      // Swap any £ in the legend title for the detected currency symbol
      if (item.name && item.name.includes("£")) {
        item.name = item.name.split("£").join(CURRENCY.symbol);
      }

      switch (item.key) {
        case "eo_session_current_tariff":
          item.line = { color: "green", dash: "none", width: 4 };
          item.line.shape="hv";

          // generate inline labels for the current tariff series
          var text = [];
          var lastValue = -1;
          for (var i = 0; i < item.x.length; i++) {
            if (item.y[i] !== lastValue) {
              text.push(formatCurrency(item.y[i]));
              lastValue = item.y[i];
            } else {
              text.push("");
            }
          }  
          item.mode = "lines+text";
          item.textposition = "bottom right";
          item.text = text;
          break;
        case "eo_session_kwh":
          item.line = { color: "red", dash: "none", width: 4 };
          item.line.shape="hv";
          break;
        case "eo_session_cost":
          item.line = { color: "blue", dash: "none", width: 4 };
          item.line.shape="hv";
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
    <div style={styles.pageTitle}>// Session Stats</div>
      <div ref={chartRef} style={{ marginTop: "20px" ,height:"calc(100vh - 120px) "}} />
    </div>
  );
}