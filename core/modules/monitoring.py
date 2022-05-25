import os
import time
import json
from uuid import uuid4

from core.__version__ import version
from core.shared import config_request_cache
from core.helpers.yamlio import read_yaml_all
from core.helpers.yamlio import(
    SYSTEM_PATH,
    MONITOR_PATH,
    CONFIG_PATH,
    CONFIG_REQUEST_PATH,
    GEOLOCATION_PATH,
    DIAG_PATH
)


CONTROL_INTERVAL=30
message_cache = {} # key, value pattern for each mid, message_body


def _check_configuration_requests(mqtt_client, configs):
    logger = configs["logger"]

    if not os.path.exists(CONFIG_REQUEST_PATH):
        logger.debug("[CONFIGURATOR] Configs folder not found, skip for now")
        return

    files = os.listdir(CONFIG_REQUEST_PATH)

    for file_name in files:
        if not file_name.endswith("_done"):
            continue

        if file_name in config_request_cache:
            request_id = config_request_cache[file_name]
        else:
            file_path = f"{CONFIG_REQUEST_PATH}/{file_name}"
            request_id = read_yaml_all(file_path)["id"]
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


def check_file_and_update_cloud(
    file_path,
    last_data,
    data_type,
    mqtt_client,
    configs,
    only_changed_values = True
    ):
    """
        parameters:
            file_path: path of file
            last_data: last cached/sent data
            data_type: type of data, for example data_system or data_monitoring
            mqtt_client: main mqtt class
            configs: global configs object
            only_changed_values: If true, agent will send only changed values. 
                                 Otherwise it will send whole data when a value 
                                 changed from data. 
    """

    logger = configs["logger"]

    mqtt_channel = f"device/{configs['token']}/hive"
    new_data = None

    if data_type == "data_diagnostic" and not os.path.exists(file_path):
        return

    try:
        new_data = read_yaml_all(file_path)
    except Exception:
        logger.exception("%s not exists!", data_type)

    if new_data:
        if data_type == "data_system":
            new_data["agent_version"] = version
        new_data.pop("last_update", None)
        data_to_send = {}

        if only_changed_values:
            for key, value in new_data.items():
                last_value = last_data.get(key, "N/A")

                if value != last_value:
                    data_to_send[key] = value

        else:
            data_to_send = new_data

        if data_to_send:
            mid = uuid4().hex[-4:]

            message_body = dict(
                type=data_type,
                data=data_to_send,
                mid=mid
            )

            message_response = mqtt_client.publish(
                mqtt_channel,
                json.dumps(message_body)
            )

            message_cache[mid] = message_body

            logger.debug("Sending new %s : %s, only_changed_values=%s", data_type, message_response, only_changed_values)
        else:
            logger.debug("Skipping %s, couldn't find any changes.", data_type)


def loop(mqttClient, configs):
    logger = configs["logger"]
    last_monitoring_data = {}
    last_system_data = {}
    last_config_data = {}
    last_geolocation_data = {}
    last_diagnostic_data = {}


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

                elif data["type"] == "data_diagnostic":
                    data["data"].pop("last_update", None)
                    last_diagnostic_data.update(data["data"])
                    logger.debug("Updated last diagnostic data")


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
        check_file_and_update_cloud(
            file_path=MONITOR_PATH,
            last_data=last_monitoring_data,
            data_type="data_monitoring",
            mqtt_client=mqttClient,
            configs=configs
        )

        # SYSTEM DATA
        check_file_and_update_cloud(
            file_path=SYSTEM_PATH,
            last_data=last_system_data,
            data_type="data_system",
            mqtt_client=mqttClient,
            configs=configs
        )

        # CONFIG DATA
        check_file_and_update_cloud(
            file_path=CONFIG_PATH,
            last_data=last_config_data,
            data_type="data_config",
            mqtt_client=mqttClient,
            configs=configs
        )

        # GEOLOCATION DATA
        check_file_and_update_cloud(
            file_path=GEOLOCATION_PATH,
            last_data=last_geolocation_data,
            data_type="data_geolocation",
            mqtt_client=mqttClient,
            configs=configs,
            only_changed_values=False
        )

        # DIAGNOSTIC DATA
        check_file_and_update_cloud(
            file_path=DIAG_PATH,
            last_data=last_diagnostic_data,
            data_type="data_diagnostic",
            mqtt_client=mqttClient,
            configs=configs,
            only_changed_values=False
        )

        time.sleep(CONTROL_INTERVAL)

def main(mqttClient, configs):
    while True:
        try:
            loop(mqttClient, configs)
        except:
            configs["logger"].exception("[MONITORING] Raised an error from monitoring thread")
