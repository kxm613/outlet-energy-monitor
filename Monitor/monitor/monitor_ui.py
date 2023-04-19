import platform
from kivy.app import App
from kivy.properties import NumericProperty, AliasProperty, BooleanProperty, StringProperty
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from math import fabs
import json
import os
from paho.mqtt.client import Client
import pigpio
from variables import *
import monitor.ip_info

import colorsys
import datetime

MQTT_CLIENT_ID = "monitor_ui"


class MonitorApp(App):
    #_updated = False
    #_updatingUI = False

    _wattage = NumericProperty(0)
    _average = NumericProperty(0)

    def _get_wattage(self):
        return self._wattage

    def _set_wattage(self, value):
        self._wattage = value
    
    def _get_average(self):
        return self._average

    def _set_average(self, value):
        self._average = value

    def _get_difference(self):
        return self.wattage - self.average

    def _get_color(self):
        # scaling difference to be between 1x and -1x of the average
        normalized_diff = self.difference / (self.average + 0.001)
        normalized_diff = min(1, max(normalized_diff, -1))

        # converting normalized difference to hue, 1x -> red (0), -1x -> green (0.4)
        hue = normalized_diff * (-0.2) + 0.2
        value = abs(normalized_diff) / 3 + 0.5

        return (hue, 1.0, value)

    def _get_difference_text(self):
        text_color = '%02x%02x%02x' % tuple(map(lambda x: round(x * 255), colorsys.hsv_to_rgb(*self.color)))
        plus_or_minus = '±' if (self.difference == 0) else ('+' if (self.difference > 0) else '-')

        return f'[color={text_color}]{plus_or_minus} {abs(self.difference)} W[/color]'

    wattage = AliasProperty(_get_wattage, _set_wattage, bind=['_wattage'])
    average = AliasProperty(_get_average, _set_average, bind=['_average'])
    difference = AliasProperty(_get_difference, bind=['_wattage', '_average'])
    color = AliasProperty(_get_color, bind=['difference'])
    diff_text = AliasProperty(_get_difference_text, bind=['difference'])
    time_text = StringProperty('')
    gpio17_pressed = BooleanProperty(False)

    def on_start(self):
        self._publish_clock = None
        self.mqtt_broker_bridged = False
        self.mqtt = Client(client_id=MQTT_CLIENT_ID)
        self.mqtt.enable_logger()
        self.mqtt.will_set(client_state_topic(MQTT_CLIENT_ID), "0",
                           qos=2, retain=True)
        self.mqtt.on_connect = self.on_connect
        self.mqtt.connect(MQTT_BROKER_HOST, port=MQTT_BROKER_PORT,
                          keepalive=MQTT_BROKER_KEEP_ALIVE_SECS)
        self.mqtt.loop_start()

        self.set_up_GPIO_and_device_status_popup()
        Clock.schedule_interval(self._update_time, 1)

    def on_connect(self, client, userdata, flags, rc):
        self.mqtt.publish(client_state_topic(MQTT_CLIENT_ID), b"1",
                          qos=2, retain=True)
        self.mqtt.message_callback_add(TOPIC_CURRENT_USAGE,
                                       self.receive_new_state)
        self.mqtt.message_callback_add(broker_bridge_connection_topic(),
                                       self.receive_bridge_connection_status)
        self.mqtt.subscribe(broker_bridge_connection_topic(), qos=1)
        self.mqtt.subscribe(TOPIC_CURRENT_USAGE, qos=1)

    def receive_bridge_connection_status(self, client, userdata, message):
        # monitor if the MQTT bridge to our cloud broker is up
        if message.payload == b"1":
            self.mqtt_broker_bridged = True
        else:
            self.mqtt_broker_bridged = False

    def receive_new_state(self, client, userdata, message):
        new_state = json.loads(message.payload.decode('utf-8'))
        
        if 'wattage' in new_state:
            self.wattage = new_state['wattage']
        if 'average' in new_state:
            self.average = new_state['average']

    def set_up_GPIO_and_device_status_popup(self):
        self.pi = pigpio.pi()
        self.pi.set_mode(17, pigpio.INPUT)
        self.pi.set_pull_up_down(17, pigpio.PUD_UP)
        Clock.schedule_interval(self._poll_GPIO, 0.05)
        self.network_status_popup = self._build_network_status_popup()
        self.network_status_popup.bind(on_open=self.update_device_status_popup)

    def _build_network_status_popup(self):
        return Popup(title='Device Status',
                     content=Label(text='IP ADDRESS WILL GO HERE'),
                     size_hint=(1, 1), auto_dismiss=False)

    def update_device_status_popup(self, instance):
        interface = "wlan0"
        ipaddr = monitor.ip_info.get_ip_address(interface)
        deviceid = monitor.ip_info.get_device_id()
        msg = ("{}: {}\n"
               "DeviceID: {}\n"
               "Broker Bridged: {}\n"
               ).format(interface,
                        ipaddr,
                        deviceid,
                        self.mqtt_broker_bridged)
        instance.content.text = msg

    def on_gpio17_pressed(self, instance, value):
        if value:
            self.network_status_popup.open()
        else:
            self.network_status_popup.dismiss()

    def _poll_GPIO(self, dt):
        self.gpio17_pressed = not self.pi.read(17)

    def _update_time(self, dt):
        self.time_text = datetime.datetime.now().strftime('%I:%M:%S %p')
