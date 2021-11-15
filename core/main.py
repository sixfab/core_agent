import json
import time
import paho.mqtt.client as mqtt

from uuid import uuid4
from threading import Thread, Lock
from logging import Logger, NOTSET
from base64 import b64decode, b64encode

from .modules import pty
from .helpers import network, logger
from .modules import monitoring, maintenance, configurator, fixer
from .shared import config_request_cache

MQTT_HOST = "mqtt.connect.sixfab.com"
MQTT_PORT = 1883


class Agent(object):
    def __init__(
        self,
        configs: dict,
        lwt: bool = True,
        enable_feeder: bool = True,
    ):
        configs["core"]["callbacks"] = []
        self.configs = configs["core"]
        self.token = self.configs["token"]
        self.logger = logger.initialize_logger()
        self.configs["logger"] = self.logger
        self.monitoring_thread = None
        self.connection_id = 1
        self.first_connection_message_recieved = False

        self.lock_thread = Lock()

        client = mqtt.Client(
            client_id=f"device/{self.token}",
            clean_session=False
            )
        self.client = client
        self.configs["mqtt_client"] = self.client

        self.terminal = pty.PTYController(self.configs)

        client.username_pw_set(self.token, "sixfab")
        client.user_data_set(self.token)

        self.set_testament()

        client.on_connect = self.__on_connect
        client.on_message = self.__on_message
        client.on_disconnect = self.__on_disconnect
        client.on_log = self.__on_log

    def loop(self):
        while True:
            try:
                self.client.connect(
                    self.configs.get("MQTT_HOST", MQTT_HOST),
                    MQTT_PORT,
                    keepalive=10
                )
                break
            except:
                self.logger.error("Couldn't connect, retrying in 5 seconds")
                time.sleep(5)

        self.client.loop_forever()


    def __on_message(self, client, userdata, msg):
        for function in self.configs["callbacks"]:
            try:
                function(client, userdata, msg)
            except:
                pass
                
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

            if answer:
                client.publish(
                    f"signaling/{self.token}/response",
                    json.dumps({
                        "id": requestID,
                        "payload": b64encode(answer).decode()
                    }),
                )

                self.logger.debug("[SIGNALING] Sent response")
            else:
                self.logger.error("[SIGNALING] An error occured during signaling, couldn't create answer")

        elif is_directive:
            try:
                payload = json.loads(payload)
            except:
                return

            command = payload.get("command")
            data = payload.get("data", {})

            if not command:
                return

            if command == "maintenance":
                Thread(target=maintenance.main, args=(data, self.configs, self.client)).start()
            elif command == "config":
                configurator.create_configuration_request(data, client, self.configs)
            elif command == "ack":
                if data in config_request_cache.values():
                    request_id = data
                    configurator.delete_configuration_request(request_id, client, self.configs)

    
    def set_testament(self, is_reconnection=False):
        if is_reconnection:
            self.connection_id += 1

        self.logger.info(f"Setting testament, is_reconnection={is_reconnection}, connection_id={self.connection_id}")

        testament_message = json.dumps(dict(
            v=0,
            id=self.connection_id
        ))

        self.client.will_set(
            "device/{}/connected".format(self.token),
            testament_message,
            qos=2,
            retain=True,
        )


    def __on_connect(self, client, userdata, flags, rc):
        self.logger.info("Connected to the broker")

        self.client.subscribe(f"device/{self.token}/directives", qos=1)
        self.client.subscribe(f"signaling/{self.token}/request", qos=1)


        connect_message = json.dumps(dict(
            ts=time.time(),
            v=1,
            id=self.connection_id
        ))

        self.client.publish(
            f"device/{self.token}/connected",
            connect_message,
            qos=2,
            retain=True,
        )


    def __on_disconnect(self, client, userdata, rc):
        print("Disconnected. Result Code: {rc}".format(rc=rc))
        self.logger.warning("Disconnected from the broker, rc=", rc)
        self.set_testament(is_reconnection=True)

    def __on_log(self, mqttc, userdata, level, string):
        #print(string.replace(userdata, "...censored_uuid..."))
        self.__check_monitoring_thread() # to keep monitoring thread alive continiously


    def __check_monitoring_thread(self):
        if self.monitoring_thread == None:
            self.logger.warning("[MONITORING] Monitoring thread not initialized, initializing")
            self.monitoring_thread = Thread(target=monitoring.main, args=(self.client, self.configs))

        elif self.monitoring_thread.is_alive():
            return

        if not self.monitoring_thread.is_alive():
            try:
                self.logger.warning("[MONITORING] Starting monitoring thread")
                self.monitoring_thread.start()
            except RuntimeError:
                self.logger.warning("[MONITORING] Couldn't start the thread, re-initializing and starting again...")
                self.monitoring_thread = Thread(target=monitoring.main, args=(self.client, self.configs))
                self.monitoring_thread.start()
