from abc import ABC
from typing import Optional, Dict

from .model import Order


class AbstractOrderProcessor(ABC):
    def process_order(self, restaurant_id: int, order: Order):
        pass

