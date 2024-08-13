from dataclasses import dataclass
from decimal import Decimal


@dataclass
class BuyOrder:
    def __init__(self):
        pass

    id: str
    name: str
    quantity: int
    price: Decimal


@dataclass
class TradeUpItem:
    def __init__(self):
        pass

    name: str
    collection: str
    rarity: int
    float_value: float
    price: Decimal
    max_float: float


@dataclass
class InventoryItem:
    def __init__(self):
        pass

    id: str
    name: str
    float_value: float
    price: Decimal
