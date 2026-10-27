# Livepeer Script to Transfer Orchestrator Fees into Gateway's Deposit

## Usage

1. Fill `config.ini` or set up corresponding env variables.
2. Start `./wallet_tools.py`


## Wallet balance metrics

`EthBalanceExporter` accepts `Name:0xaddress` arguments and polls Arbitrum every
five minutes. It exposes the following gauges at `/metrics` on port 8000, each
with `wallet` (when named) and `address` labels:

- `livepeer_eth_wallet_balance_wei`: native ETH held by the wallet.
- `livepeer_ticketbroker_deposit_wei`: the wallet's TicketBroker deposit.
- `livepeer_ticketbroker_reserve_wei`: the wallet's remaining TicketBroker reserve.

Divide these values by `1e18` to display ETH in Grafana. TicketBroker balances
are collected through read-only `getSenderInfo` calls; no signing key is needed.
Failed reads omit the affected values until the next successful poll.
