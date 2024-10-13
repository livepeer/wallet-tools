# OrchestratorSiphon

Clone repo to your machine: ```git clone https://github.com/stronk-dev/OrchestratorSiphon.git```

Modify the script to use your orchs ETH keystore file: ```nano OrchestratorSiphon/OrchestratorSiphon.py```

Dependencies:

```
pip install web3
pip install eth-utils
pip install setuptools
```

Run the script manually to test if it works:
```
python3 OrchestratorSiphon/OrchestratorSiphon.py
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
WorkingDirectory=/path/to/OrchestratorSiphon
ExecStart=/usr/bin/python3 -u /path/to/OrchestratorSiphon/OrchestratorSiphon.py

[Install]
WantedBy=multi-user.target
```

Save service file and enable the service:

```
systemctl daemon-reload
systemctl enable --now orchSiphon.service
```

Check logs: ```journalctl -u orchSiphon.service -n 500 -f```

## Arch Linux (or other venv)

For operatins systems like Arch linux, enter the repository and create a new virtual environment:

```
cd OrchestratorSiphon
python -m venv .
```

Install depedencies:
```
bin/pip install web3
bin/pip install setuptools
bin/pip install eth-utils
```

Don't forget to use the python binary from the virtual environment when running the script: ```bin/python3 OrchestratorSiphon.py```

For the `systemd` script this means changing ExecStart to `ExecStart=/path/to/OrchestratorSiphon/bin/python3 -u /path/to/OrchestratorSiphon/OrchestratorSiphon.py`