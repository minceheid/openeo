{% include 'app_top.tpl' %}

<script src="https://cdn.plot.ly/plotly-3.1.0.min.js" charset="utf-8"></script>

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
    <div id='chartDiv' style="height:90vh;width:auto"></div>
  </div>
</body>

<script>

var chartdata = [];
var timer = null;
var layout = { grid: {rows: 4,columns: 1, pattern: 'independent'},
                  showlegend:true,
                  margin: { t: 30 },
                  paper_bgcolor: "#282c34",
                  plot_bgcolor: "#282c34",
                  font: { color: "#eee"},
                  yaxis: {rangemode: 'tozero'},              
                  yaxis2: {rangemode: 'tozero'},  
                  yaxis3: {rangemode: 'tozero'},  
                  yaxis4: {rangemode: 'tozero'},  
                  };
// Calculate Legend positions
const legends=["legend","legend2","legend3","legend4"]
legends.forEach((x,i) => {
  layout[x]={y:(legends.length-i) * (1/legends.length) -0.03, yanchor:'top'}
})

url='getchartdata?type=plotly&series=sys_cpu_temperature:sys_wifi_strength,sys_1m_load_average,sys_free_memory:sys_available_memory,eo_serial_errors';


fetch(url, {
  method: 'GET',
  signal: AbortSignal.timeout(10000)
  })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        chartdata=data;
        chartUpdate()
    })        
    .catch(error => {
        console.log('Error fetching status: ', error);
      });


   <!--------------------------------->
    // Then continue to repeat every 30 seconds

    function chartUpdate() {
console.log("chartUpdate()");
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