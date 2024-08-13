import json
from typing import Dict, List


class Config:
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self._config = json.load(f)

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    @property
    def api_key(self) -> str:
        return self._config['api_key']

    @property
    def username(self) -> str:
        return self._config['username']

    @property
    def cookies_header(self) -> str:
        return self._config['cookies_header']

    @property
    def tradeup_links(self) -> List[str]:
        return self._config['tradeup_links']

    @property
    def check_interval(self) -> int:
        return self._config.get('check_interval', 300)

    @property
    def verify_ssl(self) -> bool:
        return self._config.get('verify_ssl', True)

    @property
    def cache_expiry(self) -> int:
        return self._config.get('cache_expiry', 3600)

    @property
    def enable_orders(self) -> bool:
        return self._config.get('enable_orders', False)
