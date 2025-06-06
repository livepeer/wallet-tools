#!/usr/bin/python3
from lib import Util, Contract, State


class Orchestrator:

    def __init__(self, obj):
        # Orch details
        self.source_address = obj._source_address
        # Get private key
        self.source_private_key = Util.getPrivateKey(obj._source_key, obj._source_password)
        self.source_checksum_address = Util.getChecksumAddr(obj._source_address)
        # Set target adresses
        self.target_address = obj._target_address
        self.target_checksum_address = Util.getChecksumAddr(obj._target_address)


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
    source_balance = float(Contract.getEthBalance(State.orchestrator.source_checksum_address))

    if State.FIXED_ETH is not None:
        if source_balance <= State.ETH_MINVAL:
            Util.log("No deposit possible as source is below the MIN_VAL of {0:.4f} ETH, no deposit made.".format(State.ETH_MINVAL), 1)
            exit(1)
        if (source_balance - State.ETH_MINVAL) < State.FIXED_ETH:
            Util.log("Not enough ETH in source wallet to fund fixed deposit of {0:.4f} ETH, "
                     "max possible deposit is {1:.4f} ETH, no deposit made.".format(State.FIXED_ETH, source_balance - State.ETH_MINVAL), 1)
            exit(1)
        else:
            Util.log("Funding deposit of {0:.4f} ETH to the target wallet.".format(State.FIXED_ETH), 2)
            Contract.doFundDeposit(State.FIXED_ETH)
    elif source_balance < State.ETH_THRESHOLD:
        Util.log("{0} has {1:.4f} ETH in source wallet < threshold of {2:.4f} ETH, no deposit made.".format(State.orchestrator.source_address, source_balance, State.ETH_THRESHOLD), 1)
    elif State.ETH_MINVAL > source_balance:
        Util.log("Cannot send ETH, as the minimum value {0:.4f} ETH to leave behind is larger than the balance {1:.4f} ETH, no deposit made.".format(State.ETH_MINVAL, source_balance), 1)
    else:
        Util.log("{0} has {1:.4f} in ETH in their wallet > threshold of {2:.4f} ETH, sending some to {3}...".format(State.orchestrator.source_address, source_balance, State.ETH_THRESHOLD, State.orchestrator.target_address), 2)
        Contract.doFundDeposit(source_balance - State.ETH_MINVAL)


def withdraw_fees_and_fund_deposit():
    # For each configured keystore, create an Orchestrator object
    if len(State.KEYSTORE_CONFIGS) != 1:
        Util.log("Only 1 Keystore Config is currently supported. Exiting...", 1)
        exit(1)
    State.orchestrator = Orchestrator(State.KEYSTORE_CONFIGS[0])
    print("source_address: {0}, receiver_address: {1}".format(State.orchestrator.source_address, State.orchestrator.target_address))

    if not State.SKIP_FEES_WITHDRAWAL:
        withdraw_fees()
    fund_deposit()


if __name__ == "__main__":
    withdraw_fees_and_fund_deposit()
