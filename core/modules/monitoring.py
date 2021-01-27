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
        new_monitoring_data = None
        try:
            new_monitoring_data = open("/home/sixfab/.sixfab/connect/monitor.yaml")
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
                mqttClient.publish(f"device/{configs['token']}/hive", json.dumps(dict(
                    type="data_monitoring",
                    data=data_to_send
                )))

                logger.debug("Sending new monitoring data")
            else:
                logger.debug("Skipping monitoring data, couldn't find any changes.")

            last_monitoring_data.update(new_monitoring_data)




        # SYSTEM DATA
        new_system_data = None
        try:
            new_system_data = open("/home/sixfab/.sixfab/connect/system.yaml")
        except:
            logger.error("System data not exists!")

        if new_system_data:
            new_system_data = yaml.load(new_system_data, Loader=Loader)
    
            data_to_send = {}
    
            for key, value in new_system_data.items():
                last_value = last_system_data.get(key, "N/A")

                if value != last_value:
                    data_to_send[key] = value
    
    
            if data_to_send:
                mqttClient.publish(f"device/{configs['token']}/hive", json.dumps(dict(
                    type="data_system",
                    data=data_to_send
                )))
    
                logger.debug("Sending new system data")
            else:
                logger.debug("Skipping system data, couldn't find any changes.")
    
            last_system_data.update(new_system_data)



        time.sleep(CONTROL_INTERVAL)
