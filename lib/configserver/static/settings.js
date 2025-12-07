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
	fetch("restart").then(() => {});
	makeToast("Waiting for openeo to restart...");
	window.setTimeout(() => {
		window.location.href = "/?reloadtoast=1";
	}, 7000); // 7 seconds, by experimenting, is enough.
}

modeSwitchContainer.style.display = 'none';
modeSwitchContainer.style.visibility = 'hidden';


////////////////////////////
// Submit settings via a fetch() call to simulate the form submission
// doing this avoids the browser having to fully refresh the page
// and also allows the /setsettings api to be generic
async function submitSettings() {
	const inputNodeList=document.querySelectorAll('input[id]')
	var params={};
	inputNodeList.forEach( x=> {
		// Radio Buttons and check boxes need slightly different handling
		if (x.type==="radio" &&  x.checked==false) {
			//console.log("Ignoring "+x.id,x.type,x.hasAttribute('checked'));
		} else {
			params[x.name]=x.value;
		}
	})
  
	try {
		const response = await fetch("setsettings",
			{
				method: "POST",
				headers: {"Content-Type": "application/x-www-form-urlencoded"},
				body: new URLSearchParams(params),
			});
		if (!response.ok) {
			makeToast("An error occurred (HTTP "+response.status+") - settings may have not been saved: ");
			throw new Error(`Response status: ${response.status}`);
		} else {
			makeToast("Settings have been saved");
		}
	} catch (error) {
    	console.error(error.message);
 	}
}