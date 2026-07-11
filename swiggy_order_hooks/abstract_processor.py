from abc import ABC

from .model import Order
from .lifecycle.event import OrderLifecycleEvent


class AbstractOrderProcessor(ABC):

    def process_order(self, restaurant_id: int, order: Order):
        """Legacy hook — called every poll for every order update. Kept for backward compat."""
        pass

    # ── Lifecycle hooks ───────────────────────────────────────────────────────
    # Override any of these to react to a specific transition.
    # Each fires at most once per (order_id, event_type) per process lifetime.

    def handle_lifecycle_event(self, event: OrderLifecycleEvent):
        """Dispatches to the specific handle_* method below. Override for custom routing."""
        handler = getattr(self, f"handle_{event.event_type.value}", None)
        if handler:
            handler(event)

    def handle_new_order(self, event: OrderLifecycleEvent): pass
    def handle_order_accepted(self, event: OrderLifecycleEvent): pass
    def handle_food_ready(self, event: OrderLifecycleEvent): pass
    def handle_de_assigned(self, event: OrderLifecycleEvent): pass
    def handle_picked_up(self, event: OrderLifecycleEvent): pass
    def handle_delivered(self, event: OrderLifecycleEvent): pass
    def handle_cancelled(self, event: OrderLifecycleEvent): pass

    # ── SLA check ─────────────────────────────────────────────────────────────
    # Called every poll for every active (in-flight) order.
    # Use this for time-based alerts that don't rely on a state transition.

    def check_order_sla(self, restaurant_id: int, order: Order):
        pass
