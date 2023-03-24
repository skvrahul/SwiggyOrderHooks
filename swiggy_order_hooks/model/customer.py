from dataclasses import dataclass
from dataclasses_json import dataclass_json
from typing import Optional

@dataclass_json
@dataclass
class Customer:
    customer_id: Optional[str] = None
    customer_lat: Optional[str] = None
    customer_lng: Optional[str] = None
    customer_name: Optional[str] = None