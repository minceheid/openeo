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

modeSwitchContainer.style.display = 'none';
modeSwitchContainer.style.visibility = 'hidden';
