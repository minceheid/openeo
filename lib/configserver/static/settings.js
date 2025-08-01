const modeSwitchContainer = document.getElementById("modeSwitchContainer");

let lastToggle = "";

function toggleDetail(_id) {
	/* Hide the last object. */
	if (lastToggle != "") {
		let oldToggle = document.getElementById(lastToggle);
		oldToggle.style.display = 'none';
	}
	
	let obj = document.getElementById(_id);
	
	if (obj.style.display == 'none')
		obj.style.display = 'block';
	else
		obj.style.display = 'none';
	
	lastToggle = _id;
}

function requestRestart() {
	fetch("/restart").then(() => {});
	makeToast("Waiting for openeo to restart...");
	window.setTimeout(() => {
		window.location.href = "/?reloadtoast=1";
	}, 7000); // 7 seconds, by experimenting, is enough.
}

window.onload = function() {
	const url = new URL(window.location.href);
	const params = new URLSearchParams(url.search);

	if (params.get('toast2success') != null) {
		makeToast("Settings have been saved");
	}
}

modeSwitchContainer.style.display = 'none';
modeSwitchContainer.style.visibility = 'hidden';
