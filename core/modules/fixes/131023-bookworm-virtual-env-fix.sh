#!/bin/bash

SIXFAB_PATH="/opt/sixfab"
CORE_PATH="$SIXFAB_PATH/core"
MANAGER_SOURCE_PATH="$CORE_PATH/manager"
AGENT_SOURCE_PATH="$CORE_PATH/agent"

# Install agent requirements
python3 -m venv $AGENT_SOURCE_PATH/venv
source $AGENT_SOURCE_PATH/venv/bin/activate
pip3 install -r $AGENT_SOURCE_PATH/requirements.txt
deactivate

# Install manager requirements
python3 -m venv $MANAGER_SOURCE_PATH/venv
source $MANAGER_SOURCE_PATH/venv/bin/activate
pip3 install -r $MANAGER_SOURCE_PATH/requirements.txt
deactivate

# Update service files
sudo mv $AGENT_SOURCE_PATH/core_agent.service /etc/systemd/system/core_agent.service
sudo mv $MANAGER_SOURCE_PATH/core_manager.service /etc/systemd/system/core_manager.service
sudo systemctl daemon-reload

# enable services
sudo systemctl enable core_manager.service
sudo systemctl enable core_agent.service

# restart services
sudo systemctl restart core_manager.service
sudo systemctl restart core_agent.service
