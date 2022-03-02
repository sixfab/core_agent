import os
import yaml
import json
import time
from uuid import uuid4

from core.__version__ import version
from core.shared import config_request_cache

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


CONTROL_INTERVAL=30
message_cache = {} # key, value pattern for each mid, message_body
USER_PATH = os.path.expanduser("~")
SYSTEM_PATH = f"{USER_PATH}/.core/system.yaml"
MONITOR_PATH = f"{USER_PATH}/.core/monitor.yaml"
CONFIG_PATH = f"{USER_PATH}/.core/configs/config.yaml"
CONFIGS_REQUEST_PATH = f"{USER_PATH}/.core/configs/request"
GEOLOCATION_PATH = f"{USER_PATH}/.core/geolocation.yaml"


def _check_configuration_requests(mqtt_client, configs):
    logger = configs["logger"]

    if not os.path.exists(CONFIGS_REQUEST_PATH):
        logger.debug("[CONFIGURATOR] Configs folder not found, skip for now")
        return

    files = os.listdir(CONFIGS_REQUEST_PATH)

    for file_name in files:
        if not file_name.endswith("_done"):
            continue

        if file_name in config_request_cache:
            request_id = config_request_cache[file_name]
        else:
            file_content = open(f"{CONFIGS_REQUEST_PATH}/{file_name}")
            request_id = yaml.load(file_content, Loader=Loader)["id"]

            config_request_cache[file_name] = request_id

        logger.info(f"[CONFIGURATOR] Sending status update to cloud, status=received, request_id={request_id}")

        mqtt_client.publish(
            f"device/{configs['token']}/hive", 
            json.dumps({
                "type": "config",
                "data": {
                    "id": request_id,
                    "status": "received"
                }
            })
        )

def loop(mqttClient, configs):
    logger = configs["logger"]
    last_monitoring_data = {}
    last_system_data = {}
    last_config_data = {}
    last_geolocation_data = {}


    def callback(client, userdata, msg):
        topic = msg.topic.split("/")[-1]
        payload = msg.payload.decode()

        if topic == "directives":
            try:
                payload = json.loads(payload)
            except:
                return

            if payload.get("command", None) == "ack":
                mid = payload.get("data")

                if not mid:
                    return

                data = message_cache[mid]

                if data["type"] == "data_monitoring":
                    data["data"].pop("timestamp", None)
                    data["data"].pop("last_update", None)
                    last_monitoring_data.update(data["data"])
                    logger.debug("Updated last monitoring data")

                elif data["type"] == "data_system":
                    last_system_data.update(data["data"])
                    logger.debug("Updated last system data")

                elif data["type"] == "data_config":
                    last_config_data.update(data["data"])
                    logger.debug("Updated last config data")

                elif data["type"] == "data_geolocation":
                    data["data"].pop("last_update", None)
                    last_geolocation_data.update(data["data"])
                    logger.debug("Updated last geolocation data")



    configs["callbacks"].append(callback)


    while True:
        if not mqttClient.is_connected():
            logger.debug("Not connected to MQTT broker, ignoring monitoring thread. Retrying in 10 secs")
            time.sleep(10)
            continue

        # CHECK STATUS OF CONFIGURATION REQUESTS
        try:
            _check_configuration_requests(mqttClient, configs)
        except:
            logger.exception("[MONITORING] Raised an exception during configuration monitoring")


        # MONITOR DATA
        new_monitoring_data = None
        try:
            with open(MONITOR_PATH) as monitor_data:
                new_monitoring_data = yaml.load(monitor_data, Loader=Loader) or {}
        except Exception:
            logger.exception("Monitoring data not exists!")

        if new_monitoring_data:
            new_monitoring_data.pop("last_update", None)
            data_to_send = {}

            for key, value in new_monitoring_data.items():
                last_value = last_monitoring_data.get(key, "N/A")

                if value != last_value:
                    data_to_send[key] = value

            if data_to_send:
                mid = uuid4().hex[-4:]

                message_body = dict(
                    type="data_monitoring",
                    data=data_to_send,
                    mid=mid
                )

                message_response = mqttClient.publish(
                    f"device/{configs['token']}/hive",
                    json.dumps(message_body)
                )

                message_cache[mid] = message_body

                logger.debug("Sending new monitoring data")
            else:
                logger.debug("Skipping monitoring data, couldn't find any changes.")


        # SYSTEM DATA
        new_system_data = None
        try:
            with open(SYSTEM_PATH) as system_data:
                new_system_data = yaml.load(system_data, Loader=Loader) or {}
        except Exception:
            logger.exception("System data not exists!")

        if new_system_data:
            new_system_data["agent_version"] = version
            new_system_data.pop("last_update", None)
    
            data_to_send = {}
    
            for key, value in new_system_data.items():
                last_value = last_system_data.get(key, "N/A")

                if value != last_value:
                    data_to_send[key] = value
    
    
            if data_to_send:
                mid = uuid4().hex[-4:]

                message_body = dict(
                    type="data_system",
                    data=data_to_send,
                    mid=mid
                )

                message_response = mqttClient.publish(
                    f"device/{configs['token']}/hive", 
                    json.dumps(message_body)
                )

                message_cache[mid] = message_body
    
                logger.debug("Sending new system data")
            else:
                logger.debug("Skipping system data, couldn't find any changes.")


        # CONFIG DATA
        new_config_data = None
        try:
            with open(CONFIG_PATH) as config_data:
                new_config_data = yaml.load(config_data, Loader=Loader) or {}
        except Exception:
            logger.exception("Config data not exists!")

        if new_config_data:
            data_to_send = {}
    
            for key, value in new_config_data.items():
                last_value = last_config_data.get(key, "N/A")

                if value != last_value:
                    data_to_send[key] = value
    
    
            if data_to_send:
                mid = uuid4().hex[-4:]

                message_body = dict(
                    type="data_config",
                    data=data_to_send,
                    mid=mid
                )

                message_response = mqttClient.publish(
                    f"device/{configs['token']}/hive", 
                    json.dumps(message_body)
                )

                message_cache[mid] = message_body
    
                logger.debug("Sending new config data")
            else:
                logger.debug("Skipping config data, couldn't find any changes.")


        # GEOLOCATION DATA
        new_geolocation_data = None
        try:
            with open(GEOLOCATION_PATH) as geolocation_data:
                new_geolocation_data = yaml.load(geolocation_data, Loader=Loader) or {}
        except Exception:
            logger.exception("Geolocation data not exists!")

        if new_geolocation_data:
            new_geolocation_data.pop("last_update", None)
            data_to_send = {}

            for key, value in new_geolocation_data.items():
                last_value = last_geolocation_data.get(key, "N/A")

                if value != last_value:
                    data_to_send[key] = value

            if data_to_send:
                mid = uuid4().hex[-4:]

                message_body = dict(
                    type="data_geolocation",
                    data=data_to_send,
                    mid=mid
                )

                message_response = mqttClient.publish(
                    f"device/{configs['token']}/hive",
                    json.dumps(message_body)
                )
                print(message_body, message_response)
                message_cache[mid] = message_body

                logger.debug("Sending new geolocation data")
            else:
                logger.debug("Skipping geolocation data, couldn't find any changes.")


        time.sleep(CONTROL_INTERVAL)


def main(mqttClient, configs):
    while True:
        try:
            loop(mqttClient, configs)
        except Exception as e:
            configs["logger"].exception("[MONITORING] Raised an error from monitoring thread")