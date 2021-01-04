from os import system
from json import dumps

def _update_status(mqtt_client, configs, status):
    mqtt_client.publish(
        f"device/{configs['token']}/hive", 
        dumps({
            "command": "update",
            "data": {
                "status": status
            } 
        })
    )


def main(mqtt_client, configs):

    update_status = lambda status: _update_status(mqtt_client, configs, status)

    beta_enabled = configs.get("beta", False)

    update_status("agent")

    system(f"""
        cd /opt/sixfab/connect/agent &&
        git pull &&
        {"git checkout dev" if beta_enabled else "git checkout master"} &&
        sudo systemctl restart connect_agent
    """)

    update_status("finish")
