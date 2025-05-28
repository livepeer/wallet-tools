# Any functions which requires reading/writing smart contracts gets dumped here
# Also connects to the RPC provider and holds accessors to the smart contracts

import web3  # Currency conversions
import json
import logging
from lib import State
from lib.Util import getPrivateKey, getChecksumAddr


log = logging.getLogger(__name__)


BONDING_CONTRACT_ADDR = '0x35Bcf3c30594191d53231E4FF333E8A770453e40'
TICKET_BROKER_CONTRACT_ADDR = '0xa8bB618B1520E284046F3dFc448851A1Ff26e41B'


# Define contracts

def getABI(path) -> dict:
    """
    Returns a dict with ABI data

    :param str path: absolute/relative path to an ABI file
    """
    try:
        with open(path) as f:
            info_json = json.load(f)
            return info_json["abi"]
    except Exception:
        log.exception("Fatal error: Unable to extract ABI data")
        exit(1)


abi_bonding_manager = getABI(State.SIPHON_ROOT + "/contracts/BondingManager.json")
abi_ticket_broker = getABI(State.SIPHON_ROOT + "/contracts/TicketBroker.json")


def w3_contracts():
    # connect to L2 rpc provider
    provider = web3.HTTPProvider(State.L2_RPC_PROVIDER)
    w3 = web3.Web3(provider)
    assert w3.is_connected(), "Unable to connect to the L2 RPC provider"

    # prepare contracts
    bonding_contract = w3.eth.contract(address=BONDING_CONTRACT_ADDR, abi=abi_bonding_manager)
    ticket_broker_contract = w3.eth.contract(address=TICKET_BROKER_CONTRACT_ADDR, abi=abi_ticket_broker)
    return bonding_contract, ticket_broker_contract

class Orchestrator:

    def __init__(self, obj):
        # Orch details
        self.source_address = obj.source_address
        # Get private key
        self.source_private_key = getPrivateKey(obj.source_key, obj.source_password)
        # If the password was set via file or environment var but failed to decrypt, exit
        if not self.source_private_key:
            log.error("Fatal error: Unable to decrypt keystore file. Exiting...")
            exit(1)
        self.source_checksum_address = getChecksumAddr(obj.source_address)
        # Set target adresses
        self.target_address = obj.target_address
        self.target_checksum_address = getChecksumAddr(obj.target_address)


def pendingFees(bonding_contract, orch: Orchestrator) -> float:
    try:
        pending_wei = bonding_contract.functions.pendingFees(orch.source_checksum_address, 99999).call()
        return web3.Web3.from_wei(pending_wei, 'ether')
    except Exception:
        log.warning("Unable to get pending fees", exc_info=True)
        return 0.0


def doWithdrawFees(bonding_contract, orch: Orchestrator) -> None:
    try:
        # We take a little bit off due to floating point inaccuracies causing tx's to fail
        transfer_amount = web3.Web3.to_wei(float(orch.balance_ETH_pending) - 0.00001, 'ether')
        receiver_address = orch.source_checksum_address
        log.info("Withdrawing %s WEI to %s", transfer_amount, orch.source_address)
        # Build transaction info
        transaction_obj = bonding_contract.functions.withdrawFees(receiver_address, transfer_amount).build_transaction(
            {
                "from": orch.source_checksum_address,
                'maxFeePerGas': 2000000000,
                'maxPriorityFeePerGas': 1000000000,
                "nonce": bonding_contract.w3.eth.get_transaction_count(orch.source_checksum_address)
            }
        )
        # Sign and initiate transaction
        signed_transaction = bonding_contract.w3.eth.account.sign_transaction(transaction_obj, orch.source_private_key)
        transaction_hash = bonding_contract.w3.eth.send_raw_transaction(signed_transaction.raw_transaction)
        log.info("Initiated transaction with hash %s", transaction_hash.hex())
        # Wait for transaction to be confirmed
        bonding_contract.w3.eth.wait_for_transaction_receipt(transaction_hash)
        log.info('Withdraw fees success.')
    except Exception:
        log.exception("Unable to withdraw fees")


def getEthBalance(w3, orch: Orchestrator) -> float:
    try:
        balance_wei = w3.eth.get_balance(orch.source_checksum_address)
        balance_ETH = web3.Web3.from_wei(balance_wei, 'ether')
        return balance_ETH
    except Exception:
        log.exception("Unable to get ETH balance")


def doFundDeposit(ticket_broker_contract, orch: Orchestrator, amount) -> None:
    try:
        receiver_address = orch.target_checksum_address
        log.info("Sending deposit %s WEI directly to receiver's deposit %s", amount, orch.target_address)
        amount_wei = web3.Web3.to_wei(amount, 'ether')
        # Build transaction info
        transaction_obj = ticket_broker_contract.functions.fundDepositAndReserveFor(receiver_address, amount_wei, 0).build_transaction(
            {
                "from": orch.source_checksum_address,
                'maxFeePerGas': 2000000000,
                'maxPriorityFeePerGas': 1000000000,
                'value': amount_wei,
                "nonce": ticket_broker_contract.w3.eth.get_transaction_count(orch.source_checksum_address),
                'gas': 300000,
                'chainId': 54321
            }
        )
        # Sign and initiate transaction
        signed_transaction = ticket_broker_contract.w3.eth.account.sign_transaction(transaction_obj, orch.source_private_key)
        transaction_hash = ticket_broker_contract.w3.eth.send_raw_transaction(signed_transaction.raw_transaction)
        log.info("Initiated transaction with hash %s", transaction_hash.hex())
        # Wait for transaction to be confirmed
        ticket_broker_contract.w3.eth.wait_for_transaction_receipt(transaction_hash)
        log.info("Fund deposit success.")
    except Exception:
        log.exception("Unable to fund deposit")
