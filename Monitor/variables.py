import paho.mqtt.client

DEVICE_ID_FILENAME = '/sys/class/net/eth0/address'

# MQTT Topic Names
TOPIC_CURRENT_USAGE = "monitor/usage"
TOPIC_ENABLE_OUTLETS = "monitor/set_enabled"
TOPIC_LAMP_CONFIG = "lamp/set_config"

def get_device_id():
    mac_addr = open(DEVICE_ID_FILENAME).read().strip()
    return mac_addr.replace(':', '')


def client_state_topic(client_id):
    return f'monitor/connection/{client_id}/state'


def broker_bridge_connection_topic():
    device_id = get_device_id()
    return f'$SYS/broker/connection/{device_id}_broker/state'


# MQTT Broker Connection info
MQTT_VERSION = paho.mqtt.client.MQTTv311
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_BROKER_KEEP_ALIVE_SECS = 60
