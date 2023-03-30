from typing import Optional

from dataclasses_json import dataclass_json
from dataclasses import dataclass

@dataclass_json
@dataclass
class Addon:
        choice_id: Optional[str] = None
        group_id: Optional[str] = None
        name: Optional[str] = None
        price: Optional[float] = None