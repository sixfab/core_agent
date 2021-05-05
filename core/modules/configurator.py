import os
import yaml
import json
from time import time
from core.shared import config_request_cache

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

CONFIGS_PATH = "/home/sixfab/.core/configs/request"

def _check_configurations_folder():
    paths = ["/home/sixfab", "/home/sixfab/.core", "/home/sixfab/.core/configs", "/home/sixfab/.core/configs/request"]

    for path in paths:
        if not os.path.exists(path):
            os.mkdir(path)


def create_configuration_request(data, mqtt_client, configs):
    _check_configurations_folder()

    logger = configs["logger"]
    request_id = data.get("id", None)
    timestamp = data.get("ts", int(time()))

    if not request_id:
        logger.error(f"[CONFIGURATOR] Got a configuration request without id")

    logger.info(
        f"[CONFIGURATOR] Creating configuration request, request_id={request_id}"
    )

    with open(f"{CONFIGS_PATH}/config_request_{timestamp}.yaml", "w+") as request_file:
        request_file.write(
            yaml.dump(
                {
                    "ts": timestamp,
                    "id": request_id,
                    "configs": data.get("configs", {}),
                },
                Dumper=Dumper,
            )
        )

    mqtt_client.publish(
        f"device/{configs['token']}/hive", 
        json.dumps({
            "type": "config",
            "data": {
                "id": request_id,
                "status": "sent"
            }
        })
    )


    logger.info(
        f"[CONFIGURATOR] Created configuration request, request_id={request_id}"
    )
    

def delete_configuration_request(request_id, mqtt_client, configs):
    logger = configs["logger"]

    logger.info("[CONFIGURATOR] Deleting configuration request which completed")

    request_file_name = None

    for file_name, _request_id in config_request_cache.items():
        if request_id == _request_id:
            request_file_name = file_name

    if not request_file_name:
        logger.error(f"[CONFIGURATOR] Couldn't find configuration request file for request_id={request_id}")

    if not os.path.exists(f"{CONFIGS_PATH}/{request_file_name}"):
        logger.error(f"[CONFIGURATOR] Couldn't find configuration request file for file_name={request_file_name}")

    os.remove(f"{CONFIGS_PATH}/{request_file_name}")
    logger.info(f"[CONFIGURATOR] Deleted configuration request file, file_name={request_file_name}")
