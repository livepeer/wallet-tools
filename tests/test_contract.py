from pathlib import Path
import importlib.util
import sys
import types
import unittest
from unittest.mock import Mock


class FakeWeb3:
    @staticmethod
    def to_checksum_address(address):
        return address

    @staticmethod
    def to_wei(amount, unit):
        assert unit == "ether"
        return int(amount * 10**18)

    @staticmethod
    def from_wei(amount, unit):
        assert unit == "ether"
        return amount / 10**18

    def __init__(self, provider):
        self.provider = provider
        self.eth = types.SimpleNamespace(
            chain_id=42161,
            contract=Mock(return_value=Mock()),
            get_transaction_count=Mock(return_value=1),
            account=types.SimpleNamespace(
                sign_transaction=Mock(
                    return_value=types.SimpleNamespace(raw_transaction=b"signed")
                )
            ),
            send_raw_transaction=Mock(),
            wait_for_transaction_receipt=Mock(),
        )

    def is_connected(self):
        return True


class ContractDryRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_lib = sys.modules.get("lib")
        cls.original_web3 = sys.modules.get("web3")

        cls.state = types.SimpleNamespace(
            ROOT_DIR=Path(__file__).parents[1],
            L2_RPC_PROVIDER="http://example.invalid",
            DRY_RUN=True,
            orchestrator=types.SimpleNamespace(
                source_checksum_address="0xsource",
                source_private_key=b"private-key",
            ),
        )
        cls.util = types.SimpleNamespace(log=Mock())
        fake_lib = types.ModuleType("lib")
        fake_lib.State = cls.state
        fake_lib.Util = cls.util
        sys.modules["lib"] = fake_lib

        fake_web3 = types.ModuleType("web3")
        fake_web3.HTTPProvider = lambda url: url
        fake_web3.Web3 = FakeWeb3
        sys.modules["web3"] = fake_web3

        module_path = Path(__file__).parents[1] / "lib" / "Contract.py"
        spec = importlib.util.spec_from_file_location("contract_under_test", module_path)
        cls.contract = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.contract)

    @classmethod
    def tearDownClass(cls):
        if cls.original_lib is None:
            sys.modules.pop("lib", None)
        else:
            sys.modules["lib"] = cls.original_lib
        if cls.original_web3 is None:
            sys.modules.pop("web3", None)
        else:
            sys.modules["web3"] = cls.original_web3

    def test_native_transfer_dry_run_signs_but_does_not_broadcast(self):
        self.contract.doTransferEth("0xtarget", 0.002)

        signed_transaction = self.contract.w3.eth.account.sign_transaction.call_args.args[0]
        self.assertEqual(signed_transaction["gas"], 100000)
        self.assertEqual(signed_transaction["chainId"], 42161)
        self.contract.w3.eth.send_raw_transaction.assert_not_called()
        self.contract.w3.eth.wait_for_transaction_receipt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
