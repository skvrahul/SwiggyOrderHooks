from typing import List, Optional
from dataclasses import dataclass
from dataclasses_json import dataclass_json

@dataclass_json
@dataclass
class RestaurantDetails:
    restaurant_lat: Optional[str] = None
    restaurant_lng: Optional[str] = None
    categories: Optional[List[str]] = list 