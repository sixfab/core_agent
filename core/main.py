import json
import time
import paho.mqtt.client as mqtt

from uuid import uuid4
from threading import Thread, Lock
from logging import Logger, NOTSET
from base64 import b64decode, b64encode

from .modules import pty
from .helpers import network, logger
from .modules import monitoring, updater

MQTT_HOST = "mqtt.connect.sixfab.com"
MQTT_PORT = 1883


class Agent(object):
    def __init__(
        self,
        configs: dict,
        lwt: bool = True,
        enable_feeder: bool = True,
    ):
        self.configs = configs["core"]
        self.token = self.configs["token"]
        self.logger = logger.initialize_logger()
        self.configs["logger"] = self.logger
        self.is_connected = False
        self.monitoring_initialized = False

        self.lock_thread = Lock()
        self.terminal = pty.PTYController(self.configs)

        client = mqtt.Client(client_id=f"device/{self.token}")
        self.client = client

        client.username_pw_set(self.token, "sixfab")
        client.user_data_set(self.token)

        client.will_set(
            "device/{}/connected".format(self.token),
            1,
            retain=True,
        )

        client.on_connect = self.__on_connect
        client.on_message = self.__on_message
        client.on_disconnect = self.__on_disconnect
        client.on_log = self.__on_log

    def loop(self):
        ping_addr = "power.sixfab.com"
        ping_host = None

        while True:
            if network.is_network_available(ping_host or ping_addr):

                if not ping_host:
                    ping_host = network.get_host_by_addr(ping_addr)

                if not self.is_connected:
                    self.logger.debug("[LOOP] Network online, starting mqtt agent")
                    self.client.connect(
                        self.configs.get("MQTT_HOST", MQTT_HOST),
                        MQTT_PORT,
                        keepalive=30,
                    )
                    self.client.loop_start()
                    self.is_connected = True

                time.sleep(30)
            else:
                if ping_host:
                    ping_host = None
                    continue

                if self.is_connected:
                    self.logger.debug("[LOOP] Network ofline, blocking mqtt agent")
                    self.is_connected = False
                    self.client.loop_stop()
                    self.client.disconnect()
                time.sleep(10)

    def __on_message(self, client, userdata, msg):
        topic = msg.topic.split("/")[-1]
        payload = msg.payload.decode()

        is_connection_status_message = topic == "connected"
        is_signaling_message = msg.topic.startswith("signaling")
        is_directive = topic == "directives"


        if is_signaling_message:
            self.logger.debug("[SIGNALING] Got request, creating response")

            payload = json.loads(payload)
            requestID = payload["id"]
            payload = payload["payload"]

            answer = self.terminal.request(b64decode(payload))

            client.publish(
                f"signaling/{self.token}/response",
                json.dumps({
                    "id": requestID,
                    "payload": b64encode(answer).decode()
                }),
            )

            self.logger.debug("[SIGNALING] Sent response")


        elif is_connection_status_message and payload == "0":
            self.logger.warning(
                "[CONNECTION] The broker assuming I'm offline, I'm updating my status"
            )
            self.client.publish(f"device/{self.token}/connected", 1, retain=True)

            return

        elif is_directive:
            try:
                payload = json.loads(payload)
            except:
                return

            command = payload.get("command")
            data = payload.get("data", {})

            if not command:
                return

            if command == "update":
                Thread(target=updater.update_modules, args=(self.configs, self.client)).start()

    def __on_connect(self, client, userdata, flags, rc):
        print("Connected to the server")
        self.is_connected = True

        if not self.monitoring_initialized:
            Thread(target=monitoring.main, args=(self.client, self.configs)).start()
            self.monitoring_initialized = True

        self.client.subscribe(f"device/{self.token}/directives")
        self.client.subscribe(f"device/{self.token}/connected")
        self.client.subscribe(f"signaling/{self.token}/request")
        self.client.publish(
            f"device/{self.token}/connected",
            1,
            retain=True,
        )

    def __on_disconnect(self, client, userdata, rc):
        print("Disconnected. Result Code: {rc}".format(rc=rc))
        self.is_connected = False

    def __on_log(self, mqttc, userdata, level, string):
        print(string.replace(userdata, "...censored_uuid..."))
