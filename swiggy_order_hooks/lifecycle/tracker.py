import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from ..model import Order
from .event import OrderEventType, OrderLifecycleEvent

logger = logging.getLogger(__name__)


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            # Swiggy timestamps are IST (UTC+5:30)
            try:
                from zoneinfo import ZoneInfo
                dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            except ImportError:
                from datetime import timezone, timedelta
                dt = dt.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
        return dt
    except ValueError:
        return None


class OrderStateTracker:
    """
    Watches order snapshots across polls and emits OrderLifecycleEvents
    when meaningful state transitions occur.

    Call update() on every poll for every order in the response.
    It returns any new events detected since the last snapshot.

    Deduplication: each (order_id, event_type) is emitted at most once
    per process lifetime. If the process restarts, NEW_ORDER re-fires
    but past transition events don't — only future transitions will fire.
    """

    def __init__(self):
        # Last known snapshot keyed by (restaurant_id, order_id)
        self._snapshots: Dict[Tuple[int, str], Order] = {}
        # Events already emitted — prevents re-firing on duplicate polls
        self._emitted: Set[Tuple[str, str]] = set()

    def update(
        self,
        restaurant_id: int,
        order: Order,
        last_event_time: Optional[str] = None,
    ) -> List[OrderLifecycleEvent]:
        """
        Diff the incoming order snapshot against the previous one.
        Returns a list of new lifecycle events (may be empty, may be multiple).

        last_event_time: value from RestaurantData.lastOrderEventTimestamps[order_id]
                         — Swiggy's precise timestamp for the most recent change.
        """
        key = (restaurant_id, str(order.order_id))
        prev = self._snapshots.get(key)
        observed_at = datetime.now(timezone.utc)
        event_at = _parse_dt(last_event_time)

        candidates: List[OrderLifecycleEvent] = []

        def make(etype: OrderEventType, at: Optional[datetime] = None) -> OrderLifecycleEvent:
            return OrderLifecycleEvent(
                event_type=etype,
                restaurant_id=restaurant_id,
                order=order,
                previous_order=prev,
                event_at=at if at is not None else event_at,
                observed_at=observed_at,
            )

        s = order.status
        ps = prev.status if prev else None

        # ── NEW ORDER ────────────────────────────────────────────────────────
        if prev is None:
            candidates.append(make(OrderEventType.NEW_ORDER, _parse_dt(s.ordered_time if s else None)))

        # ── ORDER ACCEPTED (placed_status: unplaced → placed) ────────────────
        prev_placed = ps.placed_status if ps else None
        curr_placed = s.placed_status if s else None
        if prev_placed != "placed" and curr_placed == "placed":
            candidates.append(make(OrderEventType.ORDER_ACCEPTED, _parse_dt(s.placed_time if s else None)))

        # ── FOOD READY (MFR: vendorData.foodPreparedTime appears) ────────────
        prev_mfr = (prev.vendorData or {}).get("foodPreparedTime") if prev else None
        curr_mfr = (order.vendorData or {}).get("foodPreparedTime") if order.vendorData else None
        if not prev_mfr and curr_mfr:
            candidates.append(make(OrderEventType.FOOD_READY, _parse_dt(curr_mfr)))

        # ── DELIVERY STATUS transitions ───────────────────────────────────────
        prev_ds = ps.delivery_status if ps else None
        curr_ds = s.delivery_status if s else None
        if prev_ds != curr_ds:
            if curr_ds == "assigned":
                candidates.append(make(OrderEventType.DE_ASSIGNED))
            elif curr_ds == "pickedup":
                candidates.append(make(OrderEventType.PICKED_UP))
            elif curr_ds == "delivered":
                candidates.append(make(OrderEventType.DELIVERED))

        # ── CANCELLED ────────────────────────────────────────────────────────
        prev_cancelled = ps.cancelled_time if ps else None
        curr_cancelled = s.cancelled_time if s else None
        if not prev_cancelled and curr_cancelled:
            candidates.append(make(OrderEventType.CANCELLED, _parse_dt(curr_cancelled)))
        elif s and s.order_status == "cancelled" and (not ps or ps.order_status != "cancelled"):
            if not any(c.event_type == OrderEventType.CANCELLED for c in candidates):
                candidates.append(make(OrderEventType.CANCELLED))

        # ── Update snapshot ───────────────────────────────────────────────────
        self._snapshots[key] = order

        # ── Deduplicate ───────────────────────────────────────────────────────
        new_events: List[OrderLifecycleEvent] = []
        for e in candidates:
            ek = (str(order.order_id), e.event_type.value)
            if ek not in self._emitted:
                self._emitted.add(ek)
                new_events.append(e)
                logger.info(
                    "RID %s: lifecycle event [%s] for order #%s (event_at=%s)",
                    restaurant_id,
                    e.event_type.value,
                    str(order.order_id)[-6:],
                    e.event_at,
                )

        return new_events

    def is_active(self, restaurant_id: int, order: Order) -> bool:
        """True if order is still in-flight (not yet delivered or cancelled)."""
        s = order.status
        if not s:
            return False
        terminal = {"delivered", "cancelled"}
        return s.order_status not in terminal and not s.cancelled_time
