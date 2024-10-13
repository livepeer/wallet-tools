#!/bin/python3
import requests
import web3
import json
import time
import sys
from datetime import datetime, timezone


# TODO: properly parse ETH key on disk, let's not put the private key in here like this

# TODO: notifications every time it transfers LPT, ETH , reward calls
# point it to an SMTP server or Telegram bot


### Global Config


# Don't change this class
class OrchConf:
  def __init__(self, key, pub, tgt):
    self._srcKey = key
    self._srcAddr = pub
    self._targetAddr = tgt

# Definitely change this. You can add multiple Orchestrators and separate them with a comma
ORCH_TARGETS = [
    OrchConf('InsertDelegatorPrivateKey', 'InsertDelegatorWalletAddress', 'InsertReceiverWalletAddress')
] 

# Fill in these to get Telegram notifications
# TODO

# Fill in these to get E-mail notifications
# TODO

# Optionally change these - remember to keep some ETH for reward calls, etc 
LPT_THRESHOLD = 100     #< Amount of pending stake before triggering TransferBond
ETH_THRESHOLD = 0.20    #< Amount of pending fees before triggering WithdrawFees
ETH_MINVAL = 0.02       #< Amount of ETH to keep in the wallet for ticket redemptions etc
ETH_MAXVAL = 0.20       #< Amount of ETH to trigger a withdrawal to the receiver
L2_RPC_PROVIDER = 'https://arb1.arbitrum.io/rpc'

### Wait times in seconds: higher values == less RPC calls being made
WAIT_TIME_ROUND_REFRESH = 60 * 15       #< Check for a change in round num or lock state
WAIT_TIME_LPT_REFRESH = 60 * 60 * 4     #< Check for a change in pending LPT
WAIT_TIME_ETH_REFRESH = 60 * 60 * 4     #< Check for a change in pending ETH
WAIT_TIME_IDLE = 60 #< Sleep time between each check for LPT or ETH thresholds being met

# Internal globals - Probably don't edit these
BONDING_CONTRACT_ADDR = '0x35Bcf3c30594191d53231E4FF333E8A770453e40'
ROUNDS_CONTRACT_ADDR = '0xdd6f56DcC28D3F5f27084381fE8Df634985cc39f'
lastRoundRefresh = 0
currentRoundNum = 0
currentRoundLocked = False
currentCheckTime = 0
orchestrators = []


### Utils


# Logs `info` to the terminal with an attached datetime
def log(info):
    print("[", datetime.now(), "] - ", info)
    sys.stdout.flush()

"""
@brief Returns a JSON object of ABI data
@param path: absolute/relative path to an ABI file
"""
def getABI(path):
    try:
        with open(path) as f:
            info_json = json.load(f)
            return info_json["abi"]
    except:
        log("Unable to extract ABI data. Is {0} a valid path?".format(path))
        exit(1)

"""
@brief Returns a JSON object of ABI data
@param path: absolute/relative path to an ABI file
"""
def getChecksumAddr(wallet):
    try:
        parsed_wallet = web3.Web3.to_checksum_address(wallet.lower())
        return parsed_wallet
    except:
        log("Unable to parse delegator wallet address. Is {0} a valid address?".format(wallet))
        exit(1)


### Define contracts


bondingABI = getABI("./BondingManagerTarget.json")
roundsABI = getABI("./RoundsManagerTarget.json")
# connect to L2 grpc provider
provider = web3.HTTPProvider(L2_RPC_PROVIDER)
w3 = web3.Web3(provider)
assert w3.is_connected()
# prepare contracts
bonding_contract = w3.eth.contract(address=BONDING_CONTRACT_ADDR, abi=bondingABI)
rounds_contract = w3.eth.contract(address=ROUNDS_CONTRACT_ADDR, abi=roundsABI)


### Main logic


# Round refresh logic


"""
@brief Refreshes the current round number
@return boolean: whether the round number has changed
"""
def refreshRound():
    global currentRoundNum
    try:
        thisRound = rounds_contract.functions.currentRound().call()
        if thisRound > currentRoundNum:
            log("Round number changed to '{0}'".format(currentRoundNum))
            currentRoundNum = thisRound
            return True
    except Exception as e:
        log("Unable to refresh round number: '{0}'".format(e))
    return False

"""
@brief Refreshes the current round lock status
"""
def refreshLock():
    global currentRoundLocked
    try:
        newLock = rounds_contract.functions.currentRoundLocked().call()
        currentRoundLocked = newLock
    except Exception as e:
        log("Unable to refresh round lock status: '{0}'".format(e))

