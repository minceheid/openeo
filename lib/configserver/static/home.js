const canvas = document.getElementById("clockCanvas");
const ctx = canvas.getContext("2d");
const startText = document.getElementById("startTime");
const endText = document.getElementById("endTime");
const currentLimText = document.getElementById("currLim");
const modeSwitchSchedule = document.getElementById("modeSwitchSchedule");
const modeSwitchManual = document.getElementById("modeSwitchManual");
const modeSwitchRemote = document.getElementById("modeSwitchRemote");
const modeSwitchContainer = document.getElementById("modeSwitchContainer");
const modeName = document.getElementById("modeName");
const timeDisplay = document.getElementById("timeDisplay");
const innerStateDisplay = document.getElementById("innerStateDisplay");
const statusWhatDoing = document.getElementById("statusWhatDoing");
const statusChargeCurrent = document.getElementById("statusChargeCurrent");
const statusChargeVolt = document.getElementById("statusChargeVolt");
const statusChargePower = document.getElementById("statusChargePower");
const statusChargeSession = document.getElementById("statusChargeSession");
const statusInfo = document.getElementById("statusInfo");

let centerX = canvas.width / 2;
let centerY = canvas.height / 2;
let radiusLarge = 170;
let radiusSmall = 100;
let canvasLarge = 450;
let canvasSmall = 250;
let dragMode = 0;		// 0 = Not dragging, 1 = Dragging timer dot, 2 = Dragging current limit dot
let dragging = null;		
let drawMobile = false;

let slideClickPosTol = 0.2;
let swClickPosTol = 0.1;

// dynamically computed
let powerSwitchWidth = 0;
let powerSwitchYPos = 0;
let powerSwitchHeight = 0;
let powerSwitchRounding = 0;

let currentLimYRelPos = 0.4;
let currentLimXRelPos = 0.55;

let currentLimPos = 0.0;
let currentLimVal = 0;

let currentLimMode = { 'schedule' : 32, 'manual' : 32, 'remote' : -1 };

const maxCurrentLim = 32;
const minCurrentLim = 6;   // Defined by Type2 standard

let currentMode = "manual";  // 'schedule', 'manual', 'remote'
let manualOnState = false;

let reqMissedResponses = 0;

let updateTick = 0;
let updateFreq = 1;

let firstPoll = false;

// assume charger comms start OK
let chargerCommsOk = true;

// Schedule is saved after no alterations to schedule for 5 seconds.
const scheduleSaveAuto = 5000;

function parseTimeToAngle(time) {
	let hours = parseInt(time.substring(0, 2));
	let minutes = parseInt(time.substring(2));
	let totalMinutes = hours * 60 + minutes; 
	return (totalMinutes / 1440) * 2 * Math.PI - Math.PI / 2;
}

let dots = [
	{ angle: parseTimeToAngle("0000"), color: "#4dabf7" } ,
	{ angle: parseTimeToAngle("0000"), color: "#f74d4d" }
];

let lastScheduleDots = window.structuredClone(dots);

['mousedown','touchstart'].forEach(event=>
	canvas.addEventListener(event, (e) => {
		const { x, y } = getMousePos(e);
		
		if (currentMode == "schedule") {
			dots.forEach((dot, index) => {
				if (isInsideDot(x, y, dot.angle)) {
					dragMode = 1;
					dragging = index;
					return;
				}
			});
		}
		
		if (isInsideCurrentLimSlider(x, y, false) !== null) {
			console.log("In slider range");
			dragMode = 2;
			dragging = null;
		}
	})
);

function mouseTouchArcEvent(e) {
	const { x, y } = getMousePos(e);
	dots[dragging].angle = Math.atan2(y - centerY, x - centerX);
	drawUI();
}

function mouseTouchSliderEvent(e) {
	const { x, y } = getMousePos(e);
	let pos = isInsideCurrentLimSlider(x, y, true);
	if (pos !== null) {
		currentLimPos = pos;
		updateCurrentLimText();
		drawUI();
	}
}

