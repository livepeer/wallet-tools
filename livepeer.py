#!/bin/python3
from lib import Util, Contract, State


class Orchestrator:

    def __init__(self, obj):
        # Orch details
        self.source_address = obj._source_address
        # Get private key
        self.source_private_key = Util.getPrivateKey(obj._source_key, obj._source_password)
        # If the password was set via file or environment var but failed to decrypt, exit
        if self.source_private_key == "":
            Util.log("Fatal error: Unable to decrypt keystore file. Exiting...", 1)
            exit(1)
        self.source_checksum_address = Util.getChecksumAddr(obj._source_address)
        # Set target adresses
        self.target_address = obj._target_address
        self.target_checksum_address = Util.getChecksumAddr(obj._target_address)


# For each configured keystore, create an Orchestrator object
if len(State.KEYSTORE_CONFIGS) != 1:
    Util.log("Only 1 Keystore Config is currently supported. Exiting...", 1)
    exit(1)


State.orchestrator = Orchestrator(State.KEYSTORE_CONFIGS[0])


# Main logic
def withdraw_fees():
    Util.log("### {}Withdrawing Fees ###".format('Dry-running ' if State.DRY_RUN else ''), 1)
    pending_fees = Contract.pendingFees()
    if pending_fees < State.ETH_THRESHOLD:
        Util.log("{0} has {1:.4f} ETH in pending fees < threshold of {2:.4f} ETH".format(State.orchestrator.source_address, pending_fees, State.ETH_THRESHOLD), 1)
    else:
        Util.log("{0} has {1:.4f} in ETH pending fees > threshold of {2:.4f} ETH, withdrawing fees...".format(State.orchestrator.source_address, pending_fees, State.ETH_THRESHOLD), 1)
        Contract.doWithdrawFees()


def fund_deposit():
    Util.log("### {}Funding Deposit ###".format('Dry-running ' if State.DRY_RUN else ''), 1)
    balance = Contract.getEthBalance()
    # Transfer ETH to Receiver Gateway's Deposit if threshold is reached
    if balance < State.ETH_THRESHOLD:
        Util.log("{0} has {1:.4f} ETH in their wallet < threshold of {2:.4f} ETH".format(State.orchestrator.source_address, balance, State.ETH_THRESHOLD), 1)
    elif State.ETH_MINVAL > balance:
        Util.log("Cannot send ETH, as the minimum value {0:.4f} ETH to leave behind is larger than the balance {1:.4f} ETH".format(State.ETH_MINVAL, balance), 1)
    else:
        Util.log("{0} has {1:.4f} in ETH in their wallet > threshold of {2:.4f} ETH, sending some to {3}...".format(State.orchestrator.source_address, balance, State.ETH_THRESHOLD, State.orchestrator.target_address), 2)
        Contract.doFundDeposit(float(balance) - State.ETH_MINVAL)


if __name__ == "__main__":
    withdraw_fees()
    fund_deposit()
