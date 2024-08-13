from steampy.client import SteamClient as BaseSteamClient
from steampy.models import GameOptions, Currency
from typing import Dict
from utils import parse_cookies


class SteamClient(BaseSteamClient):
    def __init__(self, config):
        login_cookies = parse_cookies(config.cookies_header)
        super().__init__(config.api_key, username=config.username, login_cookies=login_cookies)
        self.verify_ssl = config.verify_ssl

    def create_buy_order(self, item_name: str, price_cents: str, quantity: int) -> Dict:
        return super().market.create_buy_order(
            item_name,
            price_cents,
            quantity,
            GameOptions.CS,
            Currency.EURO
        )

    def cancel_buy_order(self, order_id: str) -> Dict:
        return super().market.cancel_buy_order(order_id)

    def get_my_inventory(self, **kwargs):
        return super().get_my_inventory(GameOptions.CS)

    def create_sell_order(self, item_id: str, price_cents: str) -> Dict:
        return super().market.create_sell_order(item_id, GameOptions.CS, price_cents)

    def fetch_price(self, item_name: str) -> Dict:
        return super().market.fetch_price(item_name, GameOptions.CS, country="EN")
