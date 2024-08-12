import re
import time
import json
import logging
import signal
import warnings
from collections import defaultdict
from decimal import Decimal
from typing import List, Dict, Union
from steampy.client import SteamClient, Asset
from steampy.models import Currency
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

    if isinstance(cookies_string, bytes):
        cookies_string = cookies_string.decode('utf-8')

    cookies_string = cookies_string.strip()

    for cookie in cookies_string.split('; '):
        if '=' in cookie:
            parts = cookie.split('=')
            name = parts[0].strip()
            value = '='.join(parts[1:]).strip()
            login_cookies[name] = value

    return login_cookies

def get_tradeupspy_headers() -> Dict[str, str]:
    return {
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

def get_wear_condition(float_value: float) -> str:
    if float_value < 0.07:
        return "Factory New"
    elif float_value < 0.15:
        return "Minimal Wear"
    elif float_value < 0.38:
        return "Field-Tested"
    elif float_value < 0.45:
        return "Well-Worn"
    else:
        return "Battle-Scarred"

class SteamTradeBot:
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        login_cookies = parse_cookies(self.config['cookies_header'])

        self.steam_client = SteamClient(self.config['api_key'], username=self.config['username'],
                                        login_cookies=login_cookies)
        self.active_buy_orders = {}
        self.running = True
        self.item_nameid_cache = {}
        self.verify_ssl = self.config.get('verify_ssl', False)
        self.tradeup_cache = {}
        self.cache_expiry = self.config.get('cache_expiry', 3600)

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
        current_time = time.time()
        if api_link in self.tradeup_cache:
            cached_data, cache_time = self.tradeup_cache[api_link]
            if current_time - cache_time < self.cache_expiry:
                return cached_data

        try:
            response = requests.get(api_link, headers=get_tradeupspy_headers(), verify=self.verify_ssl)
            response.raise_for_status()
            tradeup_data = response.json()
            self.tradeup_cache[api_link] = (tradeup_data, current_time)
            return tradeup_data
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch tradeup data: {e}")
            return {}

    def get_interchangeable_items(self, item: Dict, is_stattrak: bool) -> List[Dict]:
        collection_id = item['collection']['idc']
        rarity = item['idr']
        condition = self.get_condition(item['fv'])

        url = f"https://api.tradeupspy.com/api/skins/search/1"
        params = {
            "stattrak": str(is_stattrak).lower(),
            "rarity": rarity,
            "condition": condition,
            "collection": collection_id,
            "skinname": "",
            "filter": 0
        }

        try:
            response = requests.get(url, params=params, headers=get_tradeupspy_headers(), verify=self.verify_ssl)
            response.raise_for_status()
            return response.json().get('skinList', [])
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch interchangeable items: {e}")
            return []

    def get_condition(self, float_value: float) -> str:
        if float_value < 0.07:
            return "fn"
        elif float_value < 0.15:
            return "mw"
        elif float_value < 0.38:
            return "ft"
        elif float_value < 0.45:
            return "ww"
        else:
            return "bs"

    def place_buy_orders(self, tradeup_data: Dict):
        is_stattrak = tradeup_data['statTrak']

        grouped_items = defaultdict(list)
        for item in tradeup_data['skinList']:
            collection = item['collection']['name']
            wear_condition = get_wear_condition(item['fv'])
            grouped_items[(collection, wear_condition)].append(item)

        for (collection, wear_condition), items in grouped_items.items():
            max_price = max(Decimal(str(item['price'])) for item in items)

            interchangeable_items = self.get_interchangeable_items(items[0], is_stattrak)

            highest_buy_order = Decimal('0')
            for interchangeable_item in interchangeable_items:
                current_buy_order = self.get_highest_buy_order(interchangeable_item['name'], wear_condition, is_stattrak)
                highest_buy_order = max(highest_buy_order, current_buy_order)

            if self.should_place_buy_order(highest_buy_order, max_price):
                price = highest_buy_order
                quantity = len(items)
                for interchangeable_item in interchangeable_items:
                    full_item_name = f"{'StatTrak™ ' if is_stattrak else ''}{interchangeable_item['name']} ({wear_condition})"
                    try:
                        logging.info(f"Attempting to place buy order for {quantity} {full_item_name} at {price} each")
                        response = self.steam_client.market.create_buy_order(
                            full_item_name,
                            str(int(price * 100)),
                            quantity,
                            GameOptions.CS,
                            Currency.EURO
                        )
                        logging.debug(f"Buy order response: {response}")

                        order_id = self.process_buy_order_response(response, full_item_name, quantity, price)
                        if order_id:
                            self.active_buy_orders[order_id] = {
                                'name': full_item_name,
                                'quantity': quantity,
                                'price': price
                            }
                            logging.info(f"Placed buy order {order_id} for {quantity} {full_item_name} at {price} each")
                    except Exception as e:
                        logging.error(f"Failed to place buy order for {full_item_name}: {e}")
                        logging.exception("Traceback:")

    def process_buy_order_response(self, response: Union[Dict, List], item_name: str, quantity: int, price: Decimal) -> Union[str, None]:
        if isinstance(response, dict):
            return response.get('buy_orderid')
        elif isinstance(response, list):
            # Assuming the first element contains the status and the second contains the order ID
            if len(response) >= 2 and response[0] == 1:
                return str(response[1])
            else:
                logging.warning(f"Buy order for {item_name} might have failed. Response: {response}")
        else:
            logging.error(f"Unexpected response type from create_buy_order: {type(response)}")
        return None

    def fetch_item_orders_histogram(self, item_name: str) -> Dict:
        item_nameid = self.get_item_nameid(item_name)
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

    def get_item_nameid(self, item_name: str) -> Union[str, None]:
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

    def get_highest_buy_order(self, item_name: str, wear: str, is_stattrak: bool = False) -> Decimal:
        full_item_name = f"{'StatTrak™ ' if is_stattrak else ''}{item_name} ({wear})"
        try:
            histogram_data = self.fetch_item_orders_histogram(full_item_name)
            if not histogram_data:
                return Decimal('0')

            highest_buy_order = histogram_data.get('highest_buy_order')
            if highest_buy_order:
                return Decimal(str(highest_buy_order)) / 100  # Convert cents to euros
            return Decimal('0')
        except Exception as e:
            logging.error(f"Failed to get highest buy order for {full_item_name}: {e}")
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

        all_tradeup_data = self.fetch_all_tradeup_data()

        for item_id, item_data in inventory.items():
            if self.should_list_item(item_data, all_tradeup_data):
                self.list_item_on_market(item_id, item_data)

    def fetch_all_tradeup_data(self) -> List[Dict]:
        all_tradeup_data = []
        for tradeup_link in self.config['tradeup_links']:
            api_link = transform_link(tradeup_link)
            tradeup_data = self.fetch_tradeup_data(api_link)
            all_tradeup_data.append(tradeup_data)
        return all_tradeup_data

    def should_list_item(self, item_data: Dict, all_tradeup_data: List[Dict]) -> bool:
        for tradeup_data in all_tradeup_data:
            for tradeup_item in tradeup_data['skinList']:
                if item_data['name'] == tradeup_item['name']:
                    if Decimal(item_data.get('float_value', '0')) > Decimal(str(tradeup_item.get('maxFloat', '1'))):
                        return True
        return False

    def list_item_on_market(self, item_id: str, item_data: Dict):
        price = self.calculate_listing_price(item_data)
        try:
            logging.info(f"Listing {item_data['name']} on market for {price}")
            # Uncomment the following line when ready to actually list items
            # self.steam_client.market.create_sell_order(item_id, GameOptions.CS, str(int(price * 100)))
            logging.info(f"Listed {item_data['name']} on market for {price}")
        except Exception as e:
            logging.error(f"Failed to list {item_data['name']} on market: {e}")

    def calculate_listing_price(self, item_data: Dict) -> Decimal:
        try:
            market_price = self.steam_client.market.fetch_price(item_data['name'], GameOptions.CS, country="EN")
            lowest_price = Decimal(market_price['lowest_price'].split('$')[1])
            return lowest_price - Decimal('0.01')
        except Exception as e:
            logging.error(f"Failed to calculate listing price for {item_data['name']}: {e}")
            return Decimal('0')

if __name__ == "__main__":
    bot = SteamTradeBot('config.json')
    bot.run()