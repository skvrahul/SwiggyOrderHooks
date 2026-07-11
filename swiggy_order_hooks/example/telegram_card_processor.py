"""
TelegramCardProcessor — sends one live-updating Telegram message per order.

Each lifecycle event edits the same card in place rather than spamming new
messages. Optionally shows a "Flag delay" button that opens a mini app where
the user can copy a pre-formatted WhatsApp message with one tap.

Usage:
    l.add_hook(TelegramCardProcessor(
        token=TOKEN,
        chat_id=CHAT_ID,
        mini_app_base_url="https://your-host/flag.html",  # optional
    ))
"""

import asyncio
import logging
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.error import BadRequest

from ..abstract_processor import AbstractOrderProcessor
from ..lifecycle.event import OrderEventType, OrderLifecycleEvent
from ..model import Order

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    _IST = ZoneInfo("Asia/Kolkata")
except ImportError:
    _IST = timezone(timedelta(hours=5, minutes=30))

# Characters that must be backslash-escaped in Telegram MarkdownV2
_MD_SPECIAL = set('\\_*[]()~`>#+-=|{}.!')


def _esc(text) -> str:
    return ''.join(f'\\{c}' if c in _MD_SPECIAL else c for c in str(text))


def _fmt_time(dt: Optional[datetime]) -> str:
    if not dt:
        return "?"
    return dt.astimezone(_IST).strftime("%H:%M")


def _fmt_dur(secs: int) -> str:
    if secs < 60:
        return f"{secs}s"
    m, s = divmod(secs, 60)
    return f"{m}m {s}s" if s else f"{m}m"


def _dur_md(a: Optional[datetime], b: Optional[datetime]) -> str:
    """Returns an italic MarkdownV2 duration string, or empty string."""
    if not a or not b:
        return ""
    secs = max(0, int((b - a).total_seconds()))
    return f" _\\({_esc(_fmt_dur(secs))}\\)_"


# ── Card state ────────────────────────────────────────────────────────────────

@dataclass
class _CardState:
    order: Order
    restaurant_id: int
    message_id: int
    events: Dict[str, datetime] = field(default_factory=dict)
    de_name: Optional[str] = None
    de_phone: Optional[str] = None


# ── Processor ─────────────────────────────────────────────────────────────────

