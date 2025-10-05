
var timer=null;
const output = document.getElementById("output");
const buttons = document.getElementsByClassName("eoButton");


function beginUpdate(actionType) {
    fetch('/update', {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
        body: JSON.stringify({ action: actionType})
            
    })
	.then(response => response.json())
	.then(data => {
        console.log(data);
        makeToast('Update Started');
        refreshStatus();
	})
}

function refreshStatus() {
    fetch('/update', {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
        body: JSON.stringify({ action: "status"}),
        // Settng a timeout at 850ms because we're sending this request every 1000ms, and it will be better to ensure that
        // a previous request has timed out before sending the next, and we're not building up a large queue of requests
        signal: AbortSignal.timeout(850)
    })
	.then(response => response.json())
	.then(data => {
            console.log(data);
            if (data["openeo_upgrade_running"]==true) {
                if (timer==null) {
                    timer=setInterval(refreshStatus, 1000);
                    for (const button of buttons) { button.disabled = true; }
                }
            } else if (data["openeo_upgrade_running"]==false) {
                console.log("clearing interval timer");
                clearInterval(timer);
                timer=null;
                for (const button of buttons) { button.disabled = false; }

            }
            output.innerHTML=data["openeo_upgrade_log"];
            output.scrollTop = output.scrollHeight;
	})
    .catch(error => {
        console.log('Error fetching status: ', error);
    })
}

refreshStatus();
