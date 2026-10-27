import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


class BalanceExporterTests(unittest.TestCase):
    def setUp(self):
        self.w3 = Mock()
        self.w3.to_checksum_address.side_effect = lambda address: address
        self.w3.eth.get_balance.return_value = 1234567890123456789
        self.ticket_broker = Mock()
        self.ticket_broker.functions.getSenderInfo.return_value.call.return_value = (
            (2000000000000000001, 123),
            (3000000000000000002, 456),
        )
        contract = types.ModuleType('lib.Contract')
        contract.w3 = self.w3
        contract.ticket_broker_contract = self.ticket_broker
        module_path = Path(__file__).parents[1] / 'lib' / 'balance.py'
        spec = importlib.util.spec_from_file_location('lib.balance_under_test', module_path)
        self.balance = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'lib.Contract': contract}):
            spec.loader.exec_module(self.balance)

    def test_exports_native_deposit_and_remaining_reserve_without_losing_wei(self):
        self.balance.update_balances(['Agent:0xagent'])
        metrics = self.balance.render_metrics()

        self.ticket_broker.functions.getSenderInfo.assert_called_once_with('0xagent')
        for metric, value in (
            ('livepeer_eth_wallet_balance_wei', 1234567890123456789),
            ('livepeer_ticketbroker_deposit_wei', 2000000000000000001),
            ('livepeer_ticketbroker_reserve_wei', 3000000000000000002),
        ):
            self.assertIn(f'# TYPE {metric} gauge\n', metrics)
            self.assertIn(f'{metric}{{wallet="Agent",address="0xagent"}} {value}\n', metrics)

    def test_contract_failure_omits_stale_contract_values_and_continues_other_wallets(self):
        self.balance.ticket_balances['Agent', '0xagent'] = (1, 2)
        self.ticket_broker.functions.getSenderInfo.return_value.call.side_effect = [
            RuntimeError('RPC error'),
            ((3, 123), (4, 456)),
        ]

        self.balance.update_balances(['Agent:0xagent', 'Broadcaster:0xbroadcaster'])

        self.assertIn(('Agent', '0xagent'), self.balance.balances)
        self.assertNotIn(('Agent', '0xagent'), self.balance.ticket_balances)
        self.assertEqual(self.balance.ticket_balances['Broadcaster', '0xbroadcaster'], (3, 4))

    def test_plain_addresses_and_escaped_wallet_names_have_valid_labels(self):
        self.balance.update_balances(['0xplain', 'Agent"\\\n:0xagent'])
        metrics = self.balance.render_metrics()

        self.assertIn('livepeer_eth_wallet_balance_wei{address="0xplain"}', metrics)
        self.assertIn('wallet="Agent\\"\\\\\\n",address="0xagent"', metrics)

    def test_rpc_failure_waits_before_retrying(self):
        self.balance.balances['Agent', '0xagent'] = 1
        self.balance.ticket_balances['Agent', '0xagent'] = (2, 3)
        self.w3.eth.get_balance.side_effect = RuntimeError('RPC unavailable')
        with patch.object(self.balance.time, 'sleep', side_effect=InterruptedError) as sleep:
            with self.assertRaises(InterruptedError):
                self.balance.loop_get_balance(['Agent:0xagent'])

        sleep.assert_called_once_with(300)
        self.assertEqual(self.balance.balances, {})
        self.assertEqual(self.balance.ticket_balances, {})


if __name__ == '__main__':
    unittest.main()
