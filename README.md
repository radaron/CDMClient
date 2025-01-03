# CDMClient
CDM - Centralized Download Manager Client

## Installation

### Install/Upgrade package
``` shell
python3 -m pip install --upgrade CDMClient --user
```

### Create service
``` shell
echo "[Unit]
Description=cdm-client service
After=multi-user.target
Conflicts=getty@tty1.service
[Service]
User=${USER}
Type=simple
Environment="LC_ALL=C.UTF-8"
Environment="LANG=C.UTF-8"
ExecStart=${HOME}/.local/bin/cdm-client
Restart=on-failure
RestartSec=3
[Install]
WantedBy=multi-user.target" | sudo tee /etc/systemd/system/cdm-client.service
```
``` shell
sudo systemctl daemon-reload
sudo systemctl enable cdm-client.service
sudo systemctl start cdm-client.service
```

## Configuartion
Config file path: ```~/.config/cdm_client/config.ini```

This file automatically generated when the service starts. See the example below.
``` ini
[connection]
server_host =
api_key =
rpc_user =
rpc_password =
```

## Check logs
``` shell
journalctl -fu cdm-client
```
