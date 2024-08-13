import time

import requests
import logging
from typing import Dict, List
from utils import get_tradeupspy_headers, transform_link


class TradeUpAPI:
    def __init__(self, config):
        self.verify_ssl = config.verify_ssl
        self.cache_expiry = config.cache_expiry
        self.tradeup_cache = {}

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

    @staticmethod
    def get_condition(float_value: float) -> str:
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
