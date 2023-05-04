const hostAddress = window_global['mqtt']['hostname'];
const hostPort = window_global['mqtt']['websockets_port'];
const clientId = Math.random() + "_web_client";

function GraphHandler($){

    console.log(window_global);

    obj = {
        connect: function() {
            obj.client.connect({onSuccess: obj.onConnect,
              onFailure: obj.onFailure});
        },

        onFailure: function(response) {
            console.log(response);
        },

        onConnect: function(response) {
	    Object.keys(window_global.averages).forEach(deviceId => {
                obj.client.subscribe("devices/" + deviceId + "/monitor/usage", {qos:1});
	    });
        },

	onConnectionLost: function(responseObject) {
            if (responseObject.errorCode !== 0) {
              console.log("onConnectionLost:" + responseObject.errorMessage);
              obj.connect();
            }
        },

        onMessageArrived: function(message) {
            monitor_state = JSON.parse(message.payloadString);
	    
	    deviceId = message.destinationName.split('/')[1];
            obj.wattages[deviceId] = Number.parseFloat(monitor_state.wattage);

            obj.updateUI();
        },

	updateUI: function() {
	    var sum = Object.values(obj.wattages).reduce((a, b) => a + b, 0);
            $('#graph-header').text(`Total Current Usage: ${sum.toFixed(1)} W`);

	    var x_pos = new Date().getHours() + new Date().getMinutes() / 60;
	    obj.currentUsagePoint.data = [ { x: x_pos, y: sum, r: Math.round(sum / 10) }];
	    obj.graph.update();
        },

	labels: ["12 AM","","","3 AM","","","6 AM","","","9 AM","","","12 PM","","","3 PM","","","6 PM","","","9 PM","",""],
	wattages: {},
	data: {
	    datasets: []
	},
	currentUsagePoint: { type: 'bubble',
	                     label: 'Current Usage',
			     backgroundColor: 'rgba(94, 120, 247, 0.83)',
	                     data: [ ] },

	client: new Paho.MQTT.Client(hostAddress, Number(hostPort),
            clientId),

	createGraphData: function() {
	    obj.data.datasets.push(obj.currentUsagePoint);

	    var utc_offset = new Date().getTimezoneOffset() / 60;
	    for (var [id, label] of Object.entries(window_global.labels)) {
                var averages = window_global.averages[id];
                // shifting the graph (which records averages for UTC hours) to the user's timezone 
                var timezone_averages = averages.slice(utc_offset).concat(averages.slice(0, utc_offset));
		var datapoints = timezone_averages.map((average, i) => { return { x: i, y: average }; });
                obj.data.datasets.push({ type: 'line',
			             label: label, 
	    	  	             data: datapoints,
    			             borderColor: "#46bdc6",
				     fill: { target: 'origin', above: 'rgba(236, 248, 249, 0.62)' },
    			             tension: 0.2 });
            }
	},

        init: function() {
            obj.client.onConnectionLost = obj.onConnectionLost;
            obj.client.onMessageArrived = obj.onMessageArrived;

	    obj.createGraphData()
	    obj.graph = new Chart($('#graph'), { 
		data: obj.data, 
		options: { 
		    scales: {
			x: {
			    type: 'linear',
			    min: 0,
			    max: 23,
			    title: { display: true, text: 'Hour of the Day' },
			    ticks: {
			        callback: (value, i, ticks) => obj.labels[i],
				stepSize: 1
			    }
			},
			y: { 
			    stacked: true,
			    title: { display: true, text: 'Wattage (W or Wh)'}
			}
		    }
		}
	    });

            obj.connect();
        }
    };

    obj.init();
    return obj;
}

jQuery(GraphHandler);

