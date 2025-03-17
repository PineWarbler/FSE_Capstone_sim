#!/bin/bash
sudo systemctl restart fse_sim_server.service
sudo systemctl enable fse_sim_server.service
sudo systemctl daemon-reload

echo "re-enabled fse_sim_server.service. It is running right now and will be auto-run on future boots."