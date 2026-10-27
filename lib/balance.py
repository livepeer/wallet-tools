from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import time

from .Contract import ticket_broker_contract, w3


balances = {}
ticket_balances = {}


def update_balances(addresses):
    for address in addresses:
        if ':' in address:
            name, eth_address = address.split(':', 1)
        else:
            name, eth_address = None, address
        key = None
        try:
            address_normalised = w3.to_checksum_address(eth_address)
            key = name, address_normalised
            balance_wei = w3.eth.get_balance(address_normalised)
            balances[key] = balance_wei
            print(f"Balance for {address_normalised}: {balance_wei} wei")
        except Exception as e:
            if key is not None:
                balances.pop(key, None)
                ticket_balances.pop(key, None)
            print(f"Error fetching balance for {eth_address}: {e}")
            continue

        try:
            sender, reserve = ticket_broker_contract.functions.getSenderInfo(address_normalised).call()
            ticket_balances[key] = sender[0], reserve[0]
        except Exception as e:
            # Omit failed contract reads instead of presenting old values as current.
            ticket_balances.pop(key, None)
            print(f"Error fetching TicketBroker balances for {address_normalised}: {e}")


def loop_get_balance(addresses):
    while True:
        update_balances(addresses)
        print("Balances updated, sleeping for 5 minutes...")
        time.sleep(60 * 5)  # Sleep for 5 minutes


def render_metrics():
    tickets = ticket_balances.copy()
    metrics = [
        ('livepeer_eth_wallet_balance_wei', 'Ethereum wallet balance in wei', balances.copy()),
        ('livepeer_ticketbroker_deposit_wei', 'Livepeer TicketBroker deposit in wei',
         {key: value[0] for key, value in tickets.items()}),
        ('livepeer_ticketbroker_reserve_wei', 'Livepeer TicketBroker remaining reserve in wei',
         {key: value[1] for key, value in tickets.items()}),
    ]
    lines = []
    for metric, description, values in metrics:
        lines.extend((f'# HELP {metric} {description}', f'# TYPE {metric} gauge'))
        for (name, eth_address), value in values.items():
            if name:
                name = name.replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')
                name_label = f'wallet="{name}",'
            else:
                name_label = ''
            lines.append(f'{metric}{{{name_label}address="{eth_address}"}} {value}')
    return '\n'.join(lines) + '\n'


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_metrics().encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()


def run_metrics_server(addresses):
    thread = threading.Thread(target=loop_get_balance, daemon=True, args=addresses)
    thread.start()

    httpd = HTTPServer(('', 8000), MetricsHandler)
    print("Serving /metrics on port 8000")
    httpd.serve_forever()

    thread.join()
