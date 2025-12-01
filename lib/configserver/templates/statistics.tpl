{% include 'app_top.tpl' %}


<head>
  <script src="https://cdn.plot.ly/plotly-3.1.0.min.js" charset="utf-8"></script>
</head>

 <style>

.displaycolumn {
	width: 90%;
	display: flex;
	flex-direction: column;
	justify-content: flex-start;
	font-size: 14pt;
	overflow-x: hidden;
	overflow-y: auto;
	pointer-events: all;
	z-index: 1000;
	position: relative;
	top: 6em;
  height: 80vh;
}

.displayrow {
	display: flex;
	flex-direction: row;
	justify-content: center;
    align-items: center;
    text-align:center;
    z-index: 1000;
}
</style>

<body>
  <div class="displaycolumn">
    <div id='chartDiv' style="height:80vh;width:auto"></div>
  </div>
</body>

<script>

var chartdata = [];
var timer = null;
var layout = { grid: {rows: 3,columns: 1, pattern: 'independent'},
                  showlegend:true,
                  margin: { t: 30 },
                  paper_bgcolor: "#282c34",
                  plot_bgcolor: "#282c34",
                  font: { color: "#eee"},
                  y1: {rangemode: 'tozero'},              
                  y2: {rangemode: 'tozero'},  
                  y3: {rangemode: 'tozero'},  
                  };

// Calculate Legend positions
const legends=["legend","legend2","legend3"]
legends.forEach((x,i) => {
  layout[x]={y:(legends.length-i) * (1/legends.length) -0.03, yanchor:'top'}
})

url='getchartdata?type=plotly&series=eo_charger_state_id,eo_amps_requested_solar:eo_amps_requested_grid:eo_amps_requested_site_limit:eo_amps_requested:eo_amps_delivered,eo_current_vehicle:eo_current_site:eo_current_solar';

fetch(url, {
  method: 'GET',
  signal: AbortSignal.timeout(5000)
  })
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

        })

        chartUpdate()
    })        
    .catch(error => {
        console.log('Error fetching status: ', error);
      });


   <!--------------------------------->
    // Then continue to repeat every 30 seconds

    function chartUpdate() {

          if (timer==null) {
            // Set Timer Inverval
            timer=setInterval(chartUpdate,30000);
          }

          maxtime=chartdata[0].x[(chartdata[0].x.length)-1];
          fetch(url+'&since='+maxtime, {method: 'GET'})
              .then(function(response) { return response.json(); })
              .then(function(data) {
              
                chartdata.forEach(function(series,index) {
                  chartdata[index].x=chartdata[index].x.concat(data[index].x);
                  chartdata[index].y=chartdata[index].y.concat(data[index].y);
                });
          
                newmaxtime=chartdata[0].x[(chartdata[0].x.length)-1];
                Plotly.newPlot('chartDiv',chartdata,layout,{responsive:true});
              });
    }

    
</script>
	
{% include 'html_footer.tpl' %}