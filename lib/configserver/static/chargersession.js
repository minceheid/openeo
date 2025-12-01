
url='getsessiondata';
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
            x.kwh_number=Math.round(x.joules / 360000)/10;
            x.duration=Math.round((x.last_timestamp-Math.max(x.first_timestamp,x.day_timestamp))/60);
            x.timestamp=(new Date(x.first_timestamp*1000)).toLocaleString().replace(',','');
            x.day_timestamp_str=(new Date(x.day_timestamp*1000)).toLocaleString().replace(',','');
            x.last_timestamp_str=(new Date(x.last_timestamp*1000)).toLocaleString().replace(',','');
            x.minutes_charged=Math.round(x.seconds_charged/60,0);

            console.log(x.day_timestamp_str,x.timestamp,x.last_timestamp_str,x.duration,x.minutes_charged);
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
        
        // Generate Table Data - session records in the database are split into days, so, rather than
        // displaying each day as a separate row in the table, we merge the records again by looking at the
        // first_timestamp field.

        tabledata=[];
        last_entry=null;
        sessiondata.forEach((x,i) => {
          if (last_entry==null || x.first_timestamp!=last_entry) {

            tabledata.push({
              first_timestamp: x.first_timestamp,
              last_timestamp:x.last_timestamp,
              joules:x.joules,
              kwh:x.kwh,
              kwh_number:x.kwh_number,
              duration:x.duration,
              timestamp:x.timestamp,
              last_timestamp_str:x.last_timestamp_str,
              minutes_charged:x.minutes_charged,
            });


            last_entry=x.first_timestamp;
            sessionjoules=x.joules;
          } else //if (x.first_timestamp==last_entry) 
          {
            tabledata[tabledata.length-1].last_timestamp=x.last_timestamp;
            tabledata[tabledata.length-1].last_timestamp_str=x.last_timestamp_str;
            tabledata[tabledata.length-1].joules=x.joules;
            tabledata[tabledata.length-1].kwh=x.kwh;
            tabledata[tabledata.length-1].kwh_number=x.kwh_number;
            tabledata[tabledata.length-1].duration+=x.duration;
            tabledata[tabledata.length-1].minutes_charged+=x.minutes_charged;

            // entries in the session log within a single session are cumulative
            // by which I mean that the joules reported within a single session will not reset to zero
            // on each daily entry. To make summary chart construction easier, we need to process that out
            // so that each row reflects the correct number of joules
            sessionjoules_next=x.joules;
            x.joules-=sessionjoules;
            sessionjoules=sessionjoules_next;
            x.first_timestamp=x.day_timestamp;
          }
        }); 

        // Calculate the average kWh for each session in the table
        tabledata.forEach((x)=>{
            if (x.minutes_charged>0) {
              x.average_power=Math.round(x.kwh_number/(x.minutes_charged/60)*10)/10+" kW";
            } else {
              x.average_power="";
            }  
        });

        if (window.innerWidth<460) {
          tableData="<thead><tr class='session-heading'><th>From</th><th>Connected Duration<br>(Minutes)</th><th>Power Delivered</th><th>Charging Duration<br>(Minutes)</th></tr></thead><tbody>";
          tableData += tabledata.map(value => {
              return (
              `<tr>
                  <td>${value.timestamp}</td>
                  <td>${value.duration}</td>
                  <td>${value.kwh}</td>
                  <td>${value.minutes_charged}</td>
              </tr>`
              );
          }).join('');
          tableData+="</tbody>";
        } else {
          tableData="<thead><tr class='session-heading'><th>From</th><th>To</th><th>Connected Duration<br>(Minutes)</th><th>Power Delivered</th><th>Charging Duration<br>(Minutes)</th><th>Average Power<br>Whilst Charging</th></tr></thead><tbody>";
          tableData += tabledata.map(value => {
              return (
              `<tr>
                  <td>${value.timestamp}</td>
                  <td>${value.last_timestamp_str}</td>
                  <td>${value.duration}</td>
                  <td>${value.kwh}</td>
                  <td>${value.minutes_charged}</td>
                  <td>${value.average_power}</td>
              </tr>`
              );
          }).join('');
          tableData+="</tbody>";
        }
  
        const table = document.getElementById("sessiontable");
        table.innerHTML = tableData;

        /////////////////
        // Aggregates - generate histogram data
        const dailyTotals = aggregate(sessiondata, getDate);
        const weeklyTotals = aggregate(sessiondata, getWeekCommencing);
        const monthlyTotals = aggregate(sessiondata, getMonth);

        const last7Days = lastN(dailyTotals, 7, "daily");
        const last4Weeks = lastN(weeklyTotals, 4, "weekly");
        const last4Months = lastN(monthlyTotals, 4, "monthly");


        // --- Plotly with tabs ---
        const traces = [
        {
            x: last7Days.labels,
            y: last7Days.values,
            type: "bar",
            marker: { color: "rgba(67, 98, 252, 0.7)" },
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
            marker: { color: "rgba(207, 49, 255, 0.7)" },
            name: "Monthly",
            legend: "Monthly",
            legendgroup: "3",
            xaxis: "x3", yaxis:"y3",

        }
        ];

        width=window.innerWidth;
        if (width>=768) {
          titlefont = 22;
          axisfont = 12;
        } else if (width<375) {
          titlefont = 10;
          axisfont = 6;
        } else {
          pct = (width-375)/(768-375);
          titlefont = 10+ (22-10) * pct;
          axisfont = 6+ (12-6) * pct;
        }

        const layout = {
        margin: {l:10, r:10 },
        title: "EV Charging Energy Delivered",
        xaxis: { 
              title: "Period",
              type: "category",
              tickangle: 90,
              tickformat: "%d-%b",
              tickfont: {size: axisfont},
        },
        xaxis2: {
              title: "Period",
              type: "category",
              tickangle: 90,
              tickformat: "%d-%b",
              tickfont: {size: axisfont},

        },
        xaxis3: {
              title: "Period",
              type: "category",
              tickangle: 90,
              tickformat: "%b",
              tickfont: {size: axisfont},

        },
  
        yaxis: { 
          title: "Energy (kWh)",
          tickfont: {size: axisfont},
        },
        yaxis2: { 
          title: "Energy (kWh)",
          tickfont: {size: axisfont},
        },        
        yaxis3: { 
          title: "Energy (kWh)",
          tickfont: {size: axisfont},
        },
        grid: {rows: 1,columns: 3, pattern: 'independent', subplot_titles: ["1","2","3"]},
        paper_bgcolor: "#282c34",
        plot_bgcolor: "#282c34",
        font: { color: "#eee"},
        showlegend: false,
        annotations: [{
          text: "Daily",
          font: {size: titlefont, color: "white)"},
          showarrow: false,
          align: 'center',
          x: 0.125,
          y: 1.15,
          xref: 'paper',
          yref: 'paper'},
        {
          text: "Weekly",
          font: {size: titlefont, color: "white)"},
          showarrow: false,
          align: 'center',
          x: 0.5,
          y: 1.15,
          xref: 'paper',
          yref: 'paper'},
        {
          text: "Monthly",
          font: {size: titlefont, color: "white)"},
          showarrow: false,
          align: 'center',
          x: 0.9,
          y: 1.15,
          xref: 'paper',
          yref: 'paper' }
        ]
        };


        Plotly.newPlot("chart", traces, layout, {displayModeBar:false, responsive:true});
            

    })