canvas.addEventListener("mousemove", (e) => {
	if (dragMode == 1) {
		mouseTouchArcEvent(e);
	} else if (dragMode == 2) {
		mouseTouchSliderEvent(e);
	}
});

canvas.addEventListener("touchmove", (e) => {
	if (dragMode == 1 && currentMode == "schedule") {
		e.preventDefault(); // Prevents scrolling
		mouseTouchArcEvent(e);
	} else if (dragMode == 2) {
		e.preventDefault(); 
		mouseTouchSliderEvent(e);
	}
}, { passive: false }); // Needed so you can call preventDefault

['mouseup','touchend'].forEach(event=>
	canvas.addEventListener(event, (e) => {
		const { x, y } = getMousePos(e);
		
		if (dragMode == 1 && currentMode == "schedule") {
			window.setTimeout(() => { saveSchedule(true); }, scheduleSaveAuto);
		} else if (dragMode == 2) {
			snapCurrent();
			saveCurrentLimit();
		}
		
		if (currentMode == "manual") {
			if (isInsidePowerSwitch(x, y)) {
				console.log("insidePowerSwitch state ", manualOnState);
				manualOnState = !manualOnState;
				console.log('Save state: power switch change');
				saveState();
				drawUI();
			}
		}
		
		dragMode = 0;
		dragging = null
	})
);

/* Icon event listeners */
['mousedown','touchstart'].forEach(event=>
	modeSwitchSchedule.addEventListener(event, () => {
		switchTo("schedule")
	})
);
['mousedown','touchstart'].forEach(event=>
	modeSwitchManual.addEventListener(event, () => {
		switchTo("manual")
	})
);

/* Coming soon. */
/*
['mousedown','touchstart'].forEach(event=>
	modeSwitchRemote.addEventListener(event, () => {
		switchTo("remote")
	})
);
*/

function redrawModes() {
	modeSwitchSchedule.classList.remove("disabled");
	modeSwitchManual.classList.remove("disabled");
	//modeSwitchRemote.classList.remove("disabled");
	
	if (chargerCommsOk) {
		if (currentMode == "schedule") {
			modeSwitchSchedule.classList.add("active");
			modeSwitchManual.classList.remove("active");
			//modeSwitchRemote.classList.remove("active");
			modeName.innerHTML = "Schedule Mode";
		} else if (currentMode == "manual") {
			modeSwitchSchedule.classList.remove("active");
			modeSwitchManual.classList.add("active");
			//modeSwitchRemote.classList.remove("active");
			modeName.innerHTML = "Manual Mode";
		} else if (currentMode == "remote") {
			modeSwitchSchedule.classList.remove("active");
			modeSwitchManual.classList.remove("active");
			//modeSwitchRemote.classList.add("active");
			modeName.innerHTML = "Remote Function Mode";
		}
	} else {
		modeSwitchSchedule.classList.remove("active");
		modeSwitchManual.classList.remove("active");
		//modeSwitchRemote.classList.remove("active");
		modeSwitchSchedule.classList.add("disabled");
		modeSwitchManual.classList.add("disabled");
		//modeSwitchRemote.classList.add("disabled");
		modeName.innerHTML = "Charger Unreachable";
	}
}

function getRadius() {
	if (drawMobile)
		return radiusSmall;
	else
		return radiusLarge;
}

function isInsideCurrentLimSlider(x, y, ignoreY) {
	radius = getRadius();
	x0 = centerX - (radius*currentLimXRelPos) - (radius*slideClickPosTol);
	xs = centerX - (radius*currentLimXRelPos);
	x1 = centerX + (radius*currentLimXRelPos) + (radius*slideClickPosTol);
	xe = centerX + (radius*currentLimXRelPos);
	y0 = centerY + (radius*currentLimYRelPos) - (radius*slideClickPosTol);
	y1 = centerY + (radius*currentLimYRelPos) + (radius*slideClickPosTol);
	
	if (x >= x0 && x <= x1) {
		if (ignoreY || (y >= y0 && y <= y1)) {
			// return the clamped fractional position on the slider
			return clamp((x - xs) / (xe - xs), 0, 1);
		}
	}
	
	return null;
}

