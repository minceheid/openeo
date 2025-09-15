{% include 'app_top.tpl' %}
<head>
  <meta charset="UTF-8">
  <title>CT Sensor Calibration</title>
  <script src="https://cdn.plot.ly/plotly-3.1.0.min.js" charset="utf-8"></script>
  <style>


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
  <br><br>
  <h3>CT Sensor Calibration</h3>

  <div class="ct_tuner">
    <div id="controls"></div>
    <div id="chart"></div>
    <br>
    <div class="buttons">
    <div class="control-group"><button class="eoButton" onclick="doSubmit()">Save Settings</button></div>
    <div class="control-group"><button class="eoButton" onclick="doReset()">Reset Settings</button></div>
    </div>
  </div>

  <script type="text/javascript" src="static/ct_tuner.js"></script>
  {% include 'html_footer.tpl' %}