function downloadCSV() {

    rows=[["From","To","Connected Duration (Minutes)","Power Delivered (kWh)","Charging Duration (Minutes)","Average Power (kW)"]];
    tabledata.forEach((x) => {
      if (x.minutes_charged>0) {
        ap=Math.round((x.joules / 360000)/(x.minutes_charged/60)*10)/10
      } else {
        ap="";
      }
      rows.push([x.timestamp,x.last_timestamp_str,x.duration,Math.round(x.joules / 360000)/10,x.minutes_charged,ap ])});
    //console.log(rows);
    let csvContent = "data:text/csv;charset=utf-8," + rows.map(e => e.join(",")).join("\n");

    var encodedUri = encodeURI(csvContent);
    var link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "openeo_session_data.csv");
    document.body.appendChild(link); // Required for FF

    link.click(); // This will download the data file named "my_data.csv".
}


// --- Grouping key functions for aggregate function ---
function getDate(d) {
  return `${d.getUTCFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}

function getWeekCommencing(d) {
  var diff = d.getDate() - d.getDay() + (d.getDay() === 0 ? -6 : 1);
  d.setDate(diff);
  m=getDate(d);
  return m;
}

function getMonth(d) {
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,"0")}`;
}

// --- Aggregation of session data into summaries for histograms
function aggregate(data, keyFunc) {
  const totals = {};
  data.forEach(session => {
    let date=new Date(session.first_timestamp*1000);
    key=keyFunc(date);
    totals[key] = (totals[key] || 0) + session.kwh_number;
  });
  return totals;
}


function lastN(obj, n, mode) {
  switch(mode) {
    case "daily":
      d=new Date()
      for(i=0;i<n;i++){
        key=getDate(d);
        d.setDate(d.getDate()-1);
        obj[key] = (obj[key] || 0);
      }
      //console.log("daily",n,obj);

      break;
    case "weekly":
      d=new Date()
      var diff = d.getDate() - d.getDay() + (d.getDay() === 0 ? -6 : 1);
      newdate=new Date(d.setDate(diff));
      newdate.setHours(0,0,0,0);
      d=newdate;
      for(i=0;i<n;i++){
        key=getWeekCommencing(d);
        obj[key] = (obj[key] || 0);
        d.setDate(d.getDate()-7);

      }
      //console.log("weekly",n,obj);
      break;
    case "monthly":
      d=new Date()
      var diff = d.getDate() - d.getDay() + (d.getDay() === 0 ? -6 : 1);
      newdate=new Date(d.setDate(diff));
      newdate.setHours(0,0,0,0);
      d=newdate;
      for(i=0;i<n;i++){
        key=getMonth(d);
        obj[key] = (obj[key] || 0);
        d.setMonth(d.getMonth()-1);
      }
      //console.log("monthly",n,obj);
      break;
  }
  const keys = Object.keys(obj).sort();
  const slice = keys.slice(-n);
  return { labels: slice, values: slice.map(k => obj[k]) };
}

