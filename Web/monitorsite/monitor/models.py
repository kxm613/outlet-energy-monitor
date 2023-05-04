from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from uuid import uuid4
import json
import paho.mqtt.publish

# Create your models here.
DEFAULT_USER = 'parked_device_user'


def get_parked_user():
    return get_user_model().objects.get_or_create(username=DEFAULT_USER)[0]


def generate_association_code():
    return uuid4().hex


def default_averages():
    return { "hours": [0] * 24 }

class Monitor(models.Model):
    name = models.CharField(max_length=50, default="New Monitor")
    device_id = models.CharField(db_index=True,
                                 max_length=12,
                                 primary_key=True)
    user = models.ForeignKey(User, db_index=True,
                             on_delete=models.SET(get_parked_user))
    association_code = models.CharField(max_length=32, unique=True,
                                        default=generate_association_code)
    created_at = models.DateTimeField(auto_now_add=True)

    averages = models.JSONField(null=True, default=default_averages)

    def __str__(self):
        return "{}: {}".format(self.device_id, self.name)

    def update_averages(self, hour, wattage):
        if hour not in range(24):
            return

        if self.averages["hours"][hour] == 0:
            self.averages["hours"][hour] == wattage
        else:
            # calculating the new average as an exponential recency weighted average (ERWA)
            # This favors more recent data, which makes sense for energy usage, and allows us
            # to save just the average instead of a large amount of historical data.
            new_erwa = self.averages["hours"][hour] * .8 + wattage * .2
            self.averages["hours"][hour] = new_erwa
            self.save()

    def _generate_averages_topic(self):
        return f'devices/{self.device_id}/monitor/average'

    def publish_average_msg(self, hour):
        average_msg = { "hour": hour, "wattage": self.averages["hours"][hour] }
        paho.mqtt.publish.single(self._generate_averages_topic(),
                                 json.dumps(average_msg),
                                 qos=1,
                                 retain=True,
                                 port=50001)

    def _generate_device_association_topic(self):
        return 'devices/{}/lamp/associated'.format(self.device_id)

    def publish_unassociated_msg(self):
        # send association MQTT message
        assoc_msg = {}
        assoc_msg['associated'] = False
        assoc_msg['code'] = self.association_code
        paho.mqtt.publish.single(
            self._generate_device_association_topic(),
            json.dumps(assoc_msg),
            qos=2,
            retain=True,
            port=50001,
            )

    def associate_and_publish_associated_msg(self,  user):
        # update Lampi instance with new user
        self.user = user
        self.save()
        # publish associated message
        assoc_msg = {}
        assoc_msg['associated'] = True
        paho.mqtt.publish.single(
            self._generate_device_association_topic(),
            json.dumps(assoc_msg),
            qos=2,
            retain=True,
            port=50001,
            )
