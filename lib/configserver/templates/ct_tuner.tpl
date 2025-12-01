{% include 'app_top.tpl' %}
<head>
  <meta charset="UTF-8">
  <title>CT Sensor Calibration</title>
  <script src="https://cdn.plot.ly/plotly-3.1.0.min.js" charset="utf-8"></script>
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
}

.displayrow {
	display: flex;
	flex-direction: row;
	justify-content: center;
    align-items: center;
    text-align:center;
    z-index: 1000;
}


#controls {
  display: flex;
  flex-direction: row;
  gap: 20px;
  margin-bottom: 20px;
  z-index: 1000;
}

#buttons {
  display: flex;
  flex-direction: row;
  gap: 20px;
  margin-bottom: 20px;
  z-index: 1000;
}
.buttons {
	display: flex;
	flex-direction: row;
	justify-content: center;
  align-items: center;
      text-align:center;

}

.control-group {
  flex: 1 1 0;       /* grow and shrink equally */
  min-width: 0;      /* allow shrinking below content size */
  background: #222;
  padding: 15px;
  border-radius: 10px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.5);
  z-index: 1000;
}

.control-group h3 {
  margin: 0 0 10px 0;
  font-size: 1.1em;
}
input[type=range] {
  width: 100%;
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

.ct_tuner {
  z-index: 1000;
}

label {
  display: flex;
  justify-content: space-between;
  margin: 4px 0;
}
</style>
</head>
<body>
  <div class="displaycolumn">
    
    <div id="controls" class="displayrow"></div>
    <div id="chart"></div>
    &nbsp;
    <div class="displayrow">
  <br><br>

  <div class="ct_tuner">
    <div id="controls"></div>
    <div id="chart"></div>
    <br>
    <div class="displayrow">
      <div class="control-group">
        <button class="eoButton" onclick="doSubmit()">Save Settings</button>
        &nbsp;
        <button class="eoButton" onclick="doReset()">Reset Settings</button>
      </div>
    </div>
  </div>

  <script type="text/javascript" src="static/ct_tuner.js"></script>
  {% include 'html_footer.tpl' %}