from dataclasses import dataclass
from dataclasses_json import dataclass_json
from typing import Optional

@dataclass_json
@dataclass
class PrepTimeDetails:
    predicted_prep_time: Optional[float] = 0.0
    max_increase_threshold: Optional[int] = 0
    max_decrease_threshold: Optional[int] = 0