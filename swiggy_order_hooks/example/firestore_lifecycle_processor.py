import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from google.cloud import firestore
from google.oauth2 import service_account

from ..abstract_processor import AbstractOrderProcessor
from ..lifecycle.event import OrderEventType, OrderLifecycleEvent

logger = logging.getLogger(__name__)


class FirestoreLifecycleProcessor(AbstractOrderProcessor):
    """
    Writes order lifecycle events into Firestore as they are detected,
    merging into the existing order doc under a `lifecycle` sub-map.

    Add this alongside FirestoreOrderProcessor — it does not replace it.
    FirestoreOrderProcessor handles the initial order write; this processor
    handles all subsequent lifecycle updates.

    Firestore shape written to orders/{order_id}:

        lifecycle:
            current_stage:   "picked_up"
            last_updated_at: <timestamp>
            events:
                new_order:       { at: <timestamp>, observed_at: <timestamp> }
                order_accepted:  { at: <timestamp>, observed_at: <timestamp> }
                food_ready:      { at: <timestamp>, observed_at: <timestamp> }
                de_assigned:     { at: <timestamp>, observed_at: <timestamp> }
                de_arrived:      { at: <timestamp>, observed_at: <timestamp> }
                handover_delayed:{ at: <timestamp>, observed_at: <timestamp> }
                picked_up:       { at: <timestamp>, observed_at: <timestamp> }
                delivered:       { at: <timestamp>, observed_at: <timestamp> }
            durations_sec:
                order_to_accepted:  25
                accepted_to_mfr:    7
                mfr_to_pickup:      643
                handover_wait:      88      # de_arrived -> picked_up
                order_to_delivered: 1305

    Accepts credentials as either a file path string or a credentials object
    (matching how FirestoreOrderProcessor is called in practice).
    """

    # Ordered pairs used to compute durations once both ends are known.
    _DURATION_PAIRS = [
        ("order_to_accepted",  "new_order",       "order_accepted"),
        ("accepted_to_mfr",    "order_accepted",  "food_ready"),
        ("mfr_to_pickup",      "food_ready",      "picked_up"),
        ("handover_wait",      "de_arrived",      "picked_up"),
        ("order_to_delivered", "new_order",       "delivered"),
    ]

    def __init__(self, project_id: str, credentials=None):
        if isinstance(credentials, str):
            creds = service_account.Credentials.from_service_account_file(credentials)
            self.db = firestore.Client(project=project_id, credentials=creds)
        elif credentials is not None:
            self.db = firestore.Client(project=project_id, credentials=credentials)
        else:
            self.db = firestore.Client(project=project_id)

        # In-memory event time cache for duration computation.
        # Keyed by order_id → {event_type_value → datetime}
        self._event_times: Dict[str, Dict[str, datetime]] = {}

    # ── Lifecycle hook ────────────────────────────────────────────────────────

    def handle_lifecycle_event(self, event: OrderLifecycleEvent):
        order_id = str(event.order.order_id)
        event_key = event.event_type.value
        event_at = event.event_at or event.observed_at

        # Update in-memory cache so duration computation has all timestamps
        if order_id not in self._event_times:
            self._event_times[order_id] = {}
        self._event_times[order_id][event_key] = event_at

        # Build the Firestore update using dot-notation field paths so we
        # only touch the specific nested fields without overwriting siblings.
        update: Dict[str, Any] = {
            f"lifecycle.events.{event_key}": {
                "at": event_at,
                "observed_at": event.observed_at,
            },
            "lifecycle.current_stage": event_key,
            "lifecycle.last_updated_at": datetime.now(timezone.utc),
        }

        # Append any durations that can now be computed
        for dur_key, dur_val in self._compute_durations(order_id).items():
            update[f"lifecycle.durations_sec.{dur_key}"] = dur_val

        try:
            self.db.collection("orders").document(order_id).update(update)
            logger.info(
                "lifecycle → Firestore [%s] order #%s",
                event_key,
                order_id[-6:],
            )
        except Exception as e:
            logger.error(
                "lifecycle → Firestore FAILED [%s] order #%s: %s",
                event_key,
                order_id[-6:],
                e,
                exc_info=True,
            )

    # ── Duration computation ──────────────────────────────────────────────────

    def _compute_durations(self, order_id: str) -> Dict[str, int]:
        times = self._event_times.get(order_id, {})
        durations: Dict[str, int] = {}
        for dur_key, start_key, end_key in self._DURATION_PAIRS:
            start = times.get(start_key)
            end = times.get(end_key)
            if start and end:
                durations[dur_key] = max(0, int((end - start).total_seconds()))
        return durations
