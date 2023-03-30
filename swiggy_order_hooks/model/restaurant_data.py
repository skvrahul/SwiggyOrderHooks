from typing import Optional, List, Dict

from dataclasses import dataclass, field
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
    lastOrderEventTimestamps: Optional[Dict] = field(default_factory=dict) 
    isServiceable: Optional[bool] = None
    stressInfo: Optional[dict] = None
    updatedOrderIds: Optional[List[str]] = field(default_factory=list)
    popOrders: Optional[List[str]] = field(default_factory=list)
