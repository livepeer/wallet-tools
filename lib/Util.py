# Contains all generic functions separate from the main logic
# These are shared between all libraries and the main script

import os
import logging
import web3
from eth_account.account import Account


log = logging.getLogger(__name__)


def getChecksumAddr(wallet) -> str:
    """
    Returns a checksum version of a wallet to be used for contract calls

    :param wallet: public key of a wallet
    """
    try:
        return web3.Web3.to_checksum_address(wallet.lower())
    except Exception:
        log.exception("Fatal error: Unable to parse wallet address")
        exit(1)


def checkPath(file_path):
    """
    Checks if a string is a valid filepath

    :param str file_path: absolute/relative path on the filesystem
    :return boolean: True if a valid file, else False
    """
    if not isinstance(file_path, str):
        return False
    return os.path.isfile(file_path)


def getPrivateKey(keystore_path, password) -> str | None:
    """
    Returns the private key of a wallet

    :param str keystore_path: absolute/relative path to a keystore file
    :param str password: the password itself or a absolute/relative path to a text file with the password
    """
    try:
        with open(keystore_path) as key_file:
            encrypted_key = key_file.read()
            if checkPath(password):
                with open(password) as password_file:
                    key_password = password_file.read()
                    return Account.decrypt(encrypted_key, key_password.rstrip('\n'))
            else:
                return Account.decrypt(encrypted_key, password)
    except Exception:
        log.exception("Unable to decrypt key")
        return
