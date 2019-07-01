from datatype_tools.lib import *
from print_tools.printer import Printer
from fast_arrow import Client, OptionChain, Option, OptionPosition, OptionOrder

#: Login

p = Printer()
client = Client()
client.authenticate()

#: Get Positions

positions = OptionPosition.all(client)
positions = list(filter(lambda p: float(p["quantity"]) > 0.0, positions))

if (len(positions) > 0):
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
else:
	p.bullet('No open positions.')

#::: End Program :::