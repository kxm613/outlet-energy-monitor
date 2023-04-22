import platform
from kivy.app import App
from kivy.properties import NumericProperty, AliasProperty, BooleanProperty, StringProperty, DictProperty, ListProperty
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
import json
import os
from paho.mqtt.client import Client
import pigpio
from variables import *
import monitor.ip_info

import colorsys
import datetime
from math import fabs, log10, floor


MQTT_CLIENT_ID = "monitor_ui"


class MonitorApp(App):
    #_updated = False
    #_updatingUI = False

    _outlets = DictProperty({})
    _wattage = NumericProperty(0)
    _difference = NumericProperty(0)
    _diff_color = ListProperty([0.2, 1.0, 0.5])
    
    def _get_outlets(self):
        return self._outlets

    def _set_outlets(self, value):
        self._outlets = value

    def _get_wattage(self):
        return self._wattage

    def _set_wattage(self, value):
        self._wattage = value
    
    def _get_difference(self):
        return self._difference
    
    def _set_difference(self, value):
        self._difference = value

    def _get_color(self):
        return self._diff_color
    
    def _set_color(self, value):
        self._diff_color = value

    def _get_color(self):
        return self._diff_color

    def _get_difference_text(self):
        text_color = '%02x%02x%02x' % tuple(map(lambda x: round(x * 255), colorsys.hsv_to_rgb(*self.diff_color)))
        plus_or_minus = '±' if (self.difference == 0) else ('+' if (self.difference > 0) else '-')

        return f'[color={text_color}]{plus_or_minus} {abs(self.difference):.2f} W[/color]'

    outlets = AliasProperty(_get_outlets, _set_outlets, bind=['_outlets'])
    wattage = AliasProperty(_get_wattage, _set_wattage, bind=['_wattage'])
    difference = AliasProperty(_get_difference, _set_difference, bind=['_difference'])
    diff_color = AliasProperty(_get_color, _set_color, bind=['_diff_color'])
    diff_text = AliasProperty(_get_difference_text, bind=['difference', 'diff_color'])
    time_text = StringProperty('')
    gpio17_pressed = BooleanProperty(False)

    def on_start(self):
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
        
        if 'outlets' in new_state:
            self.outlets = new_state['outlets']

        if 'total_wattage' in new_state:
            self.wattage = self._sig_figures(new_state['total_wattage'])
        if 'difference' in new_state:
            self.difference = new_state['difference']
        if 'diff_color' in new_state:
            self.diff_color = new_state['diff_color']

    def press_callback(self, instance):
        outlet_name = instance.text.split()[0]
        previous_state = self.outlets[outlet_name]['enabled']

        new_state = not previous_state
        self.outlets[outlet_name]['enabled'] = new_state

        message = json.dumps({ 'outlets': { outlet_name: new_state }}).encode('utf-8')
        self.mqtt.publish(TOPIC_ENABLE_OUTLETS, message, qos=1)        

    def _sig_figures(self, x, sig=3):
        if x == 0:
            return 0
        if x < 1:
            sig = sig - 1
        digits = sig - floor(log10(abs(x))) - 1
        return int(round(x)) if digits == 0 else round(x, digits)

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
