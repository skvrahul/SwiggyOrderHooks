from ..abstract_processor import AbstractOrderProcessor
from typing import Optional, Dict
from ..model import Order

class DeduplicatedOrderProcessor(AbstractOrderProcessor):
    def __init__(self):
        self._order_set = set()
    def is_duplicate(self, rid: int, order: Order):
        is_in = (rid, order.order_id) in self._order_set
        return is_in

    def order_processed(self, rid: int, order: Order):
        # In theory, just order.order_id should be just enough,
        # but why risk it!
        self._order_set.add((rid, order.order_id))

    def process_order(self, restaurant_id: int, order: Order):
        if not self.is_duplicate(restaurant_id, order):
            self.process_unique_order(restaurant_id, order)
            self.order_processed(restaurant_id, order)
        #TODO: Add logging


    # Hook if wish to process a unique order update
    def process_unique_order(self, rid: int, order: Order):
        pass