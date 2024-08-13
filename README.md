# TradeLock

![Logo](https://github.com/Velka-DEV/trade-lock/blob/main/resources/logo.png?raw=true)

![License](https://img.shields.io/github/license/Velka-DEV/trade-lock)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![Steam Market Bot](https://img.shields.io/badge/Steam-Market%20Bot-000000?style=flat&logo=steam&logoColor=white)](https://steamcommunity.com/market/)
![CS2](https://img.shields.io/badge/Game-CS2-%23ff9b01?logo=counterstrike&link=https%3A%2F%2Fwww.counter-strike.net%2Fcs2)

TradeLock is an open-source project that creates a [CS2](https://www.counter-strike.net/cs2) [Steam market](https://steamcommunity.com/market/) bot. It automates the process of placing buy orders and managing inventory based on trade-up calculations from [tradeupspy.com](https://www.tradeupspy.com/). The bot analyzes trade-up opportunities, places strategic buy orders for items with specific float values, and optimizes inventory by identifying items for resale. This automation allows traders to capitalize on market opportunities efficiently, streamlining the CS2 item trading process.

## Features

- Place buy orders based on tradeupspy.com sharing links
- Automatically check for new items in the inventory
- List items with unfavorable float values for resale
- Simulate trades without placing actual orders (configurable)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/tradelock.git
   cd tradelock
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Copy `config.example.json` to `config.json` and fill in your details:
   ```
   cp config.example.json config.json
   ```

## Configuration

Edit `config.json` with your Steam credentials and preferences:

```json
{
    "api_key": "YOUR_STEAM_API_KEY",
    "username": "YOUR_STEAM_USERNAME",
    "password": "YOUR_STEAM_PASSWORD",
    "cookies_header": "YOUR_STEAM_COOKIES",
    "check_interval": 300,
    "tradeup_links": [
        "https://www.tradeupspy.com/calculator/share/..."
    ],
    "cache_expiry": 3600,
    "enable_orders": false
}
```

Set `enable_orders` to `true` to place actual orders, or keep it `false` for simulation mode.

## Usage

Run the bot with:

```
python main.py
```

The bot will start placing buy orders based on the provided trade-up links and periodically check your inventory for new items to list.

## Project Structure

```
├── config.example.json
├── config.py
├── exceptions.py
├── inventory_manager.py
├── main.py
├── market_operations.py
├── models.py
├── steam_client.py
├── steam_trade_bot.py
├── tradeup_api.py
└── utils.py
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This project is for educational purposes only. Use at your own risk. The developers are not responsible for any losses incurred through the use of this bot.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.