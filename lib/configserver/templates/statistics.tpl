<head>
	<!-- Load plotly.js into the DOM -->
	<script src='https://cdn.plot.ly/plotly-3.0.1.min.js'></script>
</head>

<body>
	<div id='chart_Power'><!-- Plotly chart will be drawn inside this DIV --></div>
	<div id='chart_Current'><!-- Plotly chart will be drawn inside this DIV --></div>
</body>

<script>

var chartdata_Power = [];

fetch('/getchartdata?type=plotly&series=eo_power_requested,eo_power_delivered,eo_charger_state_id', {method: 'GET'})
    .then(function(response) { return response.json(); })
    .then(function(data) {
        // use the json
        chartdata_Power=data;
        Plotly.newPlot('chart_Power', chartdata_Power);
        timer_Power=setInterval(chartUpdate_Power,30000);
    })


   <!--------------------------------->
    // Then continue to repeat every 30 seconds

    function chartUpdate_Power() {
          maxtime=chartdata_Power[0].x[(chartdata_Power[0].x.length)-1];
          fetch('/getchartdata?type=plotly&series=eo_power_requested,eo_power_delivered,eo_charger_state_id&since='+maxtime, {method: 'GET'})
              .then(function(response) { return response.json(); })
              .then(function(data) {

                console.log(data);
                
                chartdata_Power.forEach(function(series,index) {
                  chartdata_Power[index].x=chartdata_Power[index].x.concat(data[index].x);
                  chartdata_Power[index].y=chartdata_Power[index].y.concat(data[index].y);
                });
          
                newmaxtime=chartdata_Power[0].x[(chartdata_Power[0].x.length)-1];
                Plotly.newPlot('chart_Power', chartdata_Power);
              });
    }

var chartdata_Current = [];
fetch('/getchartdata?type=plotly&series=eo_p1_current,eo_p2_current,eo_p3_current', {method: 'GET'})
    .then(function(response) { return response.json(); })
    .then(function(data) {
        // use the json
        chartdata_Current=data;
        Plotly.newPlot('chart_Current', chartdata_Current);
        timer_Power=setInterval(chartUpdate_Power,30000);
    })


   <!--------------------------------->
    // Then continue to repeat every 30 seconds

    function chartUpdate_Power() {
          maxtime=chartdata_Current[0].x[(chartdata_Current[0].x.length)-1];
          fetch('/getchartdata?type=plotly&series=eo_p1_current,eo_p2_current,eo_p3_current&since='+maxtime, {method: 'GET'})
              .then(function(response) { return response.json(); })
              .then(function(data) {

                console.log(data);
                
                chartdata_Current.forEach(function(series,index) {
                  chartdata_Current[index].x=chartdata_Current[index].x.concat(data[index].x);
                  chartdata_Current[index].y=chartdata_Current[index].y.concat(data[index].y);
                });
          
                newmaxtime=chartdata_Current[0].x[(chartdata_Current[0].x.length)-1];
                Plotly.newPlot('chart_Current', chartdata_Current);
              });
    }
    
</script>
	
{% include 'html_footer.tpl' %}