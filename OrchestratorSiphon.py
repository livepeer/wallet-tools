#!/bin/python3
import time #< Used to put the program to sleep to save CPU cycles
from datetime import datetime, timezone #< Keep track of timers and expiration of cached variables
import sys #< Used to exit the script
from getpass import getpass # Used to get user input without printing it to screen
import signal #< Used to catch terminal signals to switch to interactive mode
import argparse #< Used to launch the program locked into interactive mode
# Import our own libraries
from lib import Util, Contract, User, State


### Immediately start signal listeners - these are used to switch to interactive mode


# The signals we're listening for
signal_names = ['SIGINT','SIGQUIT','SIGTSTP']
# Lookup table so we can translate back to a name for printing
signal_map = dict((getattr(signal, k), k) for k in signal_names)

"""
@brief Catches signals
@param num: Number corresponding to the signal name
@param _: ignored, but required when attaching the signal handler
"""
def sigHandler(num, _):
    Util.log("Received signal: {0}".format(signal_map.get(num, '<other>')), 2)
    if num == signal.SIGINT:
        sys.exit(1)
    Util.log("Will switch to interactive mode...", 2)
    State.require_user_input = True
# Immediately enable listeners for each configured signal
for name in signal_names:
    signal.signal(getattr(signal, name), sigHandler)


### Parse launch arguments


parser = argparse.ArgumentParser(description="Orchestrator Siphon")
parser.add_argument(
    '-i', '-it', '--interactive', action='store_true', help="Launch the program locked in interactive mode."
)
args, unknown = parser.parse_known_args()
if unknown:
    Util.log(f"Warning: Skipping unknown arguments: {', '.join(unknown)}", 1)
State.LOCK_INTERACTIVE = getattr(args, 'interactive', False) or getattr(args, 'it', False) or getattr(args, 'i', False)
State.require_user_input = State.LOCK_INTERACTIVE


### Orchestrator state


# This class initializes an Orchestrator object
class Orchestrator:
    def __init__(self, obj):
        # Orch details
        self.source_address = obj._source_address
        self.srcKeypath = obj._source_key
        # Get private key
        if obj._source_password == "":
            self.source_private_key = ""
        else:
            self.source_private_key = Util.getPrivateKey(obj._source_key, obj._source_password)
            # Immediately clear the text file containing the password
            if State.CLEAR_PASSWORD:
                Util.clearPassword(obj._source_password)
            # If the password was set via file or environment var but failed to decrypt, exit
            if self.source_private_key == "":
                Util.log("Fatal error: Unable to decrypt keystore file. Exiting...", 1)
                exit(1)
        self.source_checksum_address = Util.getChecksumAddr(obj._source_address)
        # Set target adresses
        self.target_address_ETH = obj._target_address_eth
        self.target_checksum_address_ETH = Util.getChecksumAddr(obj._target_address_eth)
        # ETH details
        self.previous_ETH_refresh = 0
        self.balance_ETH_pending = 0
        self.balance_ETH = 0
        # Round details
        self.previous_round_refresh = 0
        self.previous_reward_round = 0

# For each configured keystore, create a Orchestrator object
for obj in State.KEYSTORE_CONFIGS:
    Util.log("Adding Orchestrator '{0}'".format(obj._source_address), 2)
    State.orchestrators.append(Orchestrator(obj))

# For each Orch with no password set, decrypt by user input
for i in range(len(State.orchestrators)):
    while State.orchestrators[i].source_private_key == "":
        State.orchestrators[i].source_private_key = Util.getPrivateKey(State.orchestrators[i].srcKeypath, getpass("Enter the password for {0}: ".format(State.orchestrators[i].source_address)))


### Main logic


"""
@brief Checks all Orchestrators if any cached data needs refreshing or contracts need calling
"""
def refreshState():
    for i in range(len(State.orchestrators)):
        Contract.refreshFees(i)
        Contract.checkEthBalance(i)

        # Withdraw pending ETH if threshold is reached 
        if State.orchestrators[i].balance_ETH_pending < State.ETH_THRESHOLD:
            Util.log("{0} has {1:.4f} ETH in pending fees < threshold of {2:.4f} ETH".format(State.orchestrators[i].source_address, State.orchestrators[i].balance_ETH_pending, State.ETH_THRESHOLD), 3)
        else:
            Util.log("{0} has {1:.4f} in ETH pending fees > threshold of {2:.4f} ETH, withdrawing fees...".format(State.orchestrators[i].source_address, State.orchestrators[i].balance_ETH_pending, State.ETH_THRESHOLD), 2)
            Contract.doWithdrawFees(i)
            Contract.refreshFees(i)
            Contract.checkEthBalance(i)
        
        # Transfer ETH to Receiver Gateway's Deposit if threshold is reached
        if State.orchestrators[i].balance_ETH < State.ETH_THRESHOLD:
            Util.log("{0} has {1:.4f} ETH in their wallet < threshold of {2:.4f} ETH".format(State.orchestrators[i].source_address, State.orchestrators[i].balance_ETH, State.ETH_THRESHOLD), 3)
        elif State.ETH_MINVAL > State.orchestrators[i].balance_ETH:
            Util.log("Cannot fund ETH, as the minimum value to leave behind is larger than the balance", 1)
        else:
            Util.log("{0} has {1:.4f} in ETH pending fees > threshold of {2:.4f} ETH, sending some to {3}...".format(State.orchestrators[i].source_address, State.orchestrators[i].balance_ETH, State.ETH_THRESHOLD, State.orchestrators[i].target_address_ETH), 2)
            Contract.doFundDeposit(i)
            Contract.checkEthBalance(i)

current_time = datetime.now(timezone.utc).timestamp()
refreshState()