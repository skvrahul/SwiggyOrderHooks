from typing import List, Optional
from dataclasses import dataclass
from dataclasses_json import dataclass_json

from .order_status import OrderStatus
from .delivery_executive import DeliveryExecutive
from .restaurant_details import RestaurantDetails
from .cart import Cart
from .customer import Customer
from .prep_time import PrepTimeDetails

@dataclass_json
@dataclass
class Order:
    isBulkOrder: Optional[bool] = None
    last_updated_time: Optional[str] = None
    order_id: Optional[str] = None
    prep_time_predicted: Optional[int] = None
    status: Optional[OrderStatus] = None
    current_order_action: Optional[str] = None
    delivery_boy: Optional[DeliveryExecutive] = None
    customer_comment: Optional[str] = None
    customer_area: Optional[str] = None
    customer_distance: Optional[float] = None
    restaurant_details: Optional[RestaurantDetails] = None
    cart: Optional[Cart] = None
    restaurant_taxation_type: Optional[str] = None
    GST_details: Optional[dict] = dict
    vendorData: Optional[dict] = dict
    gst: Optional[float] = None
    serviceCharge: Optional[float] = None
    spending: Optional[float] = None
    tax: Optional[float] = None
    discount: Optional[float] = None
    bill: Optional[float] = None
    restaurant_trade_discount: Optional[float] = 0.0
    total_restaurant_discount: Optional[float] = None
    type: Optional[str] = None
    cafe_data: Optional[dict] = dict
    is_assured: Optional[bool] = False
    discount_descriptions: Optional[list] = list
    order_expiry_time: Optional[str] = None
    final_gp_price: Optional[float] = None
    customer: Optional[Customer] = None
    prep_time_details: Optional[PrepTimeDetails] = None
    isMFRAccurate: Optional[bool] = None
    isMFRAccuracyCalculated: Optional[bool] = None
    rest_extra_prep_time: Optional[float] = None 
    promise_prep_time: Optional[float] = None
    foodHandoverTimeSec: Optional[int] = 0