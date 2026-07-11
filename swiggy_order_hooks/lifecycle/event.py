from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from ..model import Order


class OrderEventType(Enum):
    NEW_ORDER        = "new_order"
    ORDER_ACCEPTED   = "order_accepted"   # restaurant accepted (placed_status -> placed)
    FOOD_READY       = "food_ready"       # vendorData.foodPreparedTime appeared (MFR)
    DE_ASSIGNED      = "de_assigned"      # delivery_status -> assigned
    DE_ARRIVED       = "de_arrived"       # arrived_time appeared (DE at restaurant)
    HANDOVER_DELAYED = "handover_delayed" # hand_over_delayed flipped True (Swiggy penalty window breached)
    PICKED_UP        = "picked_up"        # delivery_status -> pickedup
    DELIVERED        = "delivered"        # order_status -> delivered
    CANCELLED        = "cancelled"


@dataclass
class OrderLifecycleEvent:
    event_type:      OrderEventType
    restaurant_id:   int
    order:           Order           # current snapshot
    previous_order:  Optional[Order] # snapshot from previous poll; None for NEW_ORDER
    event_at:        Optional[datetime]  # Swiggy-side event time (from lastOrderEventTimestamps)
    observed_at:     datetime            # our wall-clock when we saw the change
