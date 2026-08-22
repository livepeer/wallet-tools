#!/usr/bin/python3
from decimal import Decimal

from lib import Contract, State, Util


class SourceWallet:
    def __init__(self, config):
        self.source_private_key = Util.getPrivateKey(config._source_key, config._source_password)
        self.source_checksum_address = Util.getChecksumAddr(config._source_address)


def top_up_wallet():
    """Conditionally fund a native ETH wallet using the configured source."""
    if not State.TOP_UP_ADDRESS:
        Util.log("Top-up wallet is not configured.", 1)
        return Decimal('0')

    if State.TOP_UP_MIN_BALANCE <= 0 or State.TOP_UP_AMOUNT <= 0:
        Util.log("Top-up minimum balance and amount must both be greater than zero.", 1)
        exit(1)

    Util.log("### {}Funding Top-up Wallet ###".format('Dry-running ' if State.DRY_RUN else ''), 1)
    target_balance = Contract.getEthBalance(State.TOP_UP_ADDRESS)
    if target_balance >= State.TOP_UP_MIN_BALANCE:
        Util.log(
            "{0} has {1:.6f} ETH >= top-up threshold of {2:.6f} ETH, no top-up made.".format(
                State.TOP_UP_ADDRESS, target_balance, State.TOP_UP_MIN_BALANCE
            ),
            1,
        )
        return Decimal('0')

    source_balance = Contract.getEthBalance(State.orchestrator.source_checksum_address)
    source_minimum = Decimal(str(State.ETH_MINVAL))
    required_balance = source_minimum + State.TOP_UP_AMOUNT
    if source_balance < required_balance:
        Util.log(
            "Skipping {0:.6f} ETH top-up to {1}: source has {2:.6f} ETH but needs "
            "at least {3:.6f} ETH to preserve {4:.4f} ETH.".format(
                State.TOP_UP_AMOUNT,
                State.TOP_UP_ADDRESS,
                source_balance,
                required_balance,
                source_minimum,
            ),
            1,
        )
        return Decimal('0')

    Util.log(
        "{0} has {1:.6f} ETH < top-up threshold of {2:.6f} ETH; sending {3:.6f} ETH.".format(
            State.TOP_UP_ADDRESS,
            target_balance,
            State.TOP_UP_MIN_BALANCE,
            State.TOP_UP_AMOUNT,
        ),
        2,
    )
    Contract.doTransferEth(State.TOP_UP_ADDRESS, State.TOP_UP_AMOUNT)
    if State.DRY_RUN:
        return State.TOP_UP_AMOUNT
    return Decimal('0')


def run_top_up_wallet():
    """Configure the source wallet and run a standalone top-up."""
    if len(State.KEYSTORE_CONFIGS) != 1:
        Util.log("Only 1 Keystore Config is currently supported. Exiting...", 1)
        exit(1)
    State.orchestrator = SourceWallet(State.KEYSTORE_CONFIGS[0])
    return top_up_wallet()


if __name__ == "__main__":
    run_top_up_wallet()
