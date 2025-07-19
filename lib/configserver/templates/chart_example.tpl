<head>
	<!-- Load plotly.js into the DOM -->
	<script src='https://cdn.plot.ly/plotly-3.0.1.min.js'></script>
</head>

<body>
	<div id='myDiv'><!-- Plotly chart will be drawn inside this DIV --></div>
</body>

<script>

var chartdata = [];

fetch('/getchartdata?type=plotly', {method: 'GET'})
    .then(function(response) { return response.json(); })
    .then(function(data) {
        // use the json
        chartdata=data;
        console.log(data);

        Plotly.newPlot('myDiv', chartdata);
        timer=setInterval(chartUpdate,30000);
    })


   <!--------------------------------->
    // Then continue to repeat every 30 seconds

    function chartUpdate() {
          maxtime=chartdata[0].x[(chartdata[0].x.length)-1];
          fetch('/getchartdata?type=plotly&since='+maxtime, {method: 'GET'})
              .then(function(response) { return response.json(); })
              .then(function(data) {

                console.log(data);
                
                chartdata.forEach(function(series,index) {
                  chartdata[index].x=chartdata[index].x.concat(data[index].x);
                  chartdata[index].y=chartdata[index].y.concat(data[index].y);
                });
          
                newmaxtime=chartdata[0].x[(chartdata[0].x.length)-1];
                Plotly.newPlot('myDiv', chartdata);
              });
    }

    
</script>
	
{% include 'html_footer.tpl' %}