class TelegramCardProcessor(AbstractOrderProcessor):
    """One live-updating Telegram card per order, edited on each lifecycle event."""

    def __init__(self, token: str, chat_id: int, mini_app_base_url: Optional[str] = None):
        self._bot = Bot(token=token)
        self._chat_id = chat_id
        self._mini_app_base_url = mini_app_base_url.rstrip("/") if mini_app_base_url else None
        self._cards: Dict[str, _CardState] = {}

    # ── Main hook (overrides dispatcher) ─────────────────────────────────────

    def handle_lifecycle_event(self, event: OrderLifecycleEvent):
        order_id = str(event.order.order_id)

        if event.event_type == OrderEventType.NEW_ORDER:
            self._init_card(event)
            return

        state = self._cards.get(order_id)
        if not state:
            # Process restarted mid-order — bootstrap a card now
            self._init_card(event)
            state = self._cards.get(order_id)
            if not state:
                return

        # Merge new event into state
        state.events[event.event_type.value] = event.event_at or event.observed_at
        state.order = event.order
        self._sync_de(state, event.order)

        text, keyboard = self._render(order_id)
        self._edit(state.message_id, text, keyboard)

    # ── Card init ─────────────────────────────────────────────────────────────

    def _init_card(self, event: OrderLifecycleEvent):
        order_id = str(event.order.order_id)
        if order_id in self._cards:
            return  # already have a card for this order

        state = _CardState(
            order=event.order,
            restaurant_id=event.restaurant_id,
            message_id=0,
            events={event.event_type.value: event.event_at or event.observed_at},
        )
        self._sync_de(state, event.order)
        self._cards[order_id] = state

        text, keyboard = self._render(order_id)
        msg = self._send(text, keyboard)
        if msg:
            state.message_id = msg.message_id
        else:
            del self._cards[order_id]

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render(self, order_id: str):
        state = self._cards[order_id]
        order = state.order
        ev = state.events

        order_id_short = order_id[-6:]
        customer = order.customer.customer_name if order.customer else "Unknown"
        is_done = OrderEventType.DELIVERED.value in ev or OrderEventType.CANCELLED.value in ev

        # ── Header ────────────────────────────────────────────────────────────
        status_dot = "🟢" if is_done else "🟡"
        lines = [
            f"{status_dot} *Order \\#{_esc(order_id_short)}* — {_esc(customer)}",
            f"_RID {_esc(str(state.restaurant_id))}_",
            "",
        ]

        # ── Items ─────────────────────────────────────────────────────────────
        if order.cart and order.cart.items:
            for item in order.cart.items:
                lines.append(f"• {_esc(item.quantity)}x {_esc(item.name)}")
            lines.append("")

        # ── Timeline ──────────────────────────────────────────────────────────
        t = {k: ev[k] for k in ev}  # shorthand

        def _row(emoji, label, key, start_key=None, end_key=None):
            at = t.get(key)
            if at is None:
                return None
            dur = _dur_md(t.get(start_key), t.get(end_key)) if start_key else ""
            return f"{emoji} {_esc(label):<16} `{_esc(_fmt_time(at))}`{dur}"

        rows = [
            _row("✅", "Placed",      "new_order"),
            _row("✅", "Accepted",    "order_accepted",  "new_order",      "order_accepted"),
            _row("✅", "MFR",         "food_ready",      "order_accepted",  "food_ready"),
        ]

        # DE assigned row — include name
        de_at = t.get("de_assigned")
        if de_at:
            de_label = f"DE: {state.de_name}" if state.de_name else "DE Assigned"
            rows.append(f"🚴 {_esc(de_label):<16} `{_esc(_fmt_time(de_at))}`")

        rows += [
            _row("📍", "Arrived",     "de_arrived"),
            _row("📦", "Picked up",   "picked_up",       "de_arrived",      "picked_up"),
            _row("✅", "Delivered",   "delivered",       "new_order",       "delivered"),
            _row("❌", "Cancelled",   "cancelled"),
        ]

        if "handover_delayed" in t:
            rows.append("⚠️ _Handover delayed \\(Swiggy penalty\\)_")

        # Pending hint
        if not is_done:
            hint = self._next_hint(ev)
            if hint:
                rows.append(f"⏳ _{_esc(hint)}_")

        lines += [r for r in rows if r]

        text = "\n".join(lines)
        keyboard = self._build_keyboard(order_id, order, state)
        return text, keyboard

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def _build_keyboard(self, order_id: str, order: Order, state: _CardState):
        buttons = []

        if state.de_phone:
            buttons.append(InlineKeyboardButton("📞 Call DE", url=f"tel:{state.de_phone}"))

        if self._mini_app_base_url:
            buttons.append(InlineKeyboardButton(
                "⚠️ Flag delay",
                url=self._flag_url(order_id, order, state),
            ))

        return InlineKeyboardMarkup([buttons]) if buttons else None

    def _flag_url(self, order_id: str, order: Order, state: _CardState) -> str:
        items_str = ", ".join(
            f"{i.quantity}x {i.name}" for i in (order.cart.items or [])
        ) if order.cart else ""

        # Most recent event name as current stage
        ev = state.events
        stage = max(ev, key=lambda k: ev[k]) if ev else ""

        return self._mini_app_base_url + "?" + urllib.parse.urlencode({
            "oid":   order_id[-6:],
            "name":  order.customer.customer_name if order.customer else "",
            "items": items_str,
            "stage": stage.replace("_", " "),
            "de":    state.de_name or "",
            "de_ph": state.de_phone or "",
        })

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sync_de(self, state: _CardState, order: Order):
        de = order.delivery_boy
        if de:
            state.de_name  = de.name  or state.de_name
            state.de_phone = de.mobile or state.de_phone

    def _next_hint(self, ev: Dict) -> Optional[str]:
        stages = [
            ("order_accepted", "Waiting for acceptance…"),
            ("food_ready",     "Waiting for MFR…"),
            ("de_assigned",    "Waiting for DE assignment…"),
            ("de_arrived",     "DE en route…"),
            ("picked_up",      "Waiting for pickup…"),
            ("delivered",      "Out for delivery…"),
        ]
        for key, hint in stages:
            if key not in ev:
                return hint
        return None

    # ── Telegram I/O ──────────────────────────────────────────────────────────

    def _send(self, text: str, keyboard) -> Optional[Message]:
        try:
            return asyncio.get_event_loop().run_until_complete(
                self._bot.send_message(
                    chat_id=self._chat_id,
                    text=text,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
            )
        except Exception as e:
            logger.error("TelegramCard send failed: %s", e)
            return None

    def _edit(self, message_id: int, text: str, keyboard):
        try:
            asyncio.get_event_loop().run_until_complete(
                self._bot.edit_message_text(
                    chat_id=self._chat_id,
                    message_id=message_id,
                    text=text,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                logger.error("TelegramCard edit failed: %s", e)
        except Exception as e:
            logger.error("TelegramCard edit failed: %s", e)
