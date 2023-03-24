from typing import Optional

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase


@dataclass_json
@dataclass
class OrderStatus:
    order_status: Optional[str] = None
    placed_status: Optional[str] = None
    placing_state: Optional[str] = field(metadata=config(letter_case=LetterCase.CAMEL), default=None)
    delivery_status: Optional[str] = None
    placed_time: Optional[str] = None
    call_partner_time: Optional[str] = None
    ordered_time: Optional[str] = None
    edited_status: Optional[str] = None
    edited_time: Optional[str] = None
    food_prep_time: Optional[int] = None
    cancelled_time: Optional[str] = None
    order_handover_window: Optional[int] = None
    early_mfr_time: Optional[int] = None
