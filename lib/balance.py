from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import time

from .Contract import w3


balances = {}


def loop_get_balance(addresses):
    while True:
        for address in addresses:
            if ':' in address:
                name, eth_address = address.split(':')
            else:
                name, eth_address = None, address
            address_normalised = w3.to_checksum_address(eth_address)
            balance_wei = w3.eth.get_balance(address_normalised)
            balances[name, address_normalised] = balance_wei
            print(f"Balance for {address_normalised}: {balance_wei} wei")
        time.sleep(60 * 5)  # Sleep for 5 minutes


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            metrics = \
                "# HELP livepeer_eth_wallet_balance_wei Ethereum wallet balance in wei\n" \
                "# TYPE livepeer_eth_wallet_balance_wei gauge\n"
            for (name, eth_address), balance in balances.items():
                if name:
                    name_label = f'name="{name}",'
                else:
                    name_label = ''
                metrics += f"livepeer_eth_wallet_balance_wei{{{name_label}address=\"{eth_address}\"}} {balance}\n"
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(metrics.encode('utf-8'))
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
