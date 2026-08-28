import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock


class FundReserveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.util = types.SimpleNamespace(log=Mock())
        cls.contract = types.SimpleNamespace(
            getEthBalance=Mock(),
            doFundReserve=Mock(),
        )
        cls.state = types.SimpleNamespace(
            DRY_RUN=False,
            ETH_MINVAL=0.1,
            orchestrator=types.SimpleNamespace(
                source_checksum_address="0xsource",
            ),
        )
        fake_lib = types.ModuleType("lib")
        fake_lib.Util = cls.util
        fake_lib.Contract = cls.contract
        fake_lib.State = cls.state

        cls.original_lib = sys.modules.get("lib")
        sys.modules["lib"] = fake_lib

        module_path = Path(__file__).parents[1] / "fees_to_deposit.py"
        spec = importlib.util.spec_from_file_location(
            "fees_to_deposit_under_test", module_path
        )
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

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
        self.contract.doFundReserve.reset_mock()

    def test_non_positive_amount_exits_without_sending(self):
        with self.assertRaises(SystemExit):
            self.module.fund_reserve(0)

        self.contract.getEthBalance.assert_not_called()
        self.contract.doFundReserve.assert_not_called()

    def test_source_below_minimum_exits_without_negative_maximum(self):
        self.contract.getEthBalance.return_value = 0.09

        with self.assertRaises(SystemExit):
            self.module.fund_reserve(0.01)

        log_message = self.util.log.call_args.args[0]
        self.assertNotIn("-0.", log_message)
        self.contract.doFundReserve.assert_not_called()

    def test_amount_that_breaches_source_minimum_exits_without_sending(self):
        self.contract.getEthBalance.return_value = 0.15

        with self.assertRaises(SystemExit):
            self.module.fund_reserve(0.06)

        self.contract.doFundReserve.assert_not_called()

    def test_valid_amount_funds_reserve(self):
        self.contract.getEthBalance.return_value = 0.2

        self.module.fund_reserve(0.05)

        self.contract.doFundReserve.assert_called_once_with(0.05)


if __name__ == "__main__":
    unittest.main()
