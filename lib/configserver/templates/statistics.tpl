<head>
  <script src="https://cdn.plot.ly/plotly-3.1.0.min.js" charset="utf-8"></script>
</head>

<body>
	<div id='chart_Power'><!-- Plotly chart will be drawn inside this DIV --></div>
	<div id='chart_Current'><!-- Plotly chart will be drawn inside this DIV --></div>
</body>

<script>

var chartdata = [];
const layout = { grid: {rows: 3,columns: 1, pattern: 'independent'},
                  legend1: {y:0.9, yanchor:'top'},
                  legend2: {y:0.65, yanchor:'top'},                          
                  legend3: {y:0.27, yanchor:'top'}, 
                  showlegend:true,
                  margin: { t: 30 },
                  paper_bgcolor: "#282c34",
                  plot_bgcolor: "#282c34",
                  font: { color: "#eee"},
                  y1: {rangemode: 'tozero'},              
                  y2: {rangemode: 'tozero'},  
                  y3: {rangemode: 'tozero'},  
                  };

//url='/getchartdata?type=plotly&series=eo_charger_state_id,eo_power_requested:eo_power_requested_solar:eo_power_requested_grid:eo_power_requested_site_limit:eo_power_delivered,eo_current_vehicle:eo_current_site:eo_current_solar';
//url='/getchartdata?type=plotly&series=eo_charger_state_id,eo_amps_requested:eo_amps_requested_solar:eo_amps_requested_grid:eo_amps_requested_site_limit:eo_amps_delivered,eo_current_vehicle:eo_current_site:eo_current_solar';
url='/getchartdata?type=plotly&series=eo_charger_state_id,eo_amps_requested_solar:eo_amps_requested_grid:eo_amps_requested_site_limit:eo_amps_requested:eo_amps_delivered,eo_current_vehicle:eo_current_site:eo_current_solar';

fetch(url, {method: 'GET'})
    .then(function(response) { return response.json(); })
    .then(function(data) {
        chartdata=data;
        // further process plotly data
        data.forEach(function (item, index) {

          switch (item.key) {
            case 'eo_power_requested','eo_amps_requested':
              item.line={color:'orange',dash:'dot',width:4};
              break;
            case 'eo_power_delivered','eo_amps_delivered':
              item.line={color:'red',width:4};
              break;
            case 'eo_power_requested_grid','eo_amps_requested_grid':
              item.fillcolor='lightblue';
              item.line={color:'black',width:0.25};
              item.stackgroup="power_areastack";
              delete item["mode"];
              delete item["type"];
              break;
            case 'eo_power_requested_solar','eo_amps_requested_solar':
              item.fillcolor='lightgreen';
              item.line={color:'black',width:0.25};
              item.stackgroup="power_areastack";
              delete item["mode"];
              delete item["type"];
              break;
            case 'eo_power_requested_site_limit','eo_amps_requested_site_limit':
              item.fillcolor='darkgrey';
              item.line={color:'black',width:0.25};
              item.stackgroup="power_areastack";
              delete item["mode"];
              delete item["type"];
              break;
            case 'eo_current_vehicle':
              item.line={color:'red',width:2};
              break;
            case 'eo_current_site':
              item.line={color:'orange',width:2};
              break;            
            case 'eo_current_solar':
              item.line={color:'lime',width:2};
              break;
          }

        });

        console.log(data);
        Plotly.newPlot('chart_Power',chartdata,layout);
        timer_Power=setInterval(chartUpdate_Power,30000);
        myplot=Plotly.newPlot('chart_Power',chartdata,layout);

    })


   <!--------------------------------->
    // Then continue to repeat every 30 seconds

    function chartUpdate_Power() {
          maxtime=chartdata[0].x[(chartdata[0].x.length)-1];
          fetch(url+'&since='+maxtime, {method: 'GET'})
              .then(function(response) { return response.json(); })
              .then(function(data) {
              
                chartdata.forEach(function(series,index) {
                  chartdata[index].x=chartdata[index].x.concat(data[index].x);
                  chartdata[index].y=chartdata[index].y.concat(data[index].y);
                });
          
                newmaxtime=chartdata[0].x[(chartdata[0].x.length)-1];
                Plotly.newPlot('chart_Power',chartdata,layout);
              });
    }

    
</script>
	
{% include 'html_footer.tpl' %}