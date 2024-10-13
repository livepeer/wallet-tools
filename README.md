# OrchestratorSyphon

Clone repo to your machine: ```git clone https://github.com/stronk-dev/OrchestratorSiphon.git```

Modify the script to use your orchs ETH keystore file: ```nano /OrchestratorSyphon/OrchestratorSyphon.py```

Dependencies:

```
pip install web3
pip install eth-utils
pip install setuptools
```

Run the script manually to test if it works:
```
python3 OrchestratorSyphon.py
```

Example systemd script (modify paths):
```sudo nano /etc/systemd/system/orchSiphon.service```

```
[Unit]
Description=LPT bond transfer
After=multi-user.target

[Service]
Type=simple
Restart=always
WorkingDirectory=/path/to/OrchestratorSyphon
ExecStart=/usr/bin/python3 -u /path/to/OrchestratorSyphon/OrchestratorSyphon.py

[Install]
WantedBy=multi-user.target
```

Save service file and enable the service:

```
systemctl daemon-reload
systemctl enable --now orchSiphon.service
```

Check logs: ```journalctl -u orchSiphon.service -n 500 -f```

