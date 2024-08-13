import logging
import re
import urllib
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Union

import requests

from utils import get_wear_condition


class MarketOperations:
    def __init__(self, steam_client, tradeup_api, config):
        self.steam_client = steam_client
        self.tradeup_api = tradeup_api
        self.config = config
        self.active_buy_orders = {}
        self.item_nameid_cache = {}

    def place_buy_orders(self, tradeup_data: Dict):
        is_stattrak = tradeup_data['statTrak']

        grouped_items = self._group_items(tradeup_data['skinList'])

        for (collection, wear_condition), items in grouped_items.items():
            max_price = max(Decimal(str(item['price'])) for item in items)

            interchangeable_items = self.tradeup_api.get_interchangeable_items(items[0], is_stattrak)

            highest_buy_order = self._get_highest_buy_order(interchangeable_items, wear_condition, is_stattrak)

            if self._should_place_buy_order(highest_buy_order, max_price):
                price = highest_buy_order
                quantity = len(items)
                self._place_buy_orders_for_items(interchangeable_items, is_stattrak, wear_condition, quantity, price)

    def _group_items(self, items: List[Dict]) -> Dict:
        grouped_items = defaultdict(list)
        for item in items:
            collection = item['collection']['name']
            wear_condition = get_wear_condition(item['fv'])
            grouped_items[(collection, wear_condition)].append(item)
        return grouped_items

    def _get_highest_buy_order(self, items: List[Dict], wear_condition: str, is_stattrak: bool) -> Decimal:
        highest_buy_order = Decimal('0')
        for item in items:
            current_buy_order = self._get_item_highest_buy_order(item['name'], wear_condition, is_stattrak)
            highest_buy_order = max(highest_buy_order, current_buy_order)
        return highest_buy_order

    def _get_item_highest_buy_order(self, item_name: str, wear: str, is_stattrak: bool) -> Decimal:
        full_item_name = f"{'StatTrak™ ' if is_stattrak else ''}{item_name} ({wear})"
        try:
            histogram_data = self._fetch_item_orders_histogram(full_item_name)
            if not histogram_data:
                return Decimal('0')

            highest_buy_order = histogram_data.get('highest_buy_order')
            if highest_buy_order:
                return Decimal(str(highest_buy_order)) / 100  # Convert cents to euros
            return Decimal('0')
        except Exception as e:
            logging.error(f"Failed to get highest buy order for {full_item_name}: {e}")
            return Decimal('0')

    def _fetch_item_orders_histogram(self, item_name: str) -> Dict:
        item_nameid = self._get_item_nameid(item_name)
        if not item_nameid:
            logging.error(f"Failed to get item_nameid for {item_name}")
            return {}

        url = "https://steamcommunity.com/market/itemordershistogram"
        params = {
            "country": "DE",
            "language": "english",
            "currency": 3,  # EUR
            "item_nameid": item_nameid
        }

        try:
            response = self.steam_client._session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logging.error(f"Failed to fetch item orders histogram for {item_name}: {e}")
            return {}

    def _get_item_nameid(self, item_name: str) -> Union[str, None]:
        if item_name in self.item_nameid_cache:
            return self.item_nameid_cache[item_name]

        market_page_url = f"https://steamcommunity.com/market/listings/730/{urllib.parse.quote(item_name)}"
        try:
            response = self.steam_client._session.get(market_page_url)
            response.raise_for_status()
            match = re.search(r'Market_LoadOrderSpread\(\s*(\d+)\s*\)', response.text)
            if match:
                item_nameid = match.group(1)
                self.item_nameid_cache[item_name] = item_nameid
                return item_nameid
        except requests.RequestException as e:
            logging.error(f"Failed to get item_nameid for {item_name}: {e}")
        return None

    def _should_place_buy_order(self, current_highest_buy_order: Decimal, max_price: Decimal) -> bool:
        return current_highest_buy_order < max_price

    def _place_buy_orders_for_items(self, items: List[Dict], is_stattrak: bool, wear_condition: str, quantity: int,
                                    price: Decimal):
        for item in items:
            full_item_name = f"{'StatTrak™ ' if is_stattrak else ''}{item['name']} ({wear_condition})"
            try:
                logging.info(f"Attempting to place buy order for {quantity} {full_item_name} at {price} each")

                if self.config.enable_orders:
                    response = self.steam_client.create_buy_order(
                        full_item_name,
                        str(int(price * 100)),
                        quantity
                    )
                    order_id = self._process_buy_order_response(response, full_item_name, quantity, price)
                    if order_id:
                        self.active_buy_orders[order_id] = {
                            'name': full_item_name,
                            'quantity': quantity,
                            'price': price
                        }
                        logging.info(f"Placed buy order {order_id} for {quantity} {full_item_name} at {price} each")
                else:
                    logging.info(
                        f"SIMULATION: Would have placed buy order for {quantity} {full_item_name} at {price} each")
            except Exception as e:
                logging.error(f"Failed to place buy order for {full_item_name}: {e}")
                logging.exception("Traceback:")

    def _process_buy_order_response(self, response: Union[Dict, List], item_name: str, quantity: int, price: Decimal) -> \
            Union[str, None]:
        if isinstance(response, dict):
            return response.get('buy_orderid')
        elif isinstance(response, list):
            if len(response) >= 2 and response[0] == 1:
                return str(response[1])
            else:
                logging.warning(f"Buy order for {item_name} might have failed. Response: {response}")
        else:
            logging.error(f"Unexpected response type from create_buy_order: {type(response)}")
        return None

    def unregister_buy_orders(self):
        for order_id in list(self.active_buy_orders.keys()):
            try:
                if self.config.enable_orders:
                    self.steam_client.cancel_buy_order(order_id)
                    logging.info(f"Cancelled buy order {order_id}")
                else:
                    logging.info(f"SIMULATION: Would have cancelled buy order {order_id}")
                del self.active_buy_orders[order_id]
            except Exception as e:
                logging.error(f"Failed to cancel buy order {order_id}: {e}")

    def list_item_on_market(self, item_id: str, item_data: Dict):
        price = self._calculate_listing_price(item_data)
        try:
            logging.info(f"Attempting to list {item_data['name']} on market for {price}")
            if self.config.enable_orders:
                self.steam_client.create_sell_order(item_id, str(int(price * 100)))
                logging.info(f"Listed {item_data['name']} on market for {price}")
            else:
                logging.info(f"SIMULATION: Would have listed {item_data['name']} on market for {price}")
        except Exception as e:
            logging.error(f"Failed to list {item_data['name']} on market: {e}")

    def _calculate_listing_price(self, item_data: Dict) -> Decimal:
        try:
            market_price = self.steam_client.fetch_price(item_data['name'])
            lowest_price = Decimal(market_price['lowest_price'].split('$')[1])
            return lowest_price - Decimal('0.01')
        except Exception as e:
            logging.error(f"Failed to calculate listing price for {item_data['name']}: {e}")
            return Decimal('0')
