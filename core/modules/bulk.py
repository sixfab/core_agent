import time
import json
import os
import requests

from core.helpers.yamlio import (
    read_yaml_all,
    write_yaml_all,
    ENV_PATH,
    BULK_CACHE,
    SYSTEM_PATH
    )


def check_bulk_deployment(configs):
    logger = configs["logger"]

    while True:
        try:
            delay_time = bulk_cache_control()
        except Exception as err:
            logger.info(err)
            delay_time = 60*60*24*365

        if "b_token" in configs:
            logger.info("Bulk deployment started. BToken: %s", configs["b_token"])
            try:
                do_token_exchange(configs)
            except Exception as err:
                logger.error(err)
            else:
                return
        else:
            logger.info("No bulk deployment exist. Continue...")
            return
        time.sleep(delay_time)


def do_token_exchange(configs):

    try:
        system_yaml_data = read_yaml_all(SYSTEM_PATH)
    except Exception as error:
        raise RuntimeError("Error occured while reading yaml file: %s", error)

    sim_iccid = system_yaml_data.get("iccid", None)

    if sim_iccid is None:
        raise RuntimeError("SIM ICCID couldn't find!")

    req={
    'deployment_token': configs["b_token"],
    'iccid': sim_iccid
    }

    api_url = "https://api.sixfab.com/v1/core/deploy"

    if "MQTT_HOST" in configs and "dev" in configs["MQTT_HOST"]:
        # core working on dev environment, change the api host
        api_url = "https://api.sixfab.dev/v1/core/deploy"

    res = requests.post(api_url, data=json.dumps(req))

    if res.status_code == 200 or res.status_code == 201:

        token = res.json()["device_token"]

        try:
            env_yaml_data = read_yaml_all(ENV_PATH)
        except:
            raise RuntimeError("Error occured while reading env.yaml")

        configs["token"] = token
        configs.pop("b_token")

        env_yaml_data["core"]["token"] = token
        env_yaml_data["core"].pop("b_token")

        try:
            write_yaml_all(ENV_PATH, env_yaml_data)
        except:
            raise RuntimeError("Error occured while writing env.yaml")

        if os.path.exists(BULK_CACHE):
            os.remove(BULK_CACHE)

    elif res.status_code == 400:
        raise RuntimeError(res.text)
    elif res.status_code == 422:
        raise RuntimeError(res.text)
    else:
        raise RuntimeError("Unknown error on token exchange!")


def bulk_cache_control():
    try:
        bulk_cache = read_yaml_all(BULK_CACHE)
    except:
        bulk_cache = {}

    if "last_time" not in bulk_cache:
        bulk_cache["last_time"] = time.time()

    try:
        write_yaml_all(BULK_CACHE, bulk_cache)
    except:
        pass

    current_time = time.time()
    last_time = bulk_cache.get("last_time")
    diff = current_time - last_time

    if diff < 60*60:
        return 10
    elif diff > 60*60 and diff < 60*60*24:
        return 60*60
    elif diff > 60*60*24 and diff < 60*60*24*7:
        return 60*60*12
    elif diff > 60*60*24*7:
        raise TimeoutError("Bulk deployment timeout!")
