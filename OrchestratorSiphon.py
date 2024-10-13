#!/bin/python3
import requests
import web3
import json
import time
import sys
from datetime import datetime, timezone

# TODO: notifications every time it transfers LPT, ETH , reward calls
# point it to an SMTP server or Telegram bot


### Global Config


# Don't change this class
class OrchConf:
  def __init__(self, key, pw, pub, tgt):
    self._srcKeyPath = key
    self._srcKeyPwPath = pw
    self._srcAddr = pub
    self._targetAddr = tgt

# Definitely change this. You can add multiple Orchestrators and separate them with a comma
ORCH_TARGETS = [
    OrchConf(
        'path to livepeer keystore file',
        'path to file with keystore password',
        'orch public address, ie: 0x847791cbf03be716a7fe9dc8c9affe17bd49ae5e',
        'receiver public address, ie: 0x13c4299Cc484C9ee85c7315c18860d6C377c03bf'
    )
] 

# Fill in these to get Telegram notifications
# TODO

# Fill in these to get E-mail notifications
# TODO

# Optionally change these - remember to keep some ETH for reward calls, etc 
LPT_THRESHOLD = 100     #< Amount of pending stake before triggering TransferBond
ETH_THRESHOLD = 0.20    #< Amount of pending fees before triggering WithdrawFees
ETH_MINVAL = 0.02       #< Amount of ETH to keep in the wallet for ticket redemptions etc
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
    except Exception as e:
        log("Unable to extract ABI data: {0}".format(e))
        exit(1)

"""
@brief Returns a JSON object of ABI data
@param path: absolute/relative path to an ABI file
"""
def getChecksumAddr(wallet):
    try:
        parsed_wallet = web3.Web3.to_checksum_address(wallet.lower())
        return parsed_wallet
    except Exception as e:
        log("Unable to parse wallet address: {0}".format(e))
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
    global lastRoundRefresh
    try:
        thisRound = rounds_contract.functions.currentRound().call()
        lastRoundRefresh = datetime.now(timezone.utc).timestamp()
        if thisRound > currentRoundNum:
            log("Round number changed to {0}".format(thisRound))
            currentRoundNum = thisRound
            return True
    except Exception as e:
        log("Unable to refresh round number: {0}".format(e))
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
        log("Unable to refresh round lock status: {0}".format(e))

# Gets the last round the orch called reward
def refreshRewardRound(idx):
    global orchestrators
    try:
        # getTranscoder      (returns [lastRewardRound, rewardCut, feeShare, 
        #                              lastActiveStakeUpdateRound, activationRound, deactivationRound,
        #                              activeCumulativeRewards, cumulativeRewards, cumulativeFees,
        #                              lastFeeRound])
        orchestratorInfo = bonding_contract.functions.getTranscoder(orchestrators[idx].parsedSrcAddr).call()
        orchestrators[idx].lastRewardRound = orchestratorInfo[0]
        orchestrators[idx].lastRoundCheck = datetime.now(timezone.utc).timestamp()
        log("Latest reward round for {0} is {1}".format(orchestrators[idx].srcAddr, orchestrators[idx].lastRewardRound))
    except Exception as e:
        log("Unable to refresh round lock status: {0}".format(e))


# Orch LPT logic


"""
@brief Refresh Delegator pending LPT
"""
def refreshStake(idx):
    global orchestrators
    try:
        pending_lptu = bonding_contract.functions.pendingStake(orchestrators[idx].parsedSrcAddr, 99999).call()
        pending_lpt = web3.Web3.from_wei(pending_lptu, 'ether')
        orchestrators[idx].pendingLPT = pending_lpt
        orchestrators[idx].lastLptCheck = datetime.now(timezone.utc).timestamp()
        log("{0} currently has {1:.2f} LPT available for unstaking".format(orchestrators[idx].srcAddr, pending_lpt))
    except Exception as e:
        log("Unable to refresh stake: '{0}'".format(e))

