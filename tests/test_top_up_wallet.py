from decimal import Decimal
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock


class TopUpWalletTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.util = types.SimpleNamespace(log=Mock())
        cls.contract = types.SimpleNamespace(
            getEthBalance=Mock(),
            doTransferEth=Mock(),
        )
        cls.state = types.SimpleNamespace()
        fake_lib = types.ModuleType("lib")
        fake_lib.Util = cls.util
        fake_lib.Contract = cls.contract
        fake_lib.State = cls.state

        cls.original_lib = sys.modules.get("lib")
        sys.modules["lib"] = fake_lib

        module_path = Path(__file__).parents[1] / "top_up_wallet.py"
        spec = importlib.util.spec_from_file_location("top_up_wallet_under_test", module_path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.module.SourceWallet = Mock()

    @classmethod
    def tearDownClass(cls):
        if cls.original_lib is None:
            sys.modules.pop("lib", None)
        else:
            sys.modules["lib"] = cls.original_lib

    def setUp(self):
        self.util.log.reset_mock()
        self.contract.getEthBalance.reset_mock()
        self.contract.getEthBalance.side_effect = None
        self.contract.doTransferEth.reset_mock()
        self.module.SourceWallet.reset_mock()

        self.state.TOP_UP_ADDRESS = "0xbb9ad59B3EF21F4B1300a8Ba9556E5FE6df8a254"
        self.state.TOP_UP_MIN_BALANCE = Decimal("0.0002")
        self.state.TOP_UP_AMOUNT = Decimal("0.002")
        self.state.ETH_MINVAL = 0.3
        self.state.DRY_RUN = False
        self.state.KEYSTORE_CONFIGS = [object()]
        self.state.orchestrator = types.SimpleNamespace(
            source_checksum_address="0xsource",
        )
        self.module.SourceWallet.return_value = types.SimpleNamespace(
            source_checksum_address="0xsource",
        )

    def test_below_threshold_sends_fixed_amount(self):
        self.contract.getEthBalance.side_effect = [
            Decimal("0.000199"),
            Decimal("0.302"),
        ]

        self.module.top_up_wallet()

        self.contract.doTransferEth.assert_called_once_with(
            self.state.TOP_UP_ADDRESS, Decimal("0.002")
        )

    def test_at_threshold_is_skipped(self):
        self.contract.getEthBalance.return_value = Decimal("0.0002")

        self.module.top_up_wallet()

        self.contract.doTransferEth.assert_not_called()

    def test_source_floor_is_preserved(self):
        self.contract.getEthBalance.side_effect = [
            Decimal("0.0001"),
            Decimal("0.301"),
        ]

        self.module.top_up_wallet()

        self.contract.doTransferEth.assert_not_called()

    def test_dry_run_returns_planned_spend(self):
        self.state.DRY_RUN = True
        self.contract.getEthBalance.side_effect = [
            Decimal("0.0001"),
            Decimal("0.4"),
        ]

        planned_spend = self.module.top_up_wallet()

        self.assertEqual(planned_spend, Decimal("0.002"))

    def test_missing_address_disables_top_up(self):
        self.state.TOP_UP_ADDRESS = ""

        self.module.top_up_wallet()

        self.module.SourceWallet.assert_not_called()
        self.contract.getEthBalance.assert_not_called()


if __name__ == "__main__":
    unittest.main()
