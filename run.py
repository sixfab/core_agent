from core.main import Agent
import yaml


try:
    with open("/opt/sixfab/.env.yaml") as env_file:
        configs = yaml.safe_load(env_file)
except:
    configs = {}


if __name__ == "__main__":
    agent = Agent(
        configs=configs
    )
    agent.loop()
