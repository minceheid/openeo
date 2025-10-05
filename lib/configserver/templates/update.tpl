{% include 'app_top.tpl' %}


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

.eoButton {
  border-radius: 12px;
  z-index: 1000;
  transition-duration: 0.4s;
  	justify-content: center;
  align-items: center;
  min-width: 175px;
}
.eoButton:hover {
  background-color: #04AA6D; /* Green */
  color: white;
}

</style>

<body>
 <div class="displaycolumn">
    <div class="displayrow">OpenEO Current Version: <div id="version-info">{{ status['app_version'] }}</div></div>
    <div class="displayrow">OpenEO Latest Version: <div id="openeo_latest_version">{{ status['openeo_latest_version'] }}</div></div>
    <div class="displayrow">
        <button id=updateButton class="eoButton" onclick="beginUpdate('openeo')">Update OpenEO</button>
        &nbsp;
        <button id=updateButton class="eoButton" onclick="beginUpdate('raspberrypi')">Update Raspberry Pi</button>
        &nbsp;
        <button id=updateButton class="eoButton" onclick="location.href = '/';beginUpdate('reboot')">Reboot</button>
    </div>
    &nbsp;
    <div class="displayrow">
      <textarea id="output" name="output" rows=30 cols=80 style="max-width:100%"></textarea>
    </div>
</div>



<script type="text/javascript" src="static/update.js"></script>
{% include 'html_footer.tpl' %}