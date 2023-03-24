from dataclasses import dataclass
from dataclasses_json import dataclass_json
from typing import Optional, List

from .item import Item

@dataclass_json
@dataclass
class Cart:
    charges: Optional[dict] = dict
    items: Optional[List[Item]] = list