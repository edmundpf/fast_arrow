import os
from datatype_tools.lib import *
from print_tools.printer import Printer
from file_tools.json_file import import_json, export_json
from fast_arrow import Client, OptionChain, Option, OptionPosition, OptionOrder

#: Login

cur_path = os.path.abspath(__file__)
config = import_json('../data/config.json', path=cur_path)
auth_data = import_json('../data/login_data.json', path=cur_path)

username = config['u_n'].b64_dec()
password = config['p_w'].b64_dec()
device_token = config['d_t'].b64_dec()

client = Client(username=username, password=password, device_token=device_token)
client.authenticate()

#: Get Positions

positions = OptionPosition.all(client)
positions = list(filter(lambda p: float(p["quantity"]) > 0.0, positions))
positions = OptionPosition.mergein_marketdata_list(client, positions)
positions = OptionPosition.mergein_instrumentdata_list(client, positions)
positions = OptionPosition.mergein_orderdata_list(client, positions)

#: Get Most Recent Order

symbol = positions[0]['chain_symbol']
strat = positions[0]['option_type']
effect = positions[0]['type']
buy_price = positions[0]['average_price']
bid_price = positions[0]['bid_price']
expiration_date = positions[0]['expiration_date']
quantity = positions[0]['quantity']
url = positions[0]['instrument']

p = Printer()
p.chevron(f'{symbol}-{expiration_date}-{effect}-{strat}, Quantity: {quantity}, Buy: {buy_price}, Bid: {bid_price}')

#: Place Order

direction = "credit"

legs = [{ "side": "sell",
    "option": url,
    "position_effect": "close",
    "ratio_quantity": 1 }]

quantity = 1
time_in_force = "gfd"
trigger = "immediate"
order_type = "limit"

order = OptionOrder.submit(client, direction, legs, bid_price, quantity, time_in_force, trigger, order_type)

p.bullet('Option order placed.')

#::: End Program :::