"""
@brief Transfers all but 1 LPT stake to the configured destination wallet
"""
def doTransferBond(idx):
    global orchestrators
    try:
        transfer_amount = web3.Web3.to_wei(float(orchestrators[idx].pendingLPT) - 1, 'ether')
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
        # log("Completed transaction {0}".format(receipt))
        log('Transfer bond success.')
    except Exception as e:
        log("Unable to transfer bond: {0}".format(e))

def doCallReward(idx):
    global orchestrators
    try:
        log("Calling reward for {0}".format(orchestrators[idx].srcAddr))
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
        # log("Completed transaction {0}".format(receipt))
        log('Call to reward success.')
        orchestrators[i].hasCalledReward = True
    except Exception as e:
        log("Unable to call reward: {0}".format(e))
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
        orchestrators[idx].lastEthCheck = datetime.now(timezone.utc).timestamp()
        log("{0} has {1:.6f} ETH in pending fees".format(orchestrators[idx].srcAddr, pending_eth))
    except Exception as e:
        log("Unable to refresh fees: '{0}'".format(e))

"""
@brief Withdraws all fees to the receiver wallet
"""
def doWithdrawFees(idx):
    global orchestrators
    try:
        transfer_amount = web3.Web3.to_wei(float(orchestrators[idx].pendingETH) - 0.00001, 'ether')
        log("Should withdraw {0} WEI".format(transfer_amount))
        # Build transaction info
        tx = bonding_contract.functions.withdrawFees(orchestrators[idx].parsedTargetAddr, transfer_amount).build_transaction(
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
        # log("Completed transaction {0}".format(receipt))
        log('Withdraw fees success.')
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
        log("{0} currently has {1:.4f} ETH in their wallet".format(orchestrators[idx].srcAddr, ethBalance))
    except Exception as e:
        log("Unable to get ETH balance: '{0}'".format(e))

"""
@brief Transfers all ETH minus the minval to the receiver wallet
"""
def doSendFees(idx):
    global orchestrators
    try:
        if ETH_MINVAL > orchestrators[idx].ethBalance:
            log("Cannot transfer ETH, as the minimum value to leave behind is larger than the balance")
            return
        transfer_amount = web3.Web3.to_wei(float(orchestrators[idx].ethBalance) - ETH_MINVAL, 'ether')
        log("Should transfer {0} wei".format(transfer_amount))
        # Build transaction info
        tx = {
            'from': orchestrators[idx].parsedSrcAddr,
            'to': orchestrators[idx].parsedTargetAddr,
            'value': transfer_amount,
            "nonce": w3.eth.get_transaction_count(orchestrators[idx].parsedSrcAddr),
            'gas': 200000,
            'maxFeePerGas': 2000000000,
            'maxPriorityFeePerGas': 1000000000,
            'chainId': 42161
        }

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
        self.srcAddr = obj._srcAddr
        # Get private key
        with open(obj._srcKeyPath) as keyfile:
            encrypted_key = keyfile.read()
            with open(obj._srcKeyPwPath) as pwfile:
                keyPw = pwfile.read()
                self.srcKey = w3.eth.account.decrypt(encrypted_key, keyPw.rstrip('\n'))
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
        if currentRoundLocked:
            log("(cached) Round status: round {0} (locked). Refreshing in {1:.0f} seconds...".format(currentRoundNum, WAIT_TIME_ROUND_REFRESH - (currentCheckTime - lastRoundRefresh)))
        else:
            log("(cached) Round status: round {0} (unlocked). Refreshing in {1:.0f} seconds...".format(currentRoundNum, WAIT_TIME_ROUND_REFRESH - (currentCheckTime - lastRoundRefresh)))
    else:
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
            log("(cached) {0}'s pending stake is {1:.2f} LPT. Refreshing in {2:.0f} seconds...".format(orchestrators[i].srcAddr, orchestrators[i].pendingLPT, WAIT_TIME_LPT_REFRESH - (currentCheckTime - orchestrators[i].lastLptCheck)))
        else:
            refreshStake(i)

        # Withdraw pending LPT at the end of round if threshold is reached
        if orchestrators[i].pendingLPT < LPT_THRESHOLD:
            log("{0} has {1:.2f} LPT in pending stake < threshold {2:.2f}.".format(orchestrators[i].srcAddr, orchestrators[i].pendingLPT, LPT_THRESHOLD))
        else:
            log("{0} has {1:.2f} LPT pending stake > threshold {2:.2f}, transferring bond...".format(orchestrators[i].srcAddr, orchestrators[i].pendingLPT, LPT_THRESHOLD))
            if currentRoundLocked:
                doTransferBond(i)
                refreshStake(i)
            else:
                log("Waiting for round to be locked before transferring bond")

        # Then check pending ETH -> WithdrawFees
        if currentCheckTime < orchestrators[i].lastEthCheck + WAIT_TIME_ETH_REFRESH:
            log("(cached) {0}'s pending fees is {1:.4f} ETH. Refreshing in {2:.0f} seconds...".format(orchestrators[i].srcAddr, orchestrators[i].pendingETH, WAIT_TIME_ETH_REFRESH - (currentCheckTime - orchestrators[i].lastEthCheck)))
        else:
            refreshFees(i)
            checkEthBalance(i)

        # Withdraw pending ETH if threshold is reached 
        if orchestrators[i].pendingETH < ETH_THRESHOLD:
            log("{0} has {1:.4f} ETH in pending fees < threshold {2:.4f}.".format(orchestrators[i].srcAddr, orchestrators[i].pendingETH, ETH_THRESHOLD))
        else:
            log("{0} has {1:.4f} in ETH pending fees > threshold {2:.4f}, withdrawing fees...".format(orchestrators[i].srcAddr, orchestrators[i].pendingETH, ETH_THRESHOLD))
            doWithdrawFees(i)
            checkEthBalance(i)

        # Check ETH balance -> transfer ETH to receiver
        if orchestrators[i].ethBalance < ETH_THRESHOLD:
            log("{0} has {1:.4f} ETH in their wallet < threshold {2:.4f}.".format(orchestrators[i].srcAddr, orchestrators[i].ethBalance, ETH_THRESHOLD))
        else:
            log("{0} has {1:.4f} in ETH pending fees > threshold {2:.4f}, sending ETH to {3}...".format(orchestrators[i].srcAddr, orchestrators[i].ethBalance, ETH_THRESHOLD, orchestrators[i].targetAddr))
            doSendFees(i)
            checkEthBalance(i)

        # Lastly: check if we need to call reward
        
        # We can continue immediately if the latest round has not changed
        if orchestrators[i].hasCalledReward:
            log("Done for '{0}' as they have called reward this round".format(orchestrators[i].srcAddr))
            continue

        # Refresh Orch reward round
        if currentCheckTime < orchestrators[i].lastRoundCheck + WAIT_TIME_ROUND_REFRESH:
            log("(cached) {0}'s last reward round is {1}. Refreshing in {2:.0f} seconds...".format(orchestrators[i].srcAddr, orchestrators[i].lastRewardRound, WAIT_TIME_ROUND_REFRESH - (currentCheckTime - orchestrators[i].lastRoundCheck)))
        else:
            refreshRewardRound(i)

        # Call reward
        if orchestrators[i].lastRewardRound < currentRoundNum:
            log("{0} last called reward in round {1}, but the latest round is {2}. Calling reward...".format(orchestrators[i].srcAddr, orchestrators[i].lastRewardRound, currentRoundNum))
            doCallReward(i)
            refreshRewardRound(i)
        else:
            orchestrators[i].hasCalledReward = True
            log("{0} has already called reward in round {1}".format(orchestrators[i].srcAddr, currentRoundNum))

    # Sleep 30s until next refresh 
    delay = WAIT_TIME_IDLE
    while delay > 0:
        log("Sleeping for " + str(delay) + " more seconds...")
        if (delay > 30):
            delay = delay - 30
            time.sleep(30)
        else:
            time.sleep(delay)
            delay = 0
