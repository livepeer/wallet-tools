#!/usr/bin/python3
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


@wallet_tools.command('FundReserve')
@click.argument('amount', required=True, type=float)
def fund_reserve_command(amount):
    from fees_to_deposit import run_fund_reserve
    run_fund_reserve(amount)


@wallet_tools.command('TopUpWallet')
def top_up_wallet_command():
    from top_up_wallet import run_top_up_wallet
    run_top_up_wallet()


@wallet_tools.command('WithdrawFeesIntoDeposit')
def withdraw_fees_into_deposit():
    from fees_to_deposit import withdraw_fees_and_fund_deposit
    withdraw_fees_and_fund_deposit()


@wallet_tools.command('WithdrawFeesTopUpAndFundDeposit')
def withdraw_fees_top_up_and_fund_deposit_command():
    from fees_to_deposit import configure_orchestrator, fund_deposit, withdraw_fees
    from top_up_wallet import top_up_wallet

    configure_orchestrator()
    withdraw_fees()
    planned_spend = top_up_wallet()
    fund_deposit(planned_spend)


if __name__ == '__main__':
    wallet_tools()