function isInsidePowerSwitch(x, y) {
	radius = getRadius();
	x0 = centerX - (powerSwitchWidth/2) - (radius*swClickPosTol);
	y0 = centerY - powerSwitchYPos - (radius*swClickPosTol)
	x1 = centerX + (powerSwitchWidth/2) + (radius*swClickPosTol);
	y1 = centerY - powerSwitchYPos + powerSwitchHeight + (radius*swClickPosTol);
	
	return (x >= x0 && x <= x1 && y >= y0 && y <= y1);
}

function updateCurrentLimSliderForRemoteValue(remVal) {
	console.log('updateCurrentLimSliderForRemoteValue value ' + remVal);
	currentLimPos = (remVal - minCurrentLim) / (maxCurrentLim - minCurrentLim);
	currentLimPos = clamp(currentLimPos, 0, 1);
	currentLimVal = remVal;
	updateCurrentLimText();
}

function updateCurrentLimText() {
	tempLimVal = Math.floor(minCurrentLim + ((maxCurrentLim - minCurrentLim) * currentLimPos));
	console.log('updateCurrentLimText value ' + tempLimVal + ' curPos ' + currentLimPos);
	currentLimText.innerHTML = tempLimVal.toString() + "A";
}

function snapCurrent() {
	currentLimVal = minCurrentLim + Math.floor((maxCurrentLim - minCurrentLim) * currentLimPos);
	currentLimMode[currentMode] = currentLimVal;
	console.log('New current limit for mode ', currentMode, ' is ', currentLimVal);
	
	currentLimPos = (currentLimVal - minCurrentLim) / (maxCurrentLim - minCurrentLim);
	updateCurrentLimText();
	console.log('Save state: current limit');
	saveState();
	drawUI();
	updateStatus();
	
	canvas.style.visibility = 'visible';
}

function isInsideDot(x, y, angle) {
	radius = getRadius();
	const dotX = centerX + radius * Math.cos(angle);
	const dotY = centerY + radius * Math.sin(angle);
	return Math.hypot(x - dotX, y - dotY) < 15;
}

function angleToTime(angle) {
	let totalMinutes = Math.floor(((angle + Math.PI / 2) / (2 * Math.PI)) * 1440) % 1440;
	if (totalMinutes < 0) totalMinutes += 1440;
	let hours = Math.floor(totalMinutes / 60);
	let minutes = totalMinutes % 60;
	
	// time adjustment has a 5 minute resolution
	minutes = minutes - (minutes % 5);
	
	return hours.toString().padStart(2, '0') + minutes.toString().padStart(2, '0');
}

function clamp(num, min, max) {
  return num <= min 
    ? min 
    : num >= max 
      ? max 
      : num
}

function normalizeAngle(angle) {
    // Normalize angle to [0, 2π)
    return (angle % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);
}

function drawUI() {
	redrawModes();
	
	if (currentMode == "schedule") {
		drawClock();
		drawCurrentLimit();
	} else if (currentMode == "manual") {
		drawPowerSwitch();
		drawCurrentLimit();
	} else if (currentMode == "remote") {
		drawRemoteMode();
		drawCurrentLimit();
	}
}

