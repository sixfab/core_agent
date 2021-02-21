import os
import json


def update_modules(configs, mqtt_client):
    logger = configs["logger"]

    send_status = lambda status: mqtt_client.publish(
            f"device/{configs['token']}/hive", 
            json.dumps({
                "type": "update_status",
                "status": status
            })
        )

    logger.info("[UPDATER] Updating agent source")

    send_status("download_agent")
    commands = [
        "cd /opt/sixfab/connect/agent",
        "sudo git reset --hard HEAD",
        "sudo git fetch",
        "sudo git pull",
        "sudo pip3 install -r requirements.txt"
    ]
    os.system(" && ".join(commands))
    logger.info("[UPDATER] Updated agent source")


    logger.info("[UPDATER] Updating manager source")
    send_status("download_manager")
    commands = [
        "cd /opt/sixfab/connect/manager",
        "sudo git reset --hard HEAD",
        "sudo git fetch",
        "sudo git pull",
        "sudo pip3 install -r requirements.txt"
    ]
    os.system(" && ".join(commands))
    logger.info("[UPDATER] Updated manager source")


    logger.info("[UPDATER] Restarting services")
    send_status("restart_services")
    commands = [
        "sudo systemctl restart connect_manager",
        "sudo systemctl restart connect_agent"
    ]
    os.system(" && ".join(commands))
