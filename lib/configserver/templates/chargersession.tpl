{% include 'app_top.tpl' %}

<head>
  <script src="https://cdn.plot.ly/plotly-3.1.0.min.js" charset="utf-8"></script>
</head>

 <style>

h3 { text-align: center; }

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




.eoButton {
  border-radius: 12px;
  z-index: 1000;
  transition-duration: 0.4s;
  justify-content: center;
  align-items: center;
}
.eoButton:hover {
  background-color: #04AA6D; /* Green */
  color: white;
}


thead tr {
  background-color: #333333;
}
tbody tr:nth-child(odd) {
	background-color: #333333;
}
tbody tr:nth-child(even) {
	background-color: #393939;
}

table td { text-align: center; }

</style>

<body>

  <div class="displaycolumn">
    <div class="displayrow">
      <button class="eoButton" onclick="downloadCSV()">Download Charging Log</button>
    </div>
    <div class="displayrow">
      <div id="chart" style="height:40vh;width:90%;"></div>
    </div>
    <div class="displayrow">
      <table id=sessiontable style="font-size:80%; border-spacing: 3px"></table>
      </center>
    </div>
  </div>
  </body>

<script type="text/javascript" src="static/chargersession.js"></script>
{% include 'html_footer.tpl' %}