function drawClock() {
	radius = getRadius();
	ctx.clearRect(0, 0, canvas.width, canvas.height);
	ctx.beginPath();
	ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
	ctx.strokeStyle = "white";
	ctx.lineWidth = 4;
	ctx.stroke();
	
	// @TODO: rework this into a conic gradient around the centre of the arc?
	const gradient = ctx.createLinearGradient(
		centerX + radius * Math.cos(dots[0].angle),
		centerY + radius * Math.sin(dots[0].angle),
		centerX + radius * Math.cos(dots[1].angle),
		centerY + radius * Math.sin(dots[1].angle)
	);
	gradient.addColorStop(0, dots[0].color);
	gradient.addColorStop(1, dots[1].color);
	
	ctx.beginPath();
	ctx.strokeStyle = gradient;
	ctx.lineWidth = 10;
	ctx.arc(centerX, centerY, radius, dots[0].angle, dots[1].angle, false);
	ctx.stroke();
	
	dots.forEach((dot) => {{
		const dotX = centerX + radius * Math.cos(dot.angle);
		const dotY = centerY + radius * Math.sin(dot.angle);
		ctx.beginPath();
		ctx.arc(dotX, dotY, 12, 0, Math.PI * 2);
		ctx.fillStyle = dot.color;
		ctx.fill();
	}});

	timeDisplay.style.visibility = 'visible';
	innerStateDisplay.style.visibility = 'hidden';
	
	startText.innerHTML = angleToTime(dots[0].angle);
	endText.innerHTML = angleToTime(dots[1].angle);
}

function drawPowerSwitch() {
	radius = getRadius();
	
	powerSwitchWidth = radius*1.0;
	powerSwitchYPos = radius*0.6;
	powerSwitchHeight = radius*0.40;
	powerSwitchRounding = powerSwitchHeight/2;
	
	ctx.clearRect(0, 0, canvas.width, canvas.height);
	
	// Background and border goes 'green' when on
	if (manualOnState) {
		ctx.fillStyle = "#44aa44";
		ctx.strokeStyle = "#44ff44";
	} else {
		ctx.fillStyle = "#333333";
		ctx.strokeStyle = "#aaaaaa";
	}
	
	ctx.lineWidth = 2;
	ctx.beginPath();
	ctx.roundRect(centerX - (powerSwitchWidth/2), centerY - powerSwitchYPos, powerSwitchWidth, powerSwitchHeight, powerSwitchRounding);
	ctx.stroke();
	ctx.fill();
	
	// Draw 'ON' or 'OFF' position.
	// Follow Apple style: off to the left, on to the right.
	circlePadding = 4;
	circleRadius = (powerSwitchHeight / 2) - circlePadding;
	
	if (manualOnState)
		circleX = centerX + (powerSwitchWidth/2) - circleRadius - circlePadding;
	else
		circleX = centerX - (powerSwitchWidth/2) + circleRadius + circlePadding;
	
	circleY = centerY - powerSwitchYPos + (powerSwitchHeight / 2);
	
	ctx.lineWidth = 1;
	ctx.strokeStyle = "#aaaaaa";
	ctx.fillStyle = "#dddddd";
	
	ctx.beginPath();
	ctx.arc(circleX, circleY, circleRadius, 0, 2 * Math.PI);
	ctx.stroke();
	ctx.fill();

	timeDisplay.style.visibility = 'hidden';
	innerStateDisplay.style.visibility = 'visible';
	
	if (manualOnState)
		innerStateDisplay.innerHTML = '<p>Charging Enabled</p>';
	else
		innerStateDisplay.innerHTML = '<p>Charging Disabled</p>';
}

function drawRemoteMode() {
	ctx.clearRect(0, 0, canvas.width, canvas.height);
	innerStateDisplay.innerHTML = '<p>Remote Mode</p><p>3 Modules Enabled</p>';
	
	timeDisplay.style.visibility = 'hidden';
	innerStateDisplay.style.visibility = 'visible';
}

