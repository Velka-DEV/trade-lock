import re
import time
import json
import logging
import signal
import warnings
from decimal import Decimal
from typing import List, Dict
from steampy.client import SteamClient, Asset
from steampy.utils import GameOptions
from steampy.exceptions import TooManyRequests
import requests
import urllib.parse

warnings.filterwarnings('ignore', message='Unverified HTTPS request')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def transform_link(tradeup_link: str) -> str:
    pattern = r'https://www\.tradeupspy\.com/calculator/share/([^/]+)/([^/]+)/([^/]+)/([^/]+)/([^/]+)/([^/]+)/([^/]+)/([^/]+)'
    match = re.match(pattern, tradeup_link)

    if not match:
        logging.error(f"Invalid tradeup link format: {tradeup_link}")
        return ""

    name, st, ir, input_float_values, input_ids, output_ids, input_prices, output_prices = match.groups()

    api_link = (f"https://api.tradeupspy.com/api/calculator/share?"
                f"name={urllib.parse.quote(name)}&"
                f"st={st}&"
                f"ir={ir}&"
                f"inputFloatValues={input_float_values}&"
                f"inputIds={input_ids}&"
                f"outputIds={output_ids}&"
                f"inputPrices={input_prices}&"
                f"outputPrices={output_prices}")

    return api_link


def parse_cookies(cookies_string):
    login_cookies = {}

    # Convert to string if it's bytes
    if isinstance(cookies_string, bytes):
        cookies_string = cookies_string.decode('utf-8')

    # Remove leading/trailing whitespace
    cookies_string = cookies_string.strip()

    for cookie in cookies_string.split('; '):
        if '=' in cookie:
            parts = cookie.split('=')
            name = parts[0].strip()
            value = '='.join(parts[1:]).strip()  # Join the rest with '=' in case the value contains '='
            login_cookies[name] = value

    return login_cookies


