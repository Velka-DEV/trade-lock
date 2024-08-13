import time
import logging
import signal
from config import Config
from steam_client import SteamClient
from tradeup_api import TradeUpAPI
from market_operations import MarketOperations
from inventory_manager import InventoryManager
from utils import transform_link


class SteamTradeBot:
    def __init__(self, config_path: str):
        self.config = Config(config_path)
        self.steam_client = SteamClient(self.config)
        self.tradeup_api = TradeUpAPI(self.config)
        self.market_operations = MarketOperations(self.steam_client, self.tradeup_api, self.config)
        self.inventory_manager = InventoryManager(self.steam_client, self.tradeup_api, self.market_operations)
        self.running = True

    def run(self):
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        try:
            self._place_initial_buy_orders()
            while self.running:
                self.inventory_manager.check_inventory(self.config.tradeup_links)
                # Sleep for the check interval (with incremental of 1 second)
                for _ in range(self.config.check_interval):
                    if not self.running:
                        break
                    time.sleep(1)
        finally:
            self.market_operations.unregister_buy_orders()

    def stop(self, signum, frame):
        logging.info("Stopping the bot...")
        self.running = False

    def _place_initial_buy_orders(self):
        for tradeup_link in self.config.tradeup_links:
            api_link = transform_link(tradeup_link)
            tradeup_data = self.tradeup_api.fetch_tradeup_data(api_link)
            self.market_operations.place_buy_orders(tradeup_data)

        if not self.config.enable_orders:
            logging.info("SIMULATION MODE: Buy orders were not actually placed.")
