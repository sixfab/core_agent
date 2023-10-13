#!/bin/bash

SIXFAB_PATH="/opt/sixfab"
CORE_PATH="$SIXFAB_PATH/core"
AGENT_SOURCE_PATH="$CORE_PATH/agent"

# Configure the environment
export PATH="$AGENT_SOURCE_PATH/venv/bin:$PATH"

# Run the agent
$AGENT_SOURCE_PATH/venv/bin/python3 $AGENT_SOURCE_PATH/run.py