# Gets the last round the orch called reward
def refreshRewardRound(idx):
    global orchestrators
    try:
        # get delegator info (returns [lastRewardRound, rewardCut, feeShare, 
        #                              lastActiveStakeUpdateRound, activationRound, deactivationRound,
        #                              activeCumulativeRewards, cumulativeRewards, cumulativeFees,
        #                              lastFeeRound])
        orchestratorInfo = bonding_contract.functions.getTranscoder(orchestrators[idx].parsedSrcAddr).call()
        orchestrators[idx].lastRewardRound = orchestratorInfo[0]
        log("Latest reward round for Orchestrator '{0}' is {1} and the latest livepeer round is {2}".format(orchestrators[idx].srcAddr, orchestrators[idx].lastRewardRound, currentRoundNum))
    except Exception as e:
        log("Unable to refresh round lock status: '{0}'".format(e))


# Orch LPT logic


"""
@brief Refresh Delegator pending LPT
"""
def refreshStake(idx):
    global orchestrators
    try:
        pending_lptu = bonding_contract.functions.pendingStake(orchestrators[idx].parsedSrcAddr, 99999).call()
        pending_lpt = web3.Web3.from_wei(pending_lptu, 'ether')
        orchestrators[idx].pendingLPT = pending_lpt;
        log("Delegator {0} is currently staking {1:.2f} LPT".format(orchestrators[idx].srcAddr, pending_lpt))
    except Exception as e:
        log("Unable to refresh stake: '{0}'".format(e))

"""
@brief Transfers all but 1 LPT stake to the configured destination wallet
"""
def doTransferBond(idx):
    global orchestrators
    try:
        transfer_amount = web3.Web3.to_wei(orchestrators[idx].pendingLPT - 1, 'ether')
        log("Should transfer {0} LPTU".format(transfer_amount))
        # Build transaction info
        tx = bonding_contract.functions.transferBond(orchestrators[idx].parsedTargetAddr, transfer_amount,
            web3.constants.ADDRESS_ZERO, web3.constants.ADDRESS_ZERO, web3.constants.ADDRESS_ZERO,
            web3.constants.ADDRESS_ZERO).build_transaction(
            {
                "from": orchestrators[idx].parsedSrcAddr,
                "gasPrice": 1000000000,
                "nonce": w3.eth.get_transaction_count(orchestrators[idx].parsedSrcAddr)
            }
        )
        # Sign and initiate transaction
        signedTx = w3.eth.account.sign_transaction(tx, orchestrators[idx].srcKey)
        transactionHash = w3.eth.send_raw_transaction(signedTx.raw_transaction)
        log("Initiated transaction with hash {0}".format(transactionHash))
        # Wait for transaction to be confirmed
        receipt = w3.eth.wait_for_transaction_receipt(transactionHash)
        log("Completed transaction {0}".format(receipt))
    except Exception as e:
        log("Unable to transfer bond: '{0}'".format(e))

def doCallReward(idx):
    global orchestrators
    try:
        log("Calling reward for Orchetrator '{0}'".format(orchestrators[idx].srcAddr))
        # Build transaction info
        tx = bonding_contract.functions.reward().build_transaction(
            {
                "from": orchestrators[idx].parsedSrcAddr,
                "gasPrice": 1000000000,
                "nonce": w3.eth.get_transaction_count(orchestrators[idx].parsedSrcAddr)
            }
        )
        # Sign and initiate transaction
        signedTx = w3.eth.account.sign_transaction(tx, orchestrators[idx].srcKey)
        transactionHash = w3.eth.send_raw_transaction(signedTx.raw_transaction)
        log("Initiated transaction with hash {0}".format(transactionHash))
        # Wait for transaction to be confirmed
        receipt = w3.eth.wait_for_transaction_receipt(transactionHash)
        log("Completed transaction {0}".format(receipt))
        log('Call to reward success.')
        orchestrators[i].hasCalledReward = True
    except Exception as e:
        log("Unable to call reward: '{0}'".format(e))
        orchestrators[i].hasCalledReward = False


# Orchestrator ETH logic


"""
@brief Refreshes pending ETH fees
"""
def refreshFees(idx):
    global orchestrators
    try:
        pending_wei = bonding_contract.functions.pendingFees(orchestrators[idx].parsedSrcAddr, 99999).call()
        pending_eth = web3.Web3.from_wei(pending_wei, 'ether')
        orchestrators[idx].pendingETH = pending_eth
        log("Delegator {0} has {1:.6f} ETH in pending fees".format(orchestrators[idx].srcAddr, pending_eth))
    except Exception as e:
        log("Unable to refresh fees: '{0}'".format(e))

