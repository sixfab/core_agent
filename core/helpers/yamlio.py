
import yaml
import os.path

ENV_PATH = "/opt/sixfab/.env.yaml"
USER_FOLDER_PATH =  os.path.expanduser("~")
CORE_FOLDER_PATH = USER_FOLDER_PATH + "/.core/"
SYSTEM_PATH = CORE_FOLDER_PATH + "system.yaml"
BULK_CACHE= f"{USER_FOLDER_PATH}/.core/bulk.yaml"

def read_yaml_all(file):
    with open(file) as f:
        data = yaml.safe_load(f)
        return data or {}

def write_yaml_all(file, items, clear = True):
    if clear == True:
        with open(file, 'w') as f:
            yaml.dump(items, f, default_flow_style=False)
    else:
        with open(file, 'a') as f:
            yaml.dump(items, f, default_flow_style=False)
