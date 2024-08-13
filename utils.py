import re
import urllib.parse
from typing import Dict


def parse_cookies(cookies_string: str) -> Dict[str, str]:
    login_cookies = {}
    cookies_string = cookies_string.strip()
    for cookie in cookies_string.split('; '):
        if '=' in cookie:
            name, value = cookie.split('=', 1)
            login_cookies[name.strip()] = value.strip()
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


def transform_link(tradeup_link: str) -> str:
    pattern = r'https://www\.tradeupspy\.com/calculator/share/([^/]+)/([^/]+)/([^/]+)/([^/]+)/([^/]+)/([^/]+)/([^/]+)/([^/]+)'
    match = re.match(pattern, tradeup_link)

    if not match:
        raise ValueError(f"Invalid tradeup link format: {tradeup_link}")

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
