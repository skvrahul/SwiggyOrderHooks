import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Set

from telegram import Bot

from ..abstract_processor import AbstractOrderProcessor
from ..lifecycle.event import OrderLifecycleEvent
from ..model import Order

logger = logging.getLogger(__name__)


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            try:
                from zoneinfo import ZoneInfo
                dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            except ImportError:
                dt = dt.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
        return dt
    except ValueError:
        return None


class SlaWatchProcessor(AbstractOrderProcessor):
    """
    Generic SLA monitor.

    Fires on_breach() once per order when:
      - anchor_fn(order) returns a datetime  (the clock starts here)
      - waiting_fn(order) is still True      (the condition hasn't resolved)
      - time elapsed since anchor >= threshold

    Example — alert if DE not assigned within 5 min of acceptance:

        SlaWatchProcessor(
            name="assignment_delay",
            anchor_fn=lambda o: _parse_dt(o.status.placed_time if o.status else None),
            waiting_fn=lambda o: bool(o.status and o.status.delivery_status == "unassigned"),
            threshold=timedelta(minutes=5),
            on_breach=lambda rid, order, elapsed: print(f"Order {order.order_id} unassigned for {elapsed}"),
        )
    """

    def __init__(
        self,
        name: str,
        anchor_fn: Callable[[Order], Optional[datetime]],
        waiting_fn: Callable[[Order], bool],
        threshold: timedelta,
        on_breach: Callable[[int, Order, timedelta], None],
    ):
        self.name = name
        self._anchor_fn = anchor_fn
        self._waiting_fn = waiting_fn
        self._threshold = threshold
        self._on_breach = on_breach
        self._alerted: Set[str] = set()

    def check_order_sla(self, restaurant_id: int, order: Order):
        if not order.order_id or order.order_id in self._alerted:
            return
        if not self._waiting_fn(order):
            return
        anchor = self._anchor_fn(order)
        if not anchor:
            return
        elapsed = datetime.now(timezone.utc) - anchor
        if elapsed >= self._threshold:
            self._alerted.add(order.order_id)
            logger.warning(
                "RID %s: SLA breach [%s] on order #%s — elapsed %s",
                restaurant_id,
                self.name,
                str(order.order_id)[-6:],
                elapsed,
            )
            self._on_breach(restaurant_id, order, elapsed)


class PickupSlaAlertProcessor(SlaWatchProcessor):
    """
    Concrete SLA watch: alerts via Telegram when food has been sitting ready
    (vendorData.foodPreparedTime) for longer than `threshold_minutes` without
    being picked up by the DE.

    Also logs the actual MFR-to-pickup wait time when pickup does happen.
    """

    def __init__(self, token: str, chat_id: int, threshold_minutes: int = 4):
        self._bot = Bot(token=token)
        self._chat_id = chat_id
        super().__init__(
            name="pickup_after_mfr",
            anchor_fn=lambda o: _parse_dt((o.vendorData or {}).get("foodPreparedTime")),
            waiting_fn=lambda o: bool(
                o.status
                and o.status.delivery_status not in ("pickedup", "delivered")
                and not o.status.cancelled_time
                and o.status.order_status != "cancelled"
            ),
            threshold=timedelta(minutes=threshold_minutes),
            on_breach=self._send_telegram_alert,
        )

    def handle_picked_up(self, event: OrderLifecycleEvent):
        """Log actual MFR-to-pickup wait once the DE collects the order."""
        mfr_time = _parse_dt((event.order.vendorData or {}).get("foodPreparedTime"))
        if mfr_time and event.event_at:
            wait_sec = int((event.event_at - mfr_time).total_seconds())
            logger.info(
                "RID %s: order #%s picked up — food waited %ds after MFR",
                event.restaurant_id,
                str(event.order.order_id)[-6:],
                wait_sec,
            )

    def _send_telegram_alert(self, restaurant_id: int, order: Order, elapsed: timedelta):
        mins, secs = divmod(int(elapsed.total_seconds()), 60)
        order_id_short = str(order.order_id)[-6:]
        items_str = (
            ", ".join(f"{i.quantity}x {i.name}" for i in (order.cart.items or []))
            if order.cart else "?"
        )
        customer = order.customer.customer_name if order.customer else "?"
        ds = order.status.delivery_status if order.status else "?"

        message = (
            f"⚠️ Pickup delay — RID {restaurant_id}\n"
            f"Order #{order_id_short} for {customer}\n"
            f"{items_str}\n"
            f"Food ready {mins}m {secs}s ago — DE status: {ds}"
        )
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(
                self._bot.send_message(chat_id=self._chat_id, text=message)
            )
        except Exception as e:
            logger.error(
                "Failed to send Telegram SLA alert for order #%s: %s", order_id_short, e
            )