class SteamTradeBot:
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        login_cookies = parse_cookies(self.config['cookies_header'])

        self.steam_client = SteamClient(self.config['api_key'], username=self.config['username'],
                                        login_cookies=login_cookies)
        self.active_buy_orders = {}
        self.running = True
        self.verify_ssl = self.config.get('verify_ssl', False)

        if not self.verify_ssl:
            logging.warning("SSL certificate verification is disabled. This is not recommended for production use.")

    def run(self):
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        try:
            self.place_initial_buy_orders()
            while self.running:
                self.check_inventory()
                time.sleep(self.config['check_interval'])
        finally:
            self.unregister_buy_orders()

    def stop(self, signum, frame):
        logging.info("Stopping the bot...")
        self.running = False

    def place_initial_buy_orders(self):
        for tradeup_link in self.config['tradeup_links']:
            api_link = transform_link(tradeup_link)
            tradeup_data = self.fetch_tradeup_data(api_link)
            self.place_buy_orders(tradeup_data)

    def fetch_tradeup_data(self, api_link: str) -> Dict:
        headers = {
            'Host': 'api.tradeupspy.com',
            'Connection': 'keep-alive',
            'Accept': 'application/json, text/plain, */*',
            'DNT': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
            'Origin': 'https://www.tradeupspy.com',
            'Referer': 'https://www.tradeupspy.com/',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-GB,en;q=0.9'
        }

        try:
            response = requests.get(api_link, headers=headers, verify=self.verify_ssl)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch tradeup data: {e}")
            return {}

    def place_buy_orders(self, tradeup_data: Dict):
        for item in tradeup_data['skinList']:
            collection = item['collection']['name']
            rarity = item['rarity']
            is_stattrak = tradeup_data['statTrak']
            max_price = Decimal(str(item['price']))

            interchangeable_items = self.get_interchangeable_items(tradeup_data, collection, rarity, is_stattrak)

            for interchangeable_item in interchangeable_items:
                current_highest_buy_order = self.get_highest_buy_order(interchangeable_item)

                if self.should_place_buy_order(current_highest_buy_order, max_price):
                    price = current_highest_buy_order  # Place at the same price as the highest buy order
                    try:
                        logging.info(f"Placing buy order for {interchangeable_item} at {price}")
                        continue

                        response = self.steam_client.market.create_buy_order(interchangeable_item,
                                                                             str(int(price * 100)), 10, GameOptions.CS)
                        order_id = response.get('buy_orderid')
                        if order_id:
                            self.active_buy_orders[order_id] = interchangeable_item
                            logging.info(f"Placed buy order {order_id} for {interchangeable_item} at {price}")
                    except Exception as e:
                        logging.error(f"Failed to place buy order for {interchangeable_item}: {e}")

    def get_interchangeable_items(self, tradeup_data: Dict, collection: str, rarity: str, is_stattrak: bool) -> List[
        str]:
        interchangeable_items = []
        for item in tradeup_data['skinList']:
            if (item['collection']['name'] == collection and
                    item['rarity'] == rarity and
                    tradeup_data['statTrak'] == is_stattrak):
                interchangeable_items.append(item['name'])
        return interchangeable_items

    def get_highest_buy_order(self, item_name: str) -> Decimal:
        try:
            item_page = self.steam_client.market.fetch_price(item_name, GameOptions.CS)
            buy_orders = item_page.get('buy_order_graph', [])
            if buy_orders:
                return Decimal(str(buy_orders[0][0]))  # Highest buy order price
            return Decimal('0')
        except Exception as e:
            logging.error(f"Failed to get highest buy order for {item_name}: {e}")
            return Decimal('0')

    def should_place_buy_order(self, current_highest_buy_order: Decimal, max_price: Decimal) -> bool:
        return current_highest_buy_order < max_price

    def unregister_buy_orders(self):
        for order_id in list(self.active_buy_orders.keys()):
            try:
                self.steam_client.market.cancel_buy_order(order_id)
                logging.info(f"Cancelled buy order {order_id}")
                del self.active_buy_orders[order_id]
            except Exception as e:
                logging.error(f"Failed to cancel buy order {order_id}: {e}")

    def check_inventory(self):
        inventory = self.steam_client.get_my_inventory(GameOptions.CS)

        for item_id, item_data in inventory.items():
            if self.should_list_item(item_data):
                self.list_item_on_market(item_id, item_data)

    def should_list_item(self, item_data: Dict) -> bool:
        for tradeup_link in self.config['tradeup_links']:
            api_link = transform_link(tradeup_link)
            tradeup_data = self.fetch_tradeup_data(api_link)
            for tradeup_item in tradeup_data['skinList']:
                if item_data['name'] == tradeup_item['name']:
                    if Decimal(item_data.get('float_value', '0')) > Decimal(str(tradeup_item.get('maxFloat', '1'))):
                        return True
        return False

    def list_item_on_market(self, item_id: str, item_data: Dict):
        price = self.calculate_listing_price(item_data)
        try:
            logging.info(f"Listing {item_data['name']} on market for {price}")
            return
            self.steam_client.market.create_sell_order(item_id, GameOptions.CS, str(int(price * 100)))
            logging.info(f"Listed {item_data['name']} on market for {price}")
        except Exception as e:
            logging.error(f"Failed to list {item_data['name']} on market: {e}")

    def calculate_listing_price(self, item_data: Dict) -> Decimal:
        try:
            market_price = self.steam_client.market.fetch_price(item_data['name'], GameOptions.CS)
            lowest_price = Decimal(market_price['lowest_price'].split('$')[1])
            return lowest_price - Decimal('0.01')
        except Exception as e:
            logging.error(f"Failed to calculate listing price for {item_data['name']}: {e}")
            return Decimal('0')


if __name__ == "__main__":
    bot = SteamTradeBot('config.json')
    bot.run()
