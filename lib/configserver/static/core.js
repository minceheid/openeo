const toastMsgContainer = document.getElementById("toastMsgContainer");
const toastMsg = document.getElementById("toastMsg");
const evseName = document.getElementById("evseName");

function fadeToast() {
	if (toastMsgContainer.style.opacity < 0.3) {
		toastMsgContainer.style.opacity = 0;
	} else {
		toastMsgContainer.style.opacity -= toastFadeRate;
		window.setTimeout(fadeToast, toastFadePeriod);
	}
}

function makeToastError(msg) {
	toastMsg.innerHTML = msg;
	toastMsg.classList.add("toast-msg-error");
	toastMsgContainer.style.visibility = 'visible';
	toastMsgContainer.style.opacity = 1.0;
	window.setTimeout(fadeToast, toastFadePeriod);
}

function makeToast(msg) {
	toastMsg.innerHTML = msg;
	toastMsg.classList.remove("toast-msg-error");
	toastMsgContainer.style.visibility = 'visible';
	toastMsgContainer.style.opacity = 1.0;
	window.setTimeout(fadeToast, toastFadePeriod);
}

function getMousePos(e) {
	/* Get mouse or touchscreen position according to passed event */
	let clientX, clientY;
	
	if (e.touches && e.touches.length > 0) {
		clientX = e.touches[0].clientX;
		clientY = e.touches[0].clientY;
	} else {
		clientX = e.clientX;
		clientY = e.clientY;
	}

	const rect = canvas.getBoundingClientRect();
	return { x: clientX - rect.left, y: clientY - rect.top };
}

evseName.innerHTML = 'Main Charger';
