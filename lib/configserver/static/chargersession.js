
url='/getsessiondata';
data=[]

fetch(url, {method: 'GET'})
    .then(function(response) { return response.json(); })
    .then(function(sessiondata) {

        daily_joules=0;
        weekly_joules=0;
        monthly_joules=0;

        now=new Date()/1000;

        // Calculate kWh from Joules
        sessiondata.forEach((x) => {
            x.kwh=Math.round(x.joules / 360000)/10+" kWh";
            x.duration=Math.round((x.last_timestamp-x.first_timestamp)/60);
            x.timestamp=(new Date(x.first_timestamp*1000)).toLocaleString();
        });
        
        let compare = (a, b) => {
            if (a.first_timestamp < b.first_timestamp) {
                return 1;
            }
            if (a.first_timestamp > b.first_timestamp) {
                return -1;
            }
            return 0;
        };
        sessiondata.sort(compare);
        
        data=sessiondata;   

        const tableData = data.map(value => {
            return (
            `<tr>
                <td>${value.timestamp}</td>
                <td>${value.duration}</td>
                <td>${value.kwh}</td>
            </tr>`
            );
        }).join('');

        const tableBody = document.querySelector("#tableBody");
        tableBody.innerHTML = tableData;


        /////////////////
        // Aggregates
        const dailyTotals = aggregate(data, formatDate);
        const weeklyTotals = aggregate(data, getWeekCommencing);
        const monthlyTotals = aggregate(data, getMonth);

        console.log("weeklyTotals",weeklyTotals);
        const last7Days = lastN(dailyTotals, 7, "daily");
        const last4Weeks = lastN(weeklyTotals, 4, "weekly");
        const last4Months = lastN(monthlyTotals, 4, "monthly");
        console.log("last4Months",last4Months);
        console.log("last4weeks",last4Weeks);
        console.log("last7days",last7Days);

        // --- Plotly with tabs ---
        const traces = [
        {
            x: last7Days.labels,
            y: last7Days.values,
            type: "bar",
            marker: { color: "rgba(0,150,255,0.7)" },
            name: "Daily",
            legend: "Daily",
            legendgroup: "1",

        },
        {
            x: last4Weeks.labels,
            y: last4Weeks.values,
            type: "bar",
            marker: { color: "rgba(0,200,100,0.7)" },
            name: "Weekly",
            legend: "Weekly",
            legendgroup: "2",
            xaxis: "x2", yaxis:"y2",
        },
        {
            x: last4Months.labels,
            y: last4Months.values,
            type: "bar",
            marker: { color: "rgba(200,100,255,0.7)" },
            name: "Monthly",
            legend: "Monthly",
            legendgroup: "3",
            xaxis: "x3", yaxis:"y3",

        }
        ];

        const layout = {
        title: "EV Charging Energy Delivered",
        xaxis: { 
              title: "Period",
              type: "category",
              tickangle: 90,
              tickformat: "%d-%b",
        },
        xaxis2: {
              title: "Period",
              type: "category",
              tickangle: 90,
              tickformat: "%d-%b",

        },
        xaxis3: {
              title: "Period",
              type: "category",
              tickangle: 90,
              tickformat: "%b"
        },
  
        yaxis: { title: "Energy (kWh)" },
        grid: {rows: 1,columns: 3, pattern: 'independent', subplot_titles: ["1","2","3"]},
        paper_bgcolor: "#282c34",
        plot_bgcolor: "#282c34",
        font: { color: "#eee"},
        showlegend: false,
        annotations: [{
          text: "Daily",
          font: {size: 16, color: "rgba(0,150,255,0.7)"},
          showarrow: false,
          align: 'center',
          x: 0.13,
          y: 1.2,
          xref: 'paper',
          yref: 'paper'},
        {
          text: "Weekly",
          font: {size: 16, color: "rgba(0,200,100,0.7)"},
          showarrow: false,
          align: 'center',
          x: 0.5,
          y: 1.2,
          xref: 'paper',
          yref: 'paper'},
        {
          text: "Monthly",
          font: {size: 16, color: "rgba(200,100,255,0.7)"},
          showarrow: false,
          align: 'center',
          x: 0.9,
          y: 1.2,
          xref: 'paper',
          yref: 'paper' }
        ]
        };

        Plotly.newPlot("chart", traces, layout, {displayModeBar:false, responsive:true});
            

    })


function downloadCSV() {

    rows=[["Date","Time","Connected Duration (Minutes)","Power Delivered (kWh)"]];
    data.forEach((x) => {rows.push([x.timestamp,x.duration,Math.round(x.joules / 360000)/10])});
    console.log(rows);
    let csvContent = "data:text/csv;charset=utf-8," + rows.map(e => e.join(",")).join("\n");

    var encodedUri = encodeURI(csvContent);
    var link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "my_data.csv");
    document.body.appendChild(link); // Required for FF

    link.click(); // This will download the data file named "my_data.csv".
}



// Convert joules → kWh
const toKWh = j => j / 3.6e6;

// --- Splitting logic ---
function splitSession(session, keyFunc) {
  const start = new Date(session.first_timestamp * 1000);
  const end = new Date(session.last_timestamp *1000);
  const totalSeconds = (end - start) / 1000;
  if (totalSeconds <= 0) return [];

  const totalKWh = toKWh(session.joules);
  const results = [];

  let cursor = new Date(start);

  while (cursor < end) {
    // next boundary according to grouping
    let boundary;
    if (keyFunc === formatDate) {
      boundary = new Date(cursor);
      boundary.setUTCHours(24,0,0,0); // next midnight
    } else if (keyFunc === getWeekCommencing) {
      const day = cursor.getUTCDay() || 7;
      const daysUntilNextWeek = 8 - day;
      boundary = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth(), cursor.getUTCDate() + daysUntilNextWeek));
      boundary.setUTCHours(0,0,0,0);
    } else if (keyFunc === getMonth) {
      boundary = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth()+1, 1));
    }

    const sliceEnd = (boundary < end) ? boundary : end;
    const sliceSeconds = (sliceEnd - cursor) / 1000;
    const fraction = sliceSeconds / totalSeconds;
    const kWhSlice = totalKWh * fraction;

    results.push({ key: keyFunc(cursor), kWh: kWhSlice });
    cursor = sliceEnd;
  }
  return results;
}

// --- Grouping key functions ---
function formatDate(d) {
  return d.toISOString().split("T")[0];
}

function getWeekCommencing(d) {
  var diff = d.getDate() - d.getDay() + (d.getDay() === 0 ? -6 : 1);

  newdate=new Date(d.setDate(diff));
  newdate.setHours(0,0,0,0);
  return `${newdate.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()+1).padStart(2,"0")}`;
}

function getMonth(d) {
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,"0")}`;
}

// --- Aggregation with splitting ---
function aggregate(data, keyFunc) {
  const totals = {};
  data.forEach(session => {
    const parts = splitSession(session, keyFunc);
    parts.forEach(({key, kWh}) => {
      totals[key] = (totals[key] || 0) + kWh;
    });
  });
  return totals;
}

function sortKeys(keys, mode) {
  if (mode === "daily") return keys.sort((a,b)=> new Date(a)-new Date(b));
  if (mode === "weekly") return keys.sort();
  if (mode === "monthly") return keys.sort();
  return keys;
}

function lastN(obj, n, mode) {
  const keys = sortKeys(Object.keys(obj), mode);
  const slice = keys.slice(-n);
  return { labels: slice, values: slice.map(k => obj[k]) };
}

