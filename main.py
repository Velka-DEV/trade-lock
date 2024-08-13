import logging
from steam_trade_bot import SteamTradeBot

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def main():
    bot = SteamTradeBot('config.json')
    bot.run()


if __name__ == "__main__":
    main()
