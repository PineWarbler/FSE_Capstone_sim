#!/bin/bash
sudo systemctl stop fse_sim_server.service
sudo systemctl disable fse_sim_server.service
echo "stopped the current server instance task and disabled it from loading on next boot"
echo "--Remember--the simulator will not function on next boot until you re-enable the service ! "