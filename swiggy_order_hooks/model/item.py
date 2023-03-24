from typing import List, Optional

from dataclasses import dataclass
from dataclasses_json import dataclass_json


@dataclass
@dataclass_json
class Addon:
    choice_id: Optional[str] = None
    group_id: Optional[str] = None
    name: Optional[str] = None
    price: Optional[float] = 0

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
    charges: Optional[dict] = dict
    addons: Optional[List[Addon]] = list
    variants: Optional[str] = None
    newAddons: Optional[List[Addon]] = list
    newVariants: Optional[List] = list
    is_oos: Optional[bool] = None 
    is_veg: Optional[str] = None
    reward_type: Optional[str] = None
    free_quantity: Optional[int] = 0
