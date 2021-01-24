import yaml
import json
import time

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


CONTROL_INTERVAL=15


def main(mqttClient, configs):
    logger = configs["logger"]
    last_monitoring_data = {}
    last_system_data = {}

    while True:

        # MONITOR DATA
        try:
            new_monitoring_data = open("/home/sixfab/.sixfab/connect/monitor.yaml")
        except:
            logger.error("Monitoring data not exists!")

        new_monitoring_data = yaml.load(new_monitoring_data, Loader=Loader)

        data_to_send = {}

        for key, value in new_monitoring_data.items():
            if key not in last_monitoring_data:
                data_to_send[key] = value

            elif last_monitoring_data[key] != value:
                data_to_send[key] = value


        if data_to_send:
            mqttClient.publish(f"device/{configs['token']}/hive", json.dumps(dict(
                type="data_monitoring",
                data=data_to_send
            )))

            logger.info("Sending new monitoring data")
        else:
            logger.info("Skipping monitoring data, couldn't find any changes.")

        last_monitoring_data.update(new_monitoring_data)




        # SYSTEM DATA
        try:
            new_system_data = open("/home/sixfab/.sixfab/connect/system.yaml")
        except:
            logger.error("System data not exists!")

        new_system_data = yaml.load(new_system_data, Loader=Loader)

        data_to_send = {}

        for key, value in new_system_data.items():
            if key not in last_system_data:
                data_to_send[key] = value

            elif last_system_data[key] != value:
                data_to_send[key] = value


        if data_to_send:
            mqttClient.publish(f"device/{configs['token']}/hive", json.dumps(dict(
                type="data_system",
                data=data_to_send
            )))

            logger.info("Sending new system data")
        else:
            logger.info("Skipping system data, couldn't find any changes.")

        last_system_data.update(new_system_data)



        time.sleep(CONTROL_INTERVAL)
