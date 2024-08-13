class TradeUpAPIError(Exception):
    """Raised when there's an error with the TradeUp API"""
    pass


class SteamAPIError(Exception):
    """Raised when there's an error with the Steam API"""
    pass


class MarketOperationError(Exception):
    """Raised when there's an error with market operations"""
    pass


class ConfigurationError(Exception):
    """Raised when there's an error in the configuration"""
    pass