"""
@brief Transfers all ETH minus the minval to the receiver wallet
"""
def doWithdrawFees(idx):
    global orchestrators
    try:
        log("Should withdraw {0} WEI".format(orchestrators[idx].pendingETH))
        # Build transaction info
        tx = bonding_contract.functions.withdrawFees(orchestrators[idx].parsedSrcAddr, orchestrators[idx].pendingETH).build_transaction(
            {
                "from": orchestrators[idx].parsedSrcAddr,
                "gasPrice": 1000000000,
                "nonce": w3.eth.get_transaction_count(orchestrators[idx].parsedSrcAddr)
            }
        )
        # Sign and initiate transaction
        signedTx = w3.eth.account.sign_transaction(tx, orchestrators[idx].srcKey)
        transactionHash = w3.eth.send_raw_transaction(signedTx.raw_transaction)
        log("Initiated transaction with hash {0}".format(transactionHash))
        # Wait for transaction to be confirmed
        receipt = w3.eth.wait_for_transaction_receipt(transactionHash)
        log("Completed transaction {0}".format(receipt))
    except Exception as e:
        log("Unable to withdraw fees: '{0}'".format(e))

"""
@brief Updates known ETH balance of the delegator
"""
def checkEthBalance(idx):
    global orchestrators
    try:
        weiBalance = w3.eth.get_balance(orchestrators[idx].parsedSrcAddr)
        ethBalance = web3.Web3.from_wei(weiBalance, 'ether')
        orchestrators[idx].ethBalance = ethBalance
        log("Delegator {0} currently has {1:.4f} ETH in their wallet".format(orchestrators[idx].srcAddr, ethBalance))
    except Exception as e:
        log("Unable to get ETH balance: '{0}'".format(e))

"""
@brief Transfers all ETH minus the minval to the receiver wallet
"""
def doSendFees(idx):
    global orchestrators
    try:
        transfer_amount = web3.Web3.to_wei(orchestrators[idx].pendingETH - ETH_MINVAL, 'ether')
        log("Should transfer {0} wei".format(transfer_amount))
        # Build transaction info
        tx = w3.eth.send_transaction(
            {
                "from": orchestrators[idx].parsedSrcAddr,
                "to": orchestrators[idx].parsedTargetAddr,
                "gasPrice": 1000000000,
                "nonce": w3.eth.get_transaction_count(orchestrators[idx].parsedSrcAddr),
                "value": transfer_amount
            }
        )
        # Sign and initiate transaction
        signedTx = w3.eth.account.sign_transaction(tx, orchestrators[idx].srcKey)
        transactionHash = w3.eth.send_raw_transaction(signedTx.raw_transaction)
        log("Initiated transaction with hash {0}".format(transactionHash))
        # Wait for transaction to be confirmed
        receipt = w3.eth.wait_for_transaction_receipt(transactionHash)
        log("Completed transaction {0}".format(receipt))
    except Exception as e:
        log("Unable to send ETH: '{0}'".format(e))


class Orchestrator:
    def __init__(self, obj):
        # Orch details
        self.srcKey = obj._srcKey
        self.srcAddr = obj._srcAddr
        self.parsedSrcAddr = getChecksumAddr(obj._srcAddr)
        self.targetAddr = obj._targetAddr
        self.parsedTargetAddr = getChecksumAddr(obj._targetAddr)
        # LPT details
        self.lastLptCheck = 0 #< Last time the Orch got it's pendingStake checked
        self.pendingLPT = 0 #< Current pending stake of the Orch
        # ETH details
        self.lastEthCheck = 0 #< Last time the Orch got it's pendingFees and ETH balance checked
        self.pendingETH = 0 #< Current pending fees of the Orch
        self.ethBalance = 0 #< Current ETH balance of the Orch
        # Round details
        self.lastRoundCheck = 0 #< Last time the Orch got it's reward round checked
        self.lastRewardRound = 0 #< Last round the Orch called reward
        self.hasCalledReward = False #< Stops checking for rewards during the current round after it succeeds

# Init orch objecs
for obj in ORCH_TARGETS:
    log("Adding Orchestrator '{0}'".format(obj._srcAddr))
    orchestrators.append(Orchestrator(obj))

