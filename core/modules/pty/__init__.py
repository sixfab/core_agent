import os
import time
import logging
import platform
import subprocess
from urllib import request

BUILDS_DIR = os.path.dirname(os.path.realpath(__file__))

class PTYController:
    def __init__(self, configs):
        self.supported_architectures = {
            "aarch64": "arm64",
            "armv6l": "arm32",
            "armv7l": "arm32",
        }
        
        self.configs = configs
        self.logger = configs["logger"]
        self.mqtt_client = configs["mqtt_client"]
        self.start_agent()

    def stop_running_agent(self):
        try:
            running_pid = subprocess.check_output(["sudo", "fuser", "8998/tcp"], stderr=subprocess.DEVNULL).decode()
        except:
            print("couldn't get running pid")
            return

        os.system(f"sudo kill -9 {running_pid}")
        print("killed process")

        return

    def is_agent_running(self):
        try:
            running_pid = subprocess.check_output(["sudo", "fuser", "8998/tcp"], stderr=subprocess.DEVNULL).decode()
            try:
                response = request.urlopen("http://localhost:8998/healthcheck")
                response = response.read()
            except:
                response = b'dead'

            return response == b"alive"
        except:
            return False


    def start_agent(self):
        if self.is_agent_running():
            self.stop_running_agent()

        architecture = platform.machine()

        if architecture not in self.supported_architectures:
            self.logger.error(f"{architecture} is not supported for remote terminal")
            self.mqtt_client.publish(f"signaling/{self.configs['token']}/response", "platform_not_supported")
            return False


        executable_source=self.supported_architectures[architecture]

        print("started go agent ", f"{BUILDS_DIR}/builds/{executable_source}")
        executable_path = f"{BUILDS_DIR}/builds/{executable_source}"
        os.system(f"sudo chmod +x {executable_path} && {executable_path} &")

        return True


    def request(self, data):
        if type(data) != bytes:
            data = data.encode()

        if not self.is_agent_running():
            if not self.start_agent():
                return

        response = None

        try:
            response = request.urlopen("http://localhost:8998/session", data)
            response = response.read()

        except Exception as e:
            print("="*20)
            print("re-opening agent")

            self.stop_running_agent()
            self.start_agent()

            time.sleep(1)

            response = request.urlopen("http://localhost:8998/session", data)
            response = response.read()



        return response
