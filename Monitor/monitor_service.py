#!/usr/bin/env python3

import kasa
import asyncio
import json
import paho.mqtt.client as mqtt

from datetime import datetime, timezone, timedelta
from variables import *

MQTT_CLIENT_ID = "monitor_service"


class InvalidMessage(Exception):
    pass


class MonitorService(object):

    def __init__(self):
        self._client = self._create_and_configure_broker_client()
        self.outlets = asyncio.run(kasa.Discover.discover(on_discovered=self.on_discovered))
        self.outlet_statuses = {}
        self.current_wattage = 0
        self.hour_wattage = 0
        self.last_poll = datetime.now(timezone.utc)
        self.hour_average = 0
        self.difference = 0
        self.diff_color = [.2, 1, 0.5]
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
        client.message_callback_add(TOPIC_HOUR_AVERAGE,
                                    self.on_message_average)
        client.on_message = self.default_on_message
        return client

    def on_connect(self, client, userdata, rc, unknown):
        self._client.publish(client_state_topic(MQTT_CLIENT_ID), "1",
                             qos=2, retain=True)
        self._client.subscribe(TOPIC_ENABLE_OUTLETS, qos=1)
        self._client.subscribe(TOPIC_HOUR_AVERAGE, qos=1)

    def default_on_message(self, client, userdata, msg):
        print("Received unexpected message on topic " +
              msg.topic + " with payload '" + str(msg.payload) + "'")

    def on_message_average(self, client, userdata, msg):
        try:
            new_average = json.loads(msg.payload.decode('utf-8'))
            if 'hour' not in new_average or new_average['hour'] != datetime.now(timezone.utc).hour:
                raise InvalidMessage()

            self.hour_average = new_average["wattage"]

        except InvalidMessage:
            print("Invalid configuration or incorrect hour. " + str(msg.payload))

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

    async def check_for_outlets(self):
        new_outlets = await kasa.Discover.discover(on_discovered=self.on_discovered)
        if self.outlets.keys() != new_outlets.keys():
            self.outlets = new_outlets

    async def poll_usage_data(self):
        if self.to_enable:
            if self.enable_state:
                await self.to_enable.turn_on()
            else:
                await self.to_enable.turn_off()
            self.to_enable = None

        self.current_wattage = 0
        for device in self.outlets.values():
            await device.update()
            self.outlet_statuses[device.alias] = { 'enabled': device.is_on, 
                                                   'wattage': device.emeter_realtime.power }
            self.current_wattage += device.emeter_realtime.power

        poll_time = datetime.now(timezone.utc)
        watt_hours = self.current_wattage * ((poll_time - self.last_poll) / timedelta(hours=1))
        print(f"Polling at {poll_time.strftime('%H:%M:%S (UTC)')}, added {watt_hours} Wh")
        self.hour_wattage += watt_hours

        if poll_time.hour != self.last_poll.hour:
            print(f"Publishing last hour's usage: {self.hour_wattage} Wh for hour {self.last_poll.hour} (UTC)")
            self.publish_hour_usage()
            self.hour_wattage = 0

        self.last_poll = poll_time

    def publish_hour_usage(self):
        last_hour = { 'hour': self.last_poll.hour,
                      'wattage': self.hour_wattage }
        self._client.publish(TOPIC_HOUR_USAGE,
                             json.dumps(last_hour).encode('utf-8'), qos=1,
                             retain=True)

    def publish_current_usage(self):
        usage = { 'wattage': self.current_wattage,
                  'difference': self.difference,
                  'diff_color': self.diff_color,
                  'outlets': self.outlet_statuses }
        self._client.publish(TOPIC_CURRENT_USAGE,
                             json.dumps(usage).encode('utf-8'), qos=1,
                             retain=True)

    def publish_difference_color(self):
        config = { 'client': 'monitor_service',
                   'color': { 'h': self.diff_color[0],
                              's': 1.0 },
                   'brightness': self.diff_color[2],
                   'on': True }
        self._client.publish(TOPIC_LAMP_CONFIG,
                             json.dumps(config).encode('utf-8'), qos=1)

    def calculate_difference(self):
        self.difference = self.current_wattage - self.hour_average
        normalized_diff = self.difference / (self.hour_average + 0.001)
        normalized_diff = min(1, max(normalized_diff, -1))

        hue = normalized_diff * (-0.2) + 0.2
        value = abs(normalized_diff) / 3 + 0.5

        self.diff_color = [hue, 1.0, value]

    async def serve(self):
        self._client.connect(MQTT_BROKER_HOST,
                             port=MQTT_BROKER_PORT,
                             keepalive=MQTT_BROKER_KEEP_ALIVE_SECS)
        self._client.loop_start()

        count = 0
        while True:
            if (count >= 10):
                await self.check_for_outlets()
                count = 0

            await self.poll_usage_data()
            self.calculate_difference()
            self.publish_current_usage()
            self.publish_difference_color()

            await asyncio.sleep(3)
            count += 1

        


if __name__ == '__main__':
    monitor = MonitorService()
    asyncio.run(monitor.serve())
