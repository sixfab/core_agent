import os.path
import yaml


ENV_PATH = "/opt/sixfab/.env.yaml"
USER_FOLDER_PATH =  os.path.expanduser("~")
CORE_FOLDER_PATH = f"{USER_FOLDER_PATH}/.core"
SYSTEM_PATH = f"{CORE_FOLDER_PATH}/system.yaml"
MONITOR_PATH = f"{CORE_FOLDER_PATH}/monitor.yaml"
GEOLOCATION_PATH = f"{CORE_FOLDER_PATH}/geolocation.yaml"
BULK_CACHE= f"{CORE_FOLDER_PATH}/bulk.yaml"
CONFIG_FOLDER_PATH = f"{CORE_FOLDER_PATH}/configs"
CONFIG_PATH = f"{CONFIG_FOLDER_PATH}/config.yaml"
CONFIG_REQUEST_PATH = f"{CONFIG_FOLDER_PATH}/request"


def read_yaml_all(file):
    with open(file) as yaml_file:
        data = yaml.safe_load(yaml_file)
        return data or {}


def write_yaml_all(file, items, clear = True):
    if clear is True:
        with open(file, 'w') as yaml_file:
            yaml.dump(items, yaml_file, default_flow_style=False)
    else:
        with open(file, 'a') as yaml_file:
            yaml.dump(items, yaml_file, default_flow_style=False)
