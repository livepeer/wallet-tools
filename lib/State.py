# All classes and variables we want to share across files
# Also parses the config on initialisation
import configparser  # Parse the .ini file
import os
import pathlib
from distutils.util import strtobool


ROOT_DIR = pathlib.Path(__file__).parent.parent


# Config & Variables


# Turn config options into a nice object to work with later
class OrchConf:
    def __init__(self, key, pw, pub, eth_target):
        self._source_key = key
        self._source_password = pw
        self._source_address = pub
        self._target_address = eth_target


# Load config file
config = configparser.ConfigParser()
config_ini = ROOT_DIR / 'config.ini'
if not config_ini.exists():
    print(f"Config file not found: {config_ini} !")
config.read(config_ini)

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
    keystore = os.getenv('KEYSTORE', "")
    password = os.getenv('PASSWORD', "")
    source_address = os.getenv('SOURCE', "")
    target_address = os.getenv('TARGET', "")
    print("source_address: {0}, receiver_address: {1}".format(source_address, target_address))

    KEYSTORE_CONFIGS.append(
        OrchConf(
            keystore,
            password,
            source_address,
            target_address
        )
    )


def get_bool(env_name, *args, fallback):
    """Get a boolean value from an environment variable or prased config ini file."""
    return strtobool(os.getenv(env_name, str(config.getboolean(*args, fallback=fallback))))


# Thresholds
ETH_THRESHOLD = float(os.getenv('ETH_THRESHOLD', config.getfloat('thresholds', 'eth_threshold')))
ETH_MINVAL = float(os.getenv('ETH_MINVAL', config.getfloat('thresholds', 'eth_minval')))
# Fixed ETH deposit
FIXED_ETH = float(os.getenv('FIXED_ETH', config.getfloat('fixed', 'fixed_eth')))
# RPC
L2_RPC_PROVIDER = os.getenv('RPC_L2', config['rpc']['l2'])
# Logging
LOG_VERBOSITY = int(os.getenv('LOG_VERBOSITY', config.getint('other', 'verbosity', fallback=1)))
LOG_TIMESTAMPED = get_bool('LOG_TIMESTAMPED', 'other', 'log_timestamped', fallback=True)
# Dry run
DRY_RUN = get_bool('DRY_RUN', 'other', 'dry_run', fallback=True)
# Disable steps
SKIP_FEES_WITHDRAWAL = get_bool('SKIP_FEES_WITHDRAWAL', 'other', 'skip_fees_withdrawal', fallback=False)
