from dataclasses import dataclass
from dataclasses_json import dataclass_json
from typing import Optional


@dataclass_json
@dataclass
class DeliveryExecutive:
    name: Optional[str] = None
    mobile: Optional[str] = None
    imageUrl: Optional[str] = None