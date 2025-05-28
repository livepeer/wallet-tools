#!/bin/python3
import logging
from lib import State
from lib.Contract import Orchestrator, pendingFees, doWithdrawFees, doFundDeposit, getEthBalance, w3_contracts


log = logging.getLogger(__name__)


def withdraw_fees(bonding_contract, orch: Orchestrator):
    # Main logic
    log.info("### Withdrawing Fees ###")
    pending_fees = pendingFees(pendingFees, orch)
    if pending_fees < State.ETH_THRESHOLD:
        log.info("%s has %.4f ETH in pending fees < threshold of %.4f ETH",
                 orch.source_address, pending_fees, State.ETH_THRESHOLD)
    else:
        log.info("%s has %.4f in ETH pending fees > threshold of %.4f ETH, withdrawing fees...",
                 orch.source_address, pending_fees, State.ETH_THRESHOLD)
        doWithdrawFees(bonding_contract, orch)


def fund_deposit(ticket_broker_contract, orch: Orchestrator):
    log.info("### Funding Deposit ###")
    balance = getEthBalance(ticket_broker_contract.w3, orch)
    # Transfer ETH to Receiver Gateway's Deposit if threshold is reached
    if balance < State.ETH_THRESHOLD:
        log.info("%s has %.4f ETH in their wallet < threshold of %.4f ETH",
                 orch.source_address, balance, State.ETH_THRESHOLD)
    elif State.ETH_MINVAL > balance:
        log.info("Cannot send ETH, as the minimum value %.4f ETH to leave behind is larger than the balance %.4f ETH",
                 State.ETH_MINVAL, balance)
    else:
        log.info("%s has %.4f in ETH pending fees > threshold of %.4f ETH, sending some to %s...",
                 orch.source_address, balance, State.ETH_THRESHOLD, orch.target_address)
        doFundDeposit(orch, float(balance) - State.ETH_MINVAL)


if __name__ == "__main__":
    # For each configured keystore, create a Orchestrator object
    if len(State.KEYSTORE_CONFIGS) != 1:
        log.error("Only 1 Keystore Config is currently supported. Exiting...")
        exit(1)

    bonding_contract, ticket_broker_contract = w3_contracts()
    orch = Orchestrator(State.KEYSTORE_CONFIGS[0])
    withdraw_fees(bonding_contract, orch)
    fund_deposit(orch)
