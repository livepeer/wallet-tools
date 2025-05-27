# All classes and variables we want to share across files
# Also parses the config on initialisation
import configparser #< Parse the .ini file
import os #< Used to get environment variables & for resolving relative file paths


# Determine root directory
SIPHON_ROOT = os.path.dirname(os.path.abspath(__file__))
# Remove subdir which venv's can add
if SIPHON_ROOT.endswith("/lib"):
    SIPHON_ROOT = os.path.dirname(SIPHON_ROOT)


### Config & Variables


# Turn config options into a nice object to work with later
class OrchConf:
  def __init__(self, key, pw, pub, eth_target):
    self._source_key = key
    self._source_password = pw
    self._source_address = pub
    self._target_address = eth_target

# Load config file
config = configparser.ConfigParser()
config.read(os.path.join(SIPHON_ROOT, 'config.ini'))

# For each keystore section, create a OrchConf object
KEYSTORE_CONFIGS = []
# If there's no environment variable set, read keystore config from .ini file
if os.getenv('KEYSTORE', "") == "":
    for section in config.sections():
        if section.startswith('keystore'):
            KEYSTORE_CONFIGS.append(
                OrchConf(
                    config[section]['keystore'],
                    config[section]['password'],
                    config[section]['source_address'],
                    config[section]['receiver_address'],
                )
            )
else:
    # Else ignore keystore config - read all data from environment variables
    keystores = os.getenv('SIPHON_KEYSTORES', "")
    passwords = os.getenv('SIPHON_PASSWORDS', "")
    source_adresses = os.getenv('SIPHON_SOURCES', "")
    receiver_addresses_eth = os.getenv('SIPHON_TARGETS_ETH', "")
    for keystore, password, source_adress, receiver_address in zip(keystores, passwords, source_adresses, receiver_addresses_eth):
            KEYSTORE_CONFIGS.append(
                OrchConf(
                    keystore,
                    password,
                    source_adress,
                    receiver_address
                )
            )
# Thresholds
ETH_THRESHOLD = float(os.getenv('SIPHON_ETH_THRESHOLD', config['thresholds']['eth_threshold']))
ETH_MINVAL = float(os.getenv('SIPHON_ETH_MINVAL', config['thresholds']['eth_minval']))
# RPC
L2_RPC_PROVIDER = os.getenv('SIPHON_RPC_L2', config['rpc']['l2'])
# Logging
LOG_VERBOSITY = int(os.getenv('SIPHON_VERBOSITY', config['other']['verbosity']))
LOG_TIMESTAMPED = bool(os.getenv('SIPHON_TIMESTAMPED', config.getboolean('other', 'log_timestamped')))