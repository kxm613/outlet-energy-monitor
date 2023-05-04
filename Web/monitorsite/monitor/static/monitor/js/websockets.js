const hostAddress = window_global['mqtt']['hostname'];
const hostPort = window_global['mqtt']['websockets_port'];
const clientId = Math.random() + "_web_client";
const deviceId = window_global['device_id'];

function MonitorPage($){

    console.log(clientId);

    obj = {
        connect: function() {
          obj.client.connect({onSuccess: obj.onConnect,
            onFailure: obj.onFailure});
        },

        onFailure: function(response) {
          console.log(response);
        },

        onConnect: function(response) {
          obj.client.subscribe("devices/" + deviceId + "/monitor/usage", {qos:1});
          obj.client.subscribe("$SYS/broker/connection/" + deviceId + "_broker/state", {qos:1});
        },

        onConnectionLost: function(responseObject) {
          if (responseObject.errorCode !== 0) {
            console.log("onConnectionLost:" + responseObject.errorMessage);
            obj.connect();
          }
        },

        onMessageArrived: function(message) {
            if (message.destinationName.endsWith('state')) {
                obj.onMessageConnectionState(message);
            } else if (message.destinationName.endsWith('usage')) {
                obj.onMessageUsageChanged(message);
	    }
        },

        onMessageConnectionState: function(message) {
            if (message.payloadString == "1" ) {
                console.log("Device Connected");
                $.unblockUI();
            } else {
                console.log("Device Disconnected");
                $.blockUI( {message: '<h1>This device does not ' +
                            'seem to be connected to the Internet.</h1>' +
                            '<p>Please make sure it is powered on ' +
                            'and connected to the network.</p>' });
            }
        },

        onMessageUsageChanged: function(message) {
            new_state = JSON.parse(message.payloadString);
            console.log(new_state)

            obj.state.wattage = Number.parseFloat(new_state.wattage).toFixed(0);
            obj.state.difference = Number.parseFloat(new_state.difference).toFixed(2);
	    obj.state.diff_color = new_state.diff_color;
	    obj.state.outlets = new_state.outlets;

            obj.updateUI();
        },

        onOutletToggle: function(inputEvent) {
	  // prevents conflicts with other buttons in the grid
	  inputEvent.stopPropagation();
	  inputEvent.stopImmediatePropagation();

	  device = inputEvent.target.innerHTML.split(' ')[0];
	  console.log(device);
 	  obj.sendOutletToggle(device);
        },

        sendOutletToggle: function(device) {
	  obj.state.outlets[device]['enabled'] = !obj.state.outlets[device]['enabled'];
	  json = { 'outlets': {} };
	  json['outlets'][device] = obj.state.outlets[device]['enabled'];

          message = new Paho.MQTT.Message(JSON.stringify(json));
          message.destinationName = "devices/" + deviceId + "/monitor/set_enabled";
          message.qos = 1;
          obj.client.send(message);
	  obj.updateOutlets();
        },

        updateUI: function() {
	    obj.updateText();
	    obj.updateOutlets();
        },

	updateTime: function() {
	    let time = new Date();
	    $('#time-text').text(time.toLocaleTimeString());
	},

	updateText: function() {
	    $('#wattage-text').text(`${obj.state.wattage} W`);
	    $('#diff-text').text(`${obj.state.difference >= 0 ? '+' : '-'} ${Math.abs(obj.state.difference)} W`);
	    diffColor = tinycolor({ h: obj.state.diff_color[0] * 360, s: 1.0, v: obj.state.diff_color[2] });
	    $('#diff-text').css('color', diffColor.toHexString());
	},

	updateOutlets: function() {
	    obj.outletGrid.empty();
	    $.each(Object.keys(obj.state.outlets), function(i, device) {
		let wattage = Number.parseFloat(obj.state.outlets[device]['wattage']).toFixed(3);
		let enabled = obj.state.outlets[device]['enabled'];
		let text = `${device} (${enabled ? 'On' : 'Off'})<br/>${wattage} W`;

		let button = document.createElement('button');
		button.className = 'outlet';
		button.innerHTML = text;
		$(button).click(obj.onOutletToggle);

		obj.outletGrid.append(button);
 	    });
	},

        state: {
            wattage: 0,
	    average: 0,
	    difference: 0,
	    diff_color: [.2, 1, .5],
	    outlets: {},
        },

	outletGrid: $('<div id=outlets>').appendTo('#bottom-pane'),
        client: new Paho.MQTT.Client(hostAddress, Number(hostPort),
            clientId),

        init: function() {
            if (deviceId == "") {
                alert("Invalid Device ID");
                return;
            }
            obj.client.onConnectionLost = obj.onConnectionLost;
            obj.client.onMessageArrived = obj.onMessageArrived;

	    setInterval(obj.updateTime, 500);
            obj.connect();
        },
    };

    obj.init();
    return obj;
}

jQuery(MonitorPage);



