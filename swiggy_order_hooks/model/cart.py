from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
from typing import Optional, List

from .item import Item

@dataclass_json
@dataclass
class Cart:
    charges: Optional[dict] = field(default_factory=dict)
    items: Optional[List[Item]] = field(default_factory=list)