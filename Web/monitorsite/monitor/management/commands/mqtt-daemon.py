import re
import json
import asyncio
from datetime import datetime, timezone
from paho.mqtt.client import Client
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.conf import settings
from monitor.models import *


MQTT_BROKER_RE_PATTERN = (r'\$sys\/broker\/connection\/'
                          r'(?P<device_id>[0-9a-f]*)_broker/state')

HOURLY_USAGE_RE_PATTERN = r'devices\/(?P<device_id>[0-9a-f]*)\/monitor\/usage\/last_hour'


def generate_averages_topic(device_id):
    return f'devices/{device_id}/monitor/average'


class Command(BaseCommand):
    help = 'Long-running Daemon Process to Integrate MQTT Messages with Django'

    def _create_default_user_if_needed(self):
        # make sure the user account exists that holds all new devices
        try:
            User.objects.get(username=settings.DEFAULT_USER)
        except User.DoesNotExist:
            print("Creating user {} to own new Monitor devices".format(
                settings.DEFAULT_USER))
            new_user = User()
            new_user.username = settings.DEFAULT_USER
            new_user.password = "123456"
            new_user.is_active = False
            new_user.save()

    def _on_connect(self, client, userdata, flags, rc):
        self.client.message_callback_add('$SYS/broker/connection/+/state',
                                         self._on_broker_bridges)
        self.client.subscribe('$SYS/broker/connection/+/state')
        self.client.message_callback_add('devices/+/monitor/usage/last_hour',
                                         self._on_hourly_usage)
        self.client.subscribe('devices/+/monitor/usage/last_hour')

    def _create_mqtt_client_and_loop(self):
        self.client = Client()
        self.client.on_connect = self._on_connect
        self.client.connect('localhost', port=50001)
        self.client.loop_start()

    def _on_new_devices(self, client, userdata, message):
        print("RECV: '{}' on '{}'".format(message.payload, message.topic))
        # message payload has to treated as type "bytes" in Python 3
        if message.payload == b'1':
            # broker connected
            results = re.search(MQTT_BROKER_RE_PATTERN, message.topic.lower())
            device_id = results.group('device_id')
            try:
                device = Monitor.objects.get(device_id=device_id)
                print("Found {}".format(device))
                device.publish_average_msg(datetime.now(timezone.utc).hour)
            except Monitor.DoesNotExist:
                # this is a new device - create new record for it
                new_device = Monitor(device_id=device_id)
                uname = settings.DEFAULT_USER
                new_device.user = User.objects.get(username=uname)
                new_device.save()
                print("Created {}".format(new_device))
                # send association MQTT message
                new_device.publish_unassociated_msg()

    def _on_broker_bridges(self, client, userdata, message):
        self._on_new_devices(client, userdata, message)
        self._on_connection_events(client, userdata, message)

    def _on_connection_events(self, client, userdata, message):
        results = re.search(MQTT_BROKER_RE_PATTERN, message.topic.lower())
        device_id = results.group('device_id')
        connection_state = 'unknown'
        if message.payload == b'1':
            print("DEVICE {} CONNECTED".format(device_id))
            connection_state = 'Connected'
        else:
            print("DEVICE {} DISCONNECTED".format(device_id))
            connection_state = 'Disconnected'

    def _on_hourly_usage(self, client, userdata, message):
        results = re.search(HOURLY_USAGE_RE_PATTERN, message.topic.lower())
        device_id = results.group('device_id')

        last_hour = json.loads(message.payload.decode('utf-8'))

        if ('hour' not in last_hour) or ('wattage' not in last_hour):
            return

        try:
            monitor = Monitor.objects.get(device_id=device_id)
            print(f"Updating hour average for device {monitor}")
            monitor.update_averages(last_hour['hour'], last_hour['wattage'])
        except Monitor.DoesNotExist:
            print(f"Invalid device ID (topic: {message.topic})")

    async def _handle_averages(self):
        last_poll = datetime.now(timezone.utc)
        while True:
            print('Polling...')
            current_poll = datetime.now(timezone.utc)
            if current_poll.hour != last_poll.hour:
                for monitor in Monitor.objects.all():
                    if monitor.user == User.objects.get(username=settings.DEFAULT_USER):
                        continue
                    print(f'Publishing hourly average for device {monitor}')
                    monitor.publish_average_msg(current_poll.hour)

            last_poll = current_poll
            await asyncio.sleep(180)

    def handle(self, *args, **options):
        self._create_default_user_if_needed()
        self._create_mqtt_client_and_loop()
        asyncio.run(self._handle_averages())
