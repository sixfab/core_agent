import yaml
import json
import time
from uuid import uuid4

from core.__version__ import version

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


CONTROL_INTERVAL=30
message_cache = {} # key, value pattern for each mid, message_body


def main(mqttClient, configs):
    logger = configs["logger"]
    last_monitoring_data = {}
    last_system_data = {}


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
                    del data["data"]["timestamp"]
                    last_monitoring_data.update(data["data"])
                    logger.debug("Updated last monitoring data")

                elif data["type"] == "data_system":
                    last_system_data.update(data["data"])
                    logger.debug("Updated last system data")



    configs["callbacks"].append(callback)


    while True:
        # MONITOR DATA
        new_monitoring_data = None
        try:
            new_monitoring_data = open("/home/sixfab/.core/monitor.yaml")
        except:
            logger.error("Monitoring data not exists!")

        if new_monitoring_data:
            new_monitoring_data = yaml.load(new_monitoring_data, Loader=Loader)

            data_to_send = {}

            for key, value in new_monitoring_data.items():
                last_value = last_monitoring_data.get(key, "N/A")

                if value != last_value:
                    data_to_send[key] = value

            if data_to_send:
                mid = uuid4().hex[-4:]

                data_to_send["timestamp"] = time.time()

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
            new_system_data = open("/home/sixfab/.core/system.yaml")
        except:
            logger.error("System data not exists!")

        if new_system_data:
            new_system_data = yaml.load(new_system_data, Loader=Loader)
            new_system_data["agent_version"] = version
    
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


        time.sleep(CONTROL_INTERVAL)