# Main loop
while True:
    currentCheckTime = datetime.now(timezone.utc).timestamp()

    # Check for round updates
    if currentCheckTime < lastRoundRefresh + WAIT_TIME_ROUND_REFRESH:
        log("Refreshing round status in {0:.0f} seconds...".format(WAIT_TIME_ROUND_REFRESH - (currentCheckTime - lastRoundRefresh)))
    else:
        lastRoundRefresh = datetime.now(timezone.utc).timestamp()
        if refreshRound():
            # Reset hasCalledReward flags for all O's since the latest round has changed
            for j in range(len(orchestrators)):
                orchestrators[j].hasCalledReward = False
        refreshLock()

    # Main logic: check each Orch
    for i in range(len(orchestrators)):
        log("Refreshing Orchestrator '{0}'".format(orchestrators[i].srcAddr))

        # First check pending LPT -> TransferBond to receiver
        if currentCheckTime < orchestrators[i].lastLptCheck + WAIT_TIME_LPT_REFRESH:
            log("Refreshing pending LPT for {0} in {1:.0f} seconds...".format(orchestrators[i].srcAddr, WAIT_TIME_LPT_REFRESH - (currentCheckTime - orchestrators[i].lastLptCheck)))
        else:
            orchestrators[i].lastLptCheck = datetime.now(timezone.utc).timestamp()
            refreshStake(i)

        # Withdraw pending LPT at the end of round if threshold is reached
        if orchestrators[i].pendingLPT < LPT_THRESHOLD:
            log("Waiting for staked LPT for {0} to reach threshold {1}. Currently has a stake of {2:.2f} LPT.".format(orchestrators[i].srcAddr, LPT_THRESHOLD, orchestrators[i].pendingLPT))
        else:
            log("Delegator {0} has a stake of {1:.2f} LPT which exceeds the minimum threshold of {2:.2f}...".format(orchestrators[i].srcAddr, orchestrators[i].pendingLPT, LPT_THRESHOLD))
            doTransferBond(i)
            refreshStake(i)

        # Then check pending ETH -> WithdrawFees
        if currentCheckTime < orchestrators[i].lastEthCheck + WAIT_TIME_ETH_REFRESH:
            log("Checking {0}'s pending ETH fees in {1:.0f} seconds...".format(orchestrators[i].srcAddr, WAIT_TIME_ETH_REFRESH - (currentCheckTime - orchestrators[i].lastEthCheck)))
        else:
            orchestrators[i].lastEthCheck = datetime.now(timezone.utc).timestamp()
            refreshFees(i)
            checkEthBalance(i)

        # Withdraw pending ETH if threshold is reached 
        if orchestrators[i].pendingETH < ETH_THRESHOLD:
            log("Waiting for pending fees to reach threshold {0:.0f}.".format(ETH_THRESHOLD))
        else:
            log("Delegator {0} has {1:.4f} in ETH fees which exceeds the minimum threshold of {2:.2f}, continuing...".format(orchestrators[i].srcAddr, orchestrators[i].pendingETH, ETH_THRESHOLD))
            doWithdrawFees(i)
            checkEthBalance(i)

        # Check ETH balance -> transfer ETH to receiver
        if orchestrators[i].ethBalance < ETH_MAXVAL:
            log("Waiting for ETH in wallet of {0} to reach threshold {1}.".format(orchestrators[i].srcAddr, ETH_MAXVAL))
        else:
            log("Delegator {0} has {1:.4f} in ETH fees which exceeds the minimum threshold of {2:.2f}, continuing...".format(orchestrators[i].srcAddr, orchestrators[i].ethBalance, ETH_THRESHOLD))
            doSendFees(i)
            checkEthBalance(i)

        # Lastly: check if we need to call reward
        
        # We can continue immediately if the latest round has not changed
        if orchestrators[i].hasCalledReward:
            log("Done for Orchestrator '{0}' as they have called reward this round".format(orchestrators[i].srcAddr))
            continue

        # Refresh Orch reward round
        if currentCheckTime < orchestrators[i].lastRoundCheck + WAIT_TIME_ROUND_REFRESH:
            log("Checking {0}'s pending ETH fees in {1:.0f} seconds...".format(orchestrators[i].srcAddr, WAIT_TIME_ROUND_REFRESH - (currentCheckTime - orchestrators[i].lastRoundCheck)))
        else:
            orchestrators[i].lastRoundCheck = datetime.now(timezone.utc).timestamp()
            refreshRewardRound(i)

        # Call reward
        if orchestrators[i].lastRewardRound < currentRoundNum:
            log("Orchestrator {0} last called reward in round {1}, but the latest round is {2}".format(orchestrators[i].srcAddr, orchestrators[i].lastRewardRound, currentRoundNum))
            doCallReward(i)
        else:
            orchestrators[i].hasCalledReward = True
            log("Orchestrator {0} has already called reward in round {1}".format(orchestrators[i].srcAddr, currentRoundNum))

    # Sleep 30s until next refresh 
    delay = WAIT_TIME_IDLE
    while delay > 0:
        log("Sleeping for " + str(delay) + " more seconds...")
        delay = delay - 30
        if (delay > 30):
            time.sleep(30)
        else:
            time.sleep(delay)
