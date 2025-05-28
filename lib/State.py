# All classes and variables we want to share across files
# Also parses the config on initialisation
import configparser
import os
import logging

# Determine root directory
SIPHON_ROOT = os.path.dirname(os.path.abspath(__file__))
# Remove subdir which venv's can add
if SIPHON_ROOT.endswith("/lib"):
    SIPHON_ROOT = os.path.dirname(SIPHON_ROOT)


# Config & Variables


# Turn config options into a nice object to work with later
class OrchConf:
    def __init__(self, key, pw, pub, eth_target):
        self.source_key = key
        self.source_password = pw
        self.source_address = pub
        self.target_address = eth_target


# Load config file
config = configparser.ConfigParser()
config.read(os.path.join(SIPHON_ROOT, 'config.ini'))

# For each keystore section, create a OrchConf object
KEYSTORE_CONFIGS = []
# If there's no environment variable set, read keystore config from .ini file
if os.getenv('KEYSTORE', "") == "":
    for name, section in config.items():
        if not name.startswith('keystore'):
            continue
        KEYSTORE_CONFIGS.append(
            OrchConf(section['keystore'], section['password'], section['source_address'], section['receiver_address']))

else:
    # Else ignore keystore config - read all data from environment variables
    keystores = os.getenv('SIPHON_KEYSTORES', "")
    passwords = os.getenv('SIPHON_PASSWORDS', "")
    source_addresses = os.getenv('SIPHON_SOURCES', "")
    receiver_addresses_eth = os.getenv('SIPHON_TARGETS_ETH', "")
    for keystore, password, source_address, receiver_address in zip(keystores, passwords, source_addresses, receiver_addresses_eth):
        KEYSTORE_CONFIGS.append(OrchConf(keystore, password, source_address, receiver_address))

# Thresholds
ETH_THRESHOLD = float(os.getenv('SIPHON_ETH_THRESHOLD', config['thresholds']['eth_threshold']))
ETH_MINVAL = float(os.getenv('SIPHON_ETH_MINVAL', config['thresholds']['eth_minval']))
# RPC
L2_RPC_PROVIDER = os.getenv('SIPHON_RPC_L2', config['rpc']['l2'])
# Logging
LOG_VERBOSITY = int(os.getenv('SIPHON_VERBOSITY', config['other']['verbosity']))
LOG_TIMESTAMPED = bool(os.getenv('SIPHON_TIMESTAMPED', config.getboolean('other', 'log_timestamped')))

logging.basicConfig(level=LOG_VERBOSITY, format="%(asctime)s %(levelname)s %(message)s")
