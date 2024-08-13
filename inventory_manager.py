import logging
from decimal import Decimal
from typing import Dict, List

from utils import transform_link


class InventoryManager:
    def __init__(self, steam_client, tradeup_api, market_operations):
        self.steam_client = steam_client
        self.tradeup_api = tradeup_api
        self.market_operations = market_operations

    def check_inventory(self, tradeup_links: List[str]):
        inventory = self.steam_client.get_my_inventory()
        all_tradeup_data = self._fetch_all_tradeup_data(tradeup_links)

        for item_id, item_data in inventory.items():
            if self._should_list_item(item_data, all_tradeup_data):
                self.market_operations.list_item_on_market(item_id, item_data)

    def _fetch_all_tradeup_data(self, tradeup_links: List[str]) -> List[Dict]:
        all_tradeup_data = []
        for tradeup_link in tradeup_links:
            api_link = transform_link(tradeup_link)
            tradeup_data = self.tradeup_api.fetch_tradeup_data(api_link)
            all_tradeup_data.append(tradeup_data)
        return all_tradeup_data

    def _should_list_item(self, item_data: Dict, all_tradeup_data: List[Dict]) -> bool:
        for tradeup_data in all_tradeup_data:
            for tradeup_item in tradeup_data['skinList']:
                if item_data['name'] == tradeup_item['name']:
                    if Decimal(item_data.get('float_value', '0')) > Decimal(str(tradeup_item.get('maxFloat', '1'))):
                        return True
        return False
