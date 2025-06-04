#!/bin/python3
import os
import click


@click.group()
def wallet_tools():
    pass


@wallet_tools.command('GetEthBalance')
@click.argument('eth_address', required=True)
def get_eth_balance(eth_address):
    from lib import Contract
    print(Contract.getEthBalance(eth_address))


@wallet_tools.command('EthBalanceExporter')
@click.argument('eth_address', required=True, nargs=-1)
def eth_balance_exporter(eth_address):
    from lib.balance import run_metrics_server
    run_metrics_server([eth_address])


@wallet_tools.command('FundDeposit')
def fund_deposit():
    os.environ['SKIP_FEES_WITHDRAWAL'] = 'True'
    from fees_to_deposit import withdraw_fees_and_fund_deposit
    withdraw_fees_and_fund_deposit()


@wallet_tools.command('WithdrawFeesIntoDeposit')
def withdraw_fees_into_deposit():
    from fees_to_deposit import withdraw_fees_and_fund_deposit
    withdraw_fees_and_fund_deposit()


if __name__ == '__main__':
    wallet_tools()
