    // --- Series mapping (API name -> friendly name) ---
    const seriesMap = {
      "eo_current_site":    "Site",
      "eo_current_vehicle": "Vehicle",
      "eo_current_solar":   "Solar"
    };

    // --- Calibration settings ---
    const calibrations = {};
    Object.keys(seriesMap).forEach(k => {
      calibrations[k] = {offset: 0, mult: 1};
    });

    async function build_slider_ui() {
      const url = "/getconfig";
      const res = await fetch(url);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const configdata = await res.json();

      calibrations["eo_current_site"].offset=configdata["loadmanagement"].ct_offset_site;
      calibrations["eo_current_site"].mult=configdata["loadmanagement"].ct_calibration_site;
      calibrations["eo_current_vehicle"].offset=configdata["loadmanagement"].ct_offset_vehicle;
      calibrations["eo_current_vehicle"].mult=configdata["loadmanagement"].ct_calibration_vehicle;
      calibrations["eo_current_solar"].offset=configdata["loadmanagement"].ct_offset_solar;
      calibrations["eo_current_solar"].mult=configdata["loadmanagement"].ct_calibration_solar;

      // --- Build slider UI ---
      const controlContainer = document.getElementById("controls");
      Object.entries(seriesMap).forEach(([key, label]) => {
        const group = document.createElement("div");
        group.className = "control-group";
        group.innerHTML = `
          <h3>${label}</h3>
          <label>Offset: <span id="${key}-offset-val">`+calibrations[key].offset+`</span></label>
          <input type="range" id="${key}-offset" min="-2" max="2" step="0.01" value="`+calibrations[key].offset+`">
          <label>Scaling: <span id="${key}-mult-val">`+calibrations[key].mult+`</span></label>
          <input type="range" id="${key}-mult" min="0.8" max="1.2" step="0.01" value="`+calibrations[key].mult+`">
        `;
        controlContainer.appendChild(group);

        document.getElementById(`${key}-offset`).addEventListener("input", e => {
          calibrations[key].offset = parseFloat(e.target.value);
          document.getElementById(`${key}-offset-val`).textContent = e.target.value;
          updateChart(); // reapply calibration instantly
        });
        document.getElementById(`${key}-mult`).addEventListener("input", e => {
          calibrations[key].mult = parseFloat(e.target.value);
          document.getElementById(`${key}-mult-val`).textContent = e.target.value;
          updateChart(); // reapply calibration instantly
        });
      });
    }

    // --- Helpers ---
    function applyCalibration(raw, cal) {
      return raw.map(v => v * cal.mult + cal.offset);
    }

    let rawData = []; // cached API result

    async function fetchData() {
      try {
        if (rawData.length==0) {
          maxtime=""
        } else {
          maxtime="since="+rawData[0].x[(rawData[0].x.length)-1]+"&";
        }
        const url = "/getchartdata?type=plotly&"+maxtime+"series=eo_current_vehicle,eo_current_site,eo_current_solar";
        const res = await fetch(url);
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();
        
        data.forEach(function (item, index) {
          switch (item.key) {
            case 'eo_current_vehicle':
              item.line={color:'red',width:3};
              break;
            case 'eo_current_site':
              item.line={color:'orange',width:3};
              break;            
            case 'eo_current_solar':
              item.line={color:'lime',width:3};
              break;
          }
        })
        if (rawData.length==0) {
          rawData = data;
        } else {  
          data.forEach(function(series,index) {
            rawData[index].x=rawData[index].x.concat(data[index].x);
            rawData[index].y=rawData[index].y.concat(data[index].y);
          });
        }

        updateChart();
      } catch (err) {
        console.error("Fetch failed:", err);
      }
    }

function updateIndicators() {
    document.getElementById(`${key}-offset`).addEventListener("input", e => {
        calibrations[key].offset = parseFloat(e.target.value);
    });
    document.getElementById(`${key}-mult`).addEventListener("input", e => {
        calibrations[key].mult = parseFloat(e.target.value);

    });
}

function updateChart() {
  if (!rawData || rawData.length === 0) return;

  const timeThreshold = Date.now() - 15 * 60 * 1000; // 15 Minutes

  const calibrated = rawData.flatMap(trace => {
    const cal = calibrations[trace.key] || { offset: 0, mult: 1 };

    // Filter points to last hour
    const filtered = trace.x.map((t, i) => {
      const ts = new Date(t).getTime();
      return { x: ts, y: trace.y[i] };
    }).filter(p => p.x >= timeThreshold);

    const xs = filtered.map(p => new Date(p.x));
    const ys = applyCalibration(filtered.map(p => p.y), cal);

    const baseTrace = {
      ...trace,
      x: xs,
      y: ys,
      mode: "lines",
      name: seriesMap[trace.name] || trace.name
    };

    // Last point label trace
    let labelTrace = {};
    if (xs.length > 0) {
      const lastX = xs[xs.length - 1];
      const lastY = ys[ys.length - 1];
      labelTrace = {
        x: [lastX],
        y: [lastY],
        mode: "markers+text",
        text: [lastY.toFixed(1)],     // show value with 1 decimal place
        textposition: "top right",
        marker: { size: 6 },
        showlegend: false,
        hoverinfo: "skip",
        name: (seriesMap[trace.name] || trace.name) + " label"
      };
    }

    return [baseTrace, labelTrace];
  });

  layout={
margin: {l: 30, r: 0, b: 30, t: 0, pad: 0 },
    paper_bgcolor: "#282c34",
    plot_bgcolor: "#282c34",
    font: { color: "#eee" },
    xaxis: { title: "Time" },
    yaxis: { title: "Current (A)" },
    legend:{
      yanchor:"top",
      y:0.99,
      xanchor:"left",
      x:0.01}};

  Plotly.newPlot("chart", calibrated, layout);
}

function doReset() {
    Object.keys(seriesMap).forEach(k => {
      calibrations[k] = {offset: 0, mult: 1};
        document.getElementById(`${k}-offset-val`).textContent = calibrations[k].offset;
        document.getElementById(`${k}-mult-val`).textContent = calibrations[k].mult;
    });
    doSubmit();
    updateChart();
}


function doSubmit() {
  	fetch('/setconfig', {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({ 
            loadmanagement: { 
                ct_offset_site: calibrations["eo_current_site"].offset,
                ct_calibration_site: calibrations["eo_current_site"].mult,
                ct_offset_vehicle: calibrations["eo_current_vehicle"].offset,
                ct_calibration_vehicle: calibrations["eo_current_vehicle"].mult,
                ct_offset_solar: calibrations["eo_current_solar"].offset,
                ct_calibration_solar: calibrations["eo_current_solar"].mult
            }}),
	    })
	.then((response) => {
       if(response.ok) {
            makeToast('Saved calibrations');
    } else {
        throw new Error('Server response wasn\'t OK');
    }})
	.catch(error => {
        console.log(error);
		makeToastError('Unable to save state: no response from charger');
	});
}

    const modeSwitchContainer = document.getElementById("modeSwitchContainer");

    modeSwitchContainer.style.display = 'none';
    modeSwitchContainer.style.visibility = 'hidden';
    // --- Initial + refresh every 5s ---
    build_slider_ui();
    fetchData();
    setInterval(fetchData, 5000);