function drawCurrentLimit() {
	radius = getRadius();
	let x0 = centerX - (radius*currentLimXRelPos);
	let x1 = centerX + (radius*currentLimXRelPos);
	let y = centerY + (radius*currentLimYRelPos);
	
	radius = getRadius();
	ctx.beginPath();
	ctx.moveTo(x0, y);
	ctx.lineTo(x0 + (currentLimPos * (x1 - x0)), y);
	ctx.strokeStyle = "#ffffff";
	ctx.lineWidth = 4;
	ctx.stroke();
	ctx.beginPath();
	ctx.lineTo(x0 + (currentLimPos * (x1 - x0)), y);
	ctx.lineTo(x1, y);
	ctx.strokeStyle = "#888888";
	ctx.lineWidth = 4;
	ctx.stroke();
	
	ctx.beginPath();
	ctx.lineWidth = 0;
	ctx.strokeStyle = "#ffffff";
	ctx.arc(x0 + (currentLimPos * (x1 - x0)), y, 5, 0, Math.PI * 2);
	ctx.fillStyle = "#ffffff";
	ctx.fill();
	ctx.stroke();
}

function saveSchedule(report) {
	const start = angleToTime(dots[0].angle);
	const end = angleToTime(dots[1].angle);
	
	console.log('Going to save schedule ' + start + ' ' + end);
	console.log('LastSchedule ' + JSON.stringify(lastScheduleDots));
	
	fetch('/setconfig', {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({ scheduler: { schedule: [{ start: start, end: end, amps : currentLimMode['schedule'] }]}}),
	})
	.then(response => response.json())
	.then(data => {
		if (report) {
			makeToast('Saved new schedule');
		}
	})
	.catch(error => {
		makeToastError('Unable to save state: no response from charger');
	});
}

function saveState() {
	const start = angleToTime(dots[0].angle);
	const end = angleToTime(dots[1].angle);
	
	if (!firstPoll) {
		console.log('Not saving state as first config poll not done');
		return;
	}
	
	console.log('Going to save state');
	
	switch_enabled = 0;
	schedule_enabled = 0;
	
	if (currentMode == "manual")
		switch_enabled = 1;
	if (currentMode == "schedule")
		schedule_enabled = 1;
	
	fetch('/setconfig', {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({ "switch" : { enabled : switch_enabled, on : manualOnState, amps : currentLimMode['manual'] }, 
		                       //"scheduler" : { enabled : schedule_enabled, amps : currentLimVal, schedule : [{ start : start, end : end }]}
							 }),
	})
	.then(response => response.json())
	.then(data => {
		// Do nothing: the state change is apparent to the user.
	})
	.catch(error => {
		makeToastError('Unable to save state: ' + error.toString())
	});
	
	// Update the status quickly after for user feedback (Set two requests so we catch the edge)
	// @FUTURE: this is really hacky because the internal state of the charger only updates once per second
	window.setTimeout(() => { updateStatus(true); }, 500);
	window.setTimeout(() => { updateStatus(true); }, 1500);
}

function saveCurrentLimit() {
	if (currentMode == "schedule")
		saveSchedule(false);
	else if (currentMode == "manual")
		saveState();
	else
		console.log('Not implemented saving current limit for mode ', currentMode);
}

function saveMode() {
	console.log('saveMode(' + currentMode + ')');
	
	config={};
	/* This has a specific endpoint because it has side effects. */
	fetch('/setmode', {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({ newmode : currentMode }),
	})
	.then(response => response.json())
	.then(data => {
		/* Do nothing: the state change is apparent to the user. */
		updateConfig(data.config);
	})
	.catch(error => {
		makeToastError('Unable to save state: ' + error.toString())
	});
	return(config);
}

function switchTo(newMode) {
	currentMode = newMode;
	updateCurrentLimSliderForRemoteValue(currentLimMode[currentMode]);
	currentLimVal = currentLimMode[currentMode];
	console.log('Current mode limits: ', currentLimMode)
	drawUI();
	saveState();
	saveMode()
	//updateConfig();
	snapCurrent();
}

