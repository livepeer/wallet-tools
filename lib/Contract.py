# Any functions which requires reading/writing smart contracts gets dumped here
# Also connects to the RPC provider and holds accessors to the smart contracts
import web3 #< Currency conversions
import sys #< To exit the program
import json #< Parse JSON ABI file
# Import our own libraries
from lib import Util, State

BONDING_CONTRACT_ADDR = '0x35Bcf3c30594191d53231E4FF333E8A770453e40'
TICKET_BROKER_CONTRACT_ADDR = '0xa8bB618B1520E284046F3dFc448851A1Ff26e41B'


### Define contracts


"""
@brief Returns a JSON object of ABI data
@param path: absolute/relative path to an ABI file
"""
def getABI(path):
    try:
        with open(path) as f:
            info_json = json.load(f)
            return info_json["abi"]
    except Exception as e:
        Util.log("Fatal error: Unable to extract ABI data: {0}".format(e), 1)
        sys.exit(1)

abi_bonding_manager = getABI(State.ROOT_DIR / "contracts/BondingManager.json")
abi_ticket_broker = getABI(State.ROOT_DIR / "contracts/TicketBroker.json")
# connect to L2 rpc provider
provider = web3.HTTPProvider(State.L2_RPC_PROVIDER)
w3 = web3.Web3(provider)
assert w3.is_connected()
# prepare contracts
bonding_contract = w3.eth.contract(address=BONDING_CONTRACT_ADDR, abi=abi_bonding_manager)
ticket_broker_contract = w3.eth.contract(address=TICKET_BROKER_CONTRACT_ADDR, abi=abi_ticket_broker)


### Orchestrator ETH logic

def pendingFees():
    try:
        pending_wei = bonding_contract.functions.pendingFees(State.orchestrator.source_checksum_address, 99999).call()
        pending_eth = web3.Web3.from_wei(pending_wei, 'ether')
        return pending_eth
    except Exception as e:
        Util.log("Unable to get pending fees: '{0}'".format(e), 1)
        return 0.0

def doWithdrawFees():
    try:
        # We take a little bit off due to floating point inaccuracies causing tx's to fail
        pending = pendingFees()
        transfer_amount = web3.Web3.to_wei(float(pending), 'ether')
        receiver_address = State.orchestrator.source_checksum_address
        Util.log("{} {} WEI to {}".format("Dry-run withdrawing" if State.DRY_RUN else "Withdrawing", transfer_amount,
                                          State.orchestrator.source_address), 1)
        # Build transaction info
        transaction_obj = bonding_contract.functions.withdrawFees(receiver_address, transfer_amount).build_transaction(
            {
                "from": State.orchestrator.source_checksum_address,
                'maxFeePerGas': 2000000000,
                'maxPriorityFeePerGas': 1000000000,
                "nonce": w3.eth.get_transaction_count(State.orchestrator.source_checksum_address)
            }
        )
        # Sign and initiate transaction
        signed_transaction = w3.eth.account.sign_transaction(transaction_obj, State.orchestrator.source_private_key)
        print("DRY RUN: {0}".format(State.DRY_RUN))
        if State.DRY_RUN:
            Util.log("Dry run mode enabled, skip executing any on-chain transactions", 1)
            return
        transaction_hash = w3.eth.send_raw_transaction(signed_transaction.raw_transaction)
        Util.log("Initiated transaction with hash {0}".format(transaction_hash.hex()), 2)
        # Wait for transaction to be confirmed
        w3.eth.wait_for_transaction_receipt(transaction_hash)
        Util.log('Withdraw fees success.', 2)
    except Exception as e:
        Util.log("Unable to withdraw fees: '{0}'".format(e), 1)
        exit(1)


def getEthBalance():
    try:
        balance_wei = w3.eth.get_balance(State.orchestrator.source_checksum_address)
        balance_ETH = web3.Web3.from_wei(balance_wei, 'ether')
        return balance_ETH
    except Exception as e:
        Util.log("Unable to get ETH balance: '{0}'".format(e), 1)

def doFundDeposit(amount):
    try:
        receiver_address = State.orchestrator.target_checksum_address
        Util.log("Sending {0} ETH to Gateway's Deposit {1}".format(amount, State.orchestrator.target_address), 2)
        amount_wei = web3.Web3.to_wei(amount, 'ether')

        transaction_obj = ticket_broker_contract.functions.fundDepositAndReserveFor(receiver_address, amount_wei, 0).build_transaction(
            {
                "from": State.orchestrator.source_checksum_address,
                'maxFeePerGas': 2000000000,
                'maxPriorityFeePerGas': 1000000000,
                'value': amount_wei,
                "nonce": w3.eth.get_transaction_count(State.orchestrator.source_checksum_address),
                'gas': 300000,
            }
        )
        signed_transaction = w3.eth.account.sign_transaction(transaction_obj, State.orchestrator.source_private_key)
        if State.DRY_RUN:
            Util.log("Dry run mode enabled, skip executing any on-chain transactions", 1)
            return
        transaction_hash = w3.eth.send_raw_transaction(signed_transaction.raw_transaction)
        Util.log("Initiated transaction with hash {0}".format(transaction_hash.hex()), 2)
        # Wait for transaction to be confirmed
        w3.eth.wait_for_transaction_receipt(transaction_hash)
        Util.log('Fund deposit success.', 2)
    except Exception as e:
        Util.log("Unable to fund deposit: '{0}'".format(e), 1)
