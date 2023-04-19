#!/usr/bin/env python3

import kasa
import asyncio
import json
import paho.mqtt.client as mqtt

from variables import *

TEMP_STATE_FILENAME = "temp_state"
MQTT_CLIENT_ID = "monitor_service"


class InvalidMessage(Exception):
    pass


class MonitorService(object):

    def __init__(self):
        self._client = self._create_and_configure_broker_client()
        self.outlets = asyncio.run(kasa.Discover.discover(on_discovered=self.on_discovered))
        self.outlet_statuses = {}
        self.total_wattage = 0
        self.to_enable = None
        self.enable_state = True

    async def on_discovered(self, dev):
        # filter out non-emeters
        print(f'Discovered {dev.alias}')

    def _create_and_configure_broker_client(self):
        client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=MQTT_VERSION)
        client.will_set(client_state_topic(MQTT_CLIENT_ID), "0",
                        qos=2, retain=True)
        client.enable_logger()
        client.on_connect = self.on_connect
        client.message_callback_add(TOPIC_ENABLE_OUTLETS,
                                    self.on_message_set_enabled)
        client.on_message = self.default_on_message
        return client

    def on_connect(self, client, userdata, rc, unknown):
        self._client.publish(client_state_topic(MQTT_CLIENT_ID), "1",
                             qos=2, retain=True)
        self._client.subscribe(TOPIC_ENABLE_OUTLETS, qos=1)

    def default_on_message(self, client, userdata, message):
        print("Received unexpected message on topic " +
              message.topic + " with payload '" + str(message.payload) + "'")

    def on_message_set_enabled(self, client, userdata, msg):
        try:
            new_config = json.loads(msg.payload.decode('utf-8'))
            if 'outlets' not in new_config:
                raise InvalidMessage()
            
            for outlet_name in new_config['outlets']:
                for dev in self.outlets.values():
                    if outlet_name == dev.alias:
                        self.schedule_enable(dev, new_config['outlets'][outlet_name])
                    
        except InvalidMessage:
            print("Invalid outlet configuration. " + str(msg.payload))

    def schedule_enable(self, device, state):
        self.to_enable = device
        self.enable_state = state

    async def poll_usage_data(self):
        if self.to_enable:
            if self.enable_state:
                await self.to_enable.turn_on()
            else:
                await self.to_enable.turn_off()
            self.to_enable = None

        self.total_wattage = 0
        for device in self.outlets.values():
            await device.update()
            self.outlet_statuses[device.alias] = { 'enabled': device.is_on, 
                                                   'wattage': device.emeter_realtime.power }
            self.total_wattage += device.emeter_realtime.power
            
        self.total_wattage

    def publish_usage_data(self):
        usage = { 'total_wattage': self.total_wattage,
                  'average_wattage': 20,
                  'outlets': self.outlet_statuses }
        self._client.publish(TOPIC_CURRENT_USAGE,
                             json.dumps(usage).encode('utf-8'), qos=1,
                             retain=True)

    async def serve(self):
        self._client.connect(MQTT_BROKER_HOST,
                             port=MQTT_BROKER_PORT,
                             keepalive=MQTT_BROKER_KEEP_ALIVE_SECS)
        self._client.loop_start()

        while True:
            await self.poll_usage_data()
            self.publish_usage_data()
            await asyncio.sleep(1)

        


if __name__ == '__main__':
    monitor = MonitorService()
    asyncio.run(monitor.serve())