function windowSizeAdjust() {
	// Responsive design: if window size < X pix, scale down clock
	if (window.innerWidth < 850 || window.innerHeight < 850) {
		// small clock
		drawMobile = true;
		canvas.width = canvasSmall;
		canvas.height = canvasSmall;
		centerX = canvas.width / 2;
		centerY = canvas.height / 2;
		document.body.style.zIndex = 1; // trigger layout recompute
		drawUI();
	} else {
		// larger clock
		drawMobile = false;
		canvas.width = canvasLarge;
		canvas.height = canvasLarge;
		centerX = canvas.width / 2;
		centerY = canvas.height / 2;
		document.body.style.zIndex = 1; // trigger layout recompute
		drawUI();
	}
}

function updateStatus(once) {
	console.log('updateStatus ' + once + ', ' + updateTick + '/' + updateFreq);
	
	if (once || ((updateTick % updateFreq) == 0)) {
		updateTick++;
	
		fetch('/getstatus', {
			method: 'GET'
		})
		.then(function(response) { return response.json(); })
		.then(function(stat) {
			chargerCommsOk = true;
			updateFreq = 1;
			
			reqMissedResponses = 0;
			
			statusChargeVolt.innerHTML = Math.round(stat['eo_live_voltage'], 0) + "V";
			statusChargeCurrent.innerHTML = Math.round(stat['eo_current_vehicle'], 0) + "/" + Math.round(stat['eo_amps_requested'], 0) + "A";
			statusChargePower.innerHTML = Number(stat['eo_power_delivered']).toFixed(2) + "kW";
			statusChargeSession.innerHTML = Number(stat['eo_session_kwh']).toFixed(2) + "kWh";
			
			// Would need translation eventually
			if (!stat['eo_connected_to_controller']) {
				statusWhatDoing.innerHTML = "Error (Controller Fault)";
				statusWhatDoing.setAttribute("class", "");
				statusWhatDoing.classList.add("status-item");
				statusWhatDoing.classList.add("status-fault");
			} else {
				state = stat['eo_charger_state'];
				
				/* Convert the state into a user-friendly message, that summarises roughly
				   what is going on. */
				if (state == 'car-connected') {
					if (stat['eo_amps_requested'] == 0) {
						state = 'charge-suspended';
					}
				} else if (state == 'charge-complete') {
					/* The EO controller reports the charge is complete after any session is 
					   stopped by the vehicle, but realistically this is wrong.  We have no idea 
					   why the car stopped charging.  Correct this to 'car-connected' if we are
					   requesting current and 'charge-suspended' if we aren't.  If we are requesting
					   current then the EVSE is ready to charge, but the car -isn't- for whatever 
					   reason.   Could be a full battery, could be a schedule, could be a fault, 
					   could be Octopii interference;  we have no idea, and neither does EO! */
					if (stat['eo_amps_requested'] > 0) {
						state = 'car-connected';
					} else {
						state = 'charge-suspended';
					}
				}
				
				if (state == 'idle') {
					statusWhatDoing.innerHTML = "Idle";
					statusWhatDoing.setAttribute("class", "");
					statusWhatDoing.classList.add("status-item");
					statusWhatDoing.classList.add("status-idle");
				} else if (state == 'plug-present') {
					statusWhatDoing.innerHTML = "Waiting for Connection";
					statusWhatDoing.setAttribute("class", "");
					statusWhatDoing.classList.add("status-item");
					statusWhatDoing.classList.add("status-paused-by-connection");
				} else if (state == 'car-connected') {
					statusWhatDoing.innerHTML = "Waiting for Vehicle";
					statusWhatDoing.setAttribute("class", "");
					statusWhatDoing.classList.add("status-item");
					statusWhatDoing.classList.add("status-paused-by-vehicle");
				} else if (state == 'mains-fault') {
					statusWhatDoing.innerHTML = "Error";
					statusWhatDoing.setAttribute("class", "");
					statusWhatDoing.classList.add("status-item");
					statusWhatDoing.classList.add("status-fault");
				} else if (state == 'charging' && stat['eo_amps_requested'] > 0) {
					statusWhatDoing.innerHTML = "Charging";
					statusWhatDoing.setAttribute("class", "");
					statusWhatDoing.classList.add("status-item");
					statusWhatDoing.classList.add("status-charging");
				} else if (state == 'charging' || state == 'charge-complete' || state == 'charge-suspended') {
					// If car is still charging, show 'Pausing'
					if (stat['eo_current_vehicle'] > 0) {
						statusWhatDoing.innerHTML = "Pausing (Waiting for Vehicle)";
						statusWhatDoing.setAttribute("class", "");
						statusWhatDoing.classList.add("status-item");
						statusWhatDoing.classList.add("status-paused-by-evse");
					} else {
						if (currentMode == "schedule") {
							statusWhatDoing.innerHTML = "Paused (Awaiting Schedule)";
							statusWhatDoing.setAttribute("class", "");
							statusWhatDoing.classList.add("status-item");
							statusWhatDoing.classList.add("status-paused-by-evse");
						} else {
							statusWhatDoing.innerHTML = "Paused";
							statusWhatDoing.setAttribute("class", "");
							statusWhatDoing.classList.add("status-item");
							statusWhatDoing.classList.add("status-paused-by-evse");
						}
					}
				} else {
					statusWhatDoing.innerHTML = "Unknown";
					statusWhatDoing.setAttribute("class", "");
					statusWhatDoing.classList.add("status-item");
				}
			}
			
			statusInfo.style.visibility = 'visible';
			drawUI();
		})
		.catch(error => {
			console.log('Error fetching status: ', error);
			reqMissedResponses++;
			if (reqMissedResponses >= 10) {
				console.log('Too many responses missed, backing off');
				updateFreq = 10;  // Once every 10 calls check status until we get a response
				chargerCommsOk = false;
				drawUI();
				return;
			}
		});
	}
}

