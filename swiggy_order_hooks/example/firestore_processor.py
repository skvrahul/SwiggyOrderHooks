import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from google.cloud import firestore
from google.oauth2 import service_account

from swiggy_order_hooks.model import Order, Item
from swiggy_order_hooks import AbstractOrderProcessor

logger = logging.getLogger(__name__)


def _to_ts(dt) -> Optional[datetime]:
    """Parse a string or convert a naive datetime to UTC-aware for Firestore."""
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class FirestoreOrderProcessor(AbstractOrderProcessor):
    """
    Firestore-backed equivalent of RestDBOrderProcessor.

    Collections:
      - orders (doc id = order_id as string)
      - products (optional; doc id = item_id if present)

    Auth:
      - Pass credentials_path, or set GOOGLE_APPLICATION_CREDENTIALS to a service account JSON path.
    """

    def __init__(self, project_id: str, creds=None):
        assert creds is not None, "creds must be a google.oauth2 credentials object"
        logger.info(
            "Loaded service account credentials: client_email=%s project_id=%s",
            creds.service_account_email,
            creds.project_id,
        )
        self.db = firestore.Client(project=project_id, credentials=creds)

        self.item_cache: Dict[str, Dict[str, Any]] = {}
        self.orders_cache: Dict[str, Dict[str, Any]] = {}
        self.customer_cache: Dict[str, Dict[str, Any]] = {}

        self._init_order_cache()

    def insert_record(self, collection_id: str, data: dict) -> bool:
        try:
            doc_id = None
            if collection_id == "orders" and "order_id" in data:
                doc_id = str(data["order_id"])
            elif collection_id == "products" and "item_id" in data:
                doc_id = str(data["item_id"])

            data = self._normalize_for_firestore(collection_id, data)

            col_ref = self.db.collection(collection_id)
            if doc_id:
                col_ref.document(doc_id).set(data, merge=True)
            else:
                col_ref.add(data)

            print(f"[Firestore] Added object to <{collection_id}> (doc_id={doc_id})")
            return True
        except Exception as e:
            print("[Firestore] Error inserting:", e)
            return False

    def get_records(self, collection_id: str, fields: List[str] = []) -> Optional[List[Dict[str, Any]]]:
        try:
            query = self.db.collection(collection_id)

            if fields:
                query = query.select(fields)

            if collection_id == "orders":
                query = query.order_by("order_time", direction=firestore.Query.DESCENDING)

            out: List[Dict[str, Any]] = []
            for doc in query.stream():
                row = doc.to_dict() or {}
                row["__id"] = doc.id
                out.append(row)
            return out
        except Exception as e:
            print("[Firestore] Error getting records:", e)
            return None

    def _insert_item(self, item: Item):
        raise NotImplementedError("item schema is not yet implemented")

    def _insert_order(self, order: Order, restaurant_id: int):
        customer_obj: Dict[str, Any] = {}
        if order.customer:
            customer_obj["customer_id"] = order.customer.customer_id
            customer_obj["customer_lat"] = order.customer.customer_lat
            customer_obj["customer_lng"] = order.customer.customer_lng
            customer_obj["customer_name"] = order.customer.customer_name
            customer_obj["customer_area"] = order.customer_area
            customer_obj["customer_distance"] = order.customer_distance

        order_obj: Dict[str, Any] = {
            "restaurant_id": restaurant_id,
            "order_id": order.order_id,
            "customer": customer_obj,
            "items": [],
            "raw_order_data": asdict(order),
            "order_time": _to_ts(order.status.ordered_time),
            "_imported_from": "swiggy_hooks",
            "_imported_at": datetime.now(timezone.utc),
        }

        items = order.cart.items or []
        for item in items:
            order_obj["items"].append({
                "item_name": item.name,
                "item_id": item.item_id,
                "item_addons": [asdict(addon) for addon in (item.addons or [])],
                "item_price": item.total,
                "item_quantity": item.quantity,
            })

        if self.insert_record("orders", order_obj):
            self.orders_cache[str(order.order_id)] = order_obj

    def _init_item_cache(self):
        items = self.get_records("products") or []
        for item in items:
            item_id = item.get("item_id") or item.get("__id")
            if item_id:
                self.item_cache[str(item_id)] = item

    def _init_order_cache(self):
        orders = self.get_records("orders", fields=["order_id"]) or []
        for order in orders:
            if "order_id" in order:
                self.orders_cache[str(order["order_id"])] = order

    def _init_customer_cache(self):
        pass

    def process_order(self, restaurant_id: int, order: Order):
        key = str(order.order_id)
        if key in self.orders_cache:
            print(f"Order #{key} has already been processed. Skipping...")
            return False
        self._insert_order(order, restaurant_id=restaurant_id)
        return True

    def _normalize_for_firestore(self, collection_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(data)
        if collection_id == "orders":
            order_time = out.get("order_time")
            if isinstance(order_time, datetime):
                out["order_time"] = _to_ts(order_time)
        return out
