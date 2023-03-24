from typing import Optional, List, Dict

from dataclasses import dataclass
from dataclasses_json import dataclass_json

from .order import Order

@dataclass_json
@dataclass
class RestaurantData:
    restaurantId: int
    orders: List[Order]
    lastUpdatedTime: Optional[str] = None
    serverTime: Optional[str] = None
    isOpen: Optional[bool] = None
    lastCachePollTime: Optional[int] = None
    batches: Optional[Dict] = dict
    lastOrderEventTimestamps: Optional[Dict] = dict 
    isServiceable: Optional[bool] = None
    stressInfo: Optional[dict] = None
    updatedOrderIds: Optional[List[str]] = list
    popOrders: Optional[List[str]] = list
