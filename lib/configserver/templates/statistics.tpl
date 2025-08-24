<head>
	<!-- Load plotly.js into the DOM -->
	<script src='https://cdn.plot.ly/plotly-3.0.1.min.js'></script>
</head>

<body>
	<div id='chart_Power'><!-- Plotly chart will be drawn inside this DIV --></div>
	<div id='chart_Current'><!-- Plotly chart will be drawn inside this DIV --></div>
</body>

<script>

var chartdata = [];

fetch('/getchartdata?type=plotly&series=eo_power_requested:eo_power_delivered:eo_charger_state_id,eo_current_vehicle:eo_current_site:eo_current_solar', {method: 'GET'})
    .then(function(response) { return response.json(); })
    .then(function(data) {
        chartdata=data
        const layout = { grid: {rows: 2,columns: 1, pattern: 'independent'}};
        Plotly.newPlot('chart_Power',chartdata,layout);
        timer_Power=setInterval(chartUpdate_Power,30000);
    })


   <!--------------------------------->
    // Then continue to repeat every 30 seconds

    function chartUpdate_Power() {
          maxtime=chartdata[0].x[(chartdata[0].x.length)-1];
          fetch('/getchartdata?type=plotly&series=eo_power_requested:eo_power_delivered:eo_charger_state_id,eo_current_vehicle:eo_current_site:eo_current_solar&since='+maxtime, {method: 'GET'})
              .then(function(response) { return response.json(); })
              .then(function(data) {
              
                chartdata.forEach(function(series,index) {
                  chartdata[index].x=chartdata[index].x.concat(data[index].x);
                  chartdata[index].y=chartdata[index].y.concat(data[index].y);
                });
          
                newmaxtime=chartdata[0].x[(chartdata[0].x.length)-1];
                const layout = { grid: {rows: 2,columns: 1, pattern: 'independent'}};
                Plotly.newPlot('chart_Power',chartdata,layout);
              });
    }

    
</script>
	
{% include 'html_footer.tpl' %}