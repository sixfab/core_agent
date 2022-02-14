import json
import time
import paho.mqtt.client as mqtt

from uuid import uuid4
from threading import Thread, Lock
from logging import Logger, NOTSET
from base64 import b64decode, b64encode

from .modules import pty
from .helpers import network, logger
from .modules import monitoring, maintenance, configurator, fixer, bulk
from .shared import config_request_cache

MQTT_HOST = "mqtt.connect.sixfab.com"
MQTT_PORT = 8883


class Agent(object):
    def __init__(
        self,
        configs: dict,
    ):
        configs["core"]["callbacks"] = []
        self.configs = configs["core"]
        self.logger = logger.initialize_logger()
        self.configs["logger"] = self.logger

        bulk.check_bulk_deployment(self.configs)

        self.token = self.configs["token"]
        self.monitoring_thread = None

        self.connection_sequence = 0
        self.connection_timestamp = 0
        self.is_fresh_connection = True
        self.used_last_connection_sequence = True

        self.subscriptions = {} # {mid: {topic: str, qos: int} } pair

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

        self.initialize_death_certificate(initial=True)
        client.tls_set()

        client.on_connect = self.__on_connect
        client.on_message = self.__on_message
        client.on_disconnect = self.__on_disconnect
        client.on_log = self.__on_log
        client.on_subscribe = self.__on_subscribe
        client.on_publish = self.__on_publish

    def loop(self):
        while True:
            try:
                self.client.connect(
                    self.configs.get("MQTT_HOST", MQTT_HOST),
                    MQTT_PORT,
                    keepalive=60
                )
                break
            except:
                self.logger.error("Couldn't connect, retrying in 5 seconds")
                time.sleep(5)

        self.client.loop_forever()

    def publish_message(self, topic, message, qos=2, retain=True):
        try:
            response = self.client.publish(
                topic,
                json.dumps(message),
                qos=qos,
                retain=retain,
            )
        except Exception as error:
            self.logger.error("Publish failed: %s", error)
            time.sleep(0.1)
            self.logger.debug("Publish retrying...")
            self.publish_message(topic, message, qos, retain)
        else:
            if response.rc == 0:
                self.logger.info("Publish Success --> mid: %s, rc: %s", response.mid, response.rc)
                return

            self.logger.error("Publish failed --> mid: %s, rc: %s", response.mid, response.rc)
            time.sleep(0.1)
            self.logger.debug("Publish retrying...")
            self.publish_message(topic, message, qos, retain)

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
                self.publish_message(
                    f"signaling/{self.token}/response",
                    {
                    "id": requestID,
                    "payload": b64encode(answer).decode()
                    },
                    qos=0,
                    retain=0
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

    def increase_connection_sequence(self):
        """
        Increases the connection sequence. This is used to identify the connection.
        Reset to zero if reached to 255.
        """
        if self.connection_sequence == 255:
            self.connection_sequence = 0
        else:
            self.connection_sequence += 1

        return self.connection_sequence

    def initialize_death_certificate(self, is_reconnect=False, initial=False):
        if not self.used_last_connection_sequence:
            self.logger.debug("Didn't used last updated connection sequence yet, skipping")
            return

        if is_reconnect:
            self.is_fresh_connection = False

        if not initial:
            self.increase_connection_sequence()

        self.connection_timestamp = int(time.time())
        self.logger.info(
            "Updated LWT, fresh=%s, connection_sequence=%s, timestamp=%s", 
            self.is_fresh_connection, 
            self.connection_sequence,
            self.connection_timestamp
        )

        testament_message = json.dumps(dict(
            seq=self.connection_sequence,
            ts=self.connection_timestamp
        ))

        self.client.will_set(
            f"device/{self.token}/death",
            testament_message,
            qos=2,
            retain=True,
        )

        self.used_last_connection_sequence = False

    def publish_birth_certificate(self):
        connect_message = {
            "seq": self.connection_sequence,
            "ts": self.connection_timestamp
        }

        if self.is_fresh_connection:
            connect_message["fresh"] = True

        self.publish_message(
            f"device/{self.token}/birth",
            connect_message,
            qos=2,
            retain=True,
        )

        self.used_last_connection_sequence = True
        self.logger.info("Sent birth certificate")

    def __on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.subscriptions = {}
            self.logger.info("Connected to the broker, rc=%s", rc)

            self.__subscribe_to_topic(f"device/{self.token}/directives", qos=1)
            self.__subscribe_to_topic(f"signaling/{self.token}/request", qos=1)

            self.publish_birth_certificate()

    def __on_subscribe(self, client, userdata, mid, granted_qos) -> None:
        is_subscription_successful = granted_qos[0] != 128

        if is_subscription_successful:
            self.logger.info("Subscribed to MQTT topic: %s", self.subscriptions[mid]["topic"])
            self.subscriptions.pop(mid, None)
            return

        self.logger.warning("Subscription to MQTT topic failed: %s  RETRYING", self.subscriptions[mid]["topic"])
        topic = self.subscriptions[mid]["topic"]
        qos = self.subscriptions[mid]["qos"]
        
        self.subscriptions.pop(mid, None)

        self.__subscribe_to_topic(topic, qos)

    def __subscribe_to_topic(self, topic, qos=0):
        """
        Send SUBSCRIPTION package to mqtt broker and cache the mid, topic pair
        """
        result, mid = self.client.subscribe(topic, qos=qos)
        
        if result != 0:
            self.__subscribe_to_topic(topic, qos)
            return

        self.subscriptions[mid] = {
            "topic": topic,
            "qos": qos,
        }

        self.logger.info("Sent SUBSCRIPTION mid=%s, topic=%s ", mid, topic)
    
    def __on_publish(self, client, userdata, mid):
        # self.logger.info("On_publish: %s", mid)
        pass

    def __on_disconnect(self, client, userdata, rc):
        self.logger.warning("Disconnected from the broker, rc=%s", rc)
        self.initialize_death_certificate(is_reconnect=True)

    def __on_log(self, client, userdata, level, string):
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
