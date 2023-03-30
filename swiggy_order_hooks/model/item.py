from typing import List, Optional

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json

from .addon import Addon

@dataclass_json
@dataclass
class Item:
    item_id: Optional[str]
    quantity: Optional[int] = 0
    name: Optional[str] = None
    restaurant_discount_hit: Optional[float] = 0
    final_sub_total: Optional[float] = 0
    sub_total: Optional[float] = 0
    total: Optional[float] = 0
    category: Optional[str] = None
    sub_category: Optional[str] = None
    charges: Optional[dict] = field(default_factory=dict)
    addons: Optional[List[Addon]] = field(default_factory=list)
    variants: Optional[str] = None
    newAddons: Optional[List[Addon]] = field(default_factory=list)
    newVariants: Optional[List] = field(default_factory=list)
    is_oos: Optional[bool] = None 
    is_veg: Optional[str] = None
    reward_type: Optional[str] = None
    free_quantity: Optional[int] = 0