function updateConfig(stat) {
		firstPoll = true;
		
		// Currently only support simple schedules
		if (stat['scheduler']['schedule'].length > 0) {
			dots[0].angle = parseTimeToAngle(stat['scheduler']['schedule'][0]['start']);
			dots[1].angle = parseTimeToAngle(stat['scheduler']['schedule'][0]['end']);
			console.log('Schedule set ', dots[0].angle, dots[1].angle);
		} else {
			console.log('Schedule is too short');
		}
		
		currentLimMode['manual'] = stat?.['switch']?.amps ?? 0;
		currentLimMode['schedule'] = stat?.scheduler?.schedule?.[0]?.amps ?? 0;
		
		manualOnState = stat?.switch?.on ?? false;
		console.log('manualOnState is set to ', manualOnState);
		
		// determine the current mode; this is tracked in 'chargeroptions' module
		currentMode = stat?.chargeroptions?.mode ?? 'manual';
		
		currentLimVal = currentLimMode[currentMode];
		updateCurrentLimSliderForRemoteValue(currentLimVal);
				
		drawUI();

}
function fetchAndUpdateConfig() {
	fetch('/getconfig', {
		method: 'GET'
	})
	.then(function(response) { return response.json(); })
	.then(function(stat) {updateConfig(stat)})
	.catch(error => {
		console.log('Error fetching config: ', error);
	});
}

addEventListener("resize", (event) => { windowSizeAdjust() })

window.onload = function() {
	const url = new URL(window.location.href);
	const params = new URLSearchParams(url.search);

	if (params.get('reloadtoast') != null) {
		makeToast("openeo has restarted");
	}
}

/* Initial state */
fetchAndUpdateConfig();
snapCurrent();
windowSizeAdjust();
updateStatus(true);
window.setInterval(() => { updateStatus(false); }, 1000);
window.setInterval(() => { fetchAndUpdateConfig(); }, 30000);  // Update the configuration every 30s, in case another user changes it
drawUI();
redrawModes();
updateCurrentLimText();

modeSwitchContainer.style.display = '';
modeSwitchContainer.style.visibility = 'visible';