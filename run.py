import os
import yaml
from core.main import Agent

config_path = os.getenv("CONFIG_PATH")

try:
    with open(config_path or "/opt/sixfab/.env.yaml") as env_file:
        configs = yaml.safe_load(env_file)
except:
    configs = {}

if __name__ == "__main__":
    agent = Agent(
        configs=configs
    )
    agent.loop()
