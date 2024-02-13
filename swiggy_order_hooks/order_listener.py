import logging
import requests

from typing import List
from time import sleep
from datetime import datetime
import dacite
from dacite import DaciteError

from .model.restaurant_data import RestaurantData

from .abstract_processor import AbstractOrderProcessor

SWIGGY_BASE_URL = 'https://partner.swiggy.com'
LOGIN_URL = f"{SWIGGY_BASE_URL}/login" 
ORDERS_URL = f"{SWIGGY_BASE_URL}/orders/v1/fetch" 
POLLING_TIME_MS = 30000


 
class SwiggyOrderListener:
    def get_orders(self, restaurant_ids: List[int], lastUpdatedTime=None):
        headers = {
            'authority': 'partner.swiggy.com',
            'method': 'POST',
            'path': '/orders/v1/fetch',
            'scheme': 'https',
            'accept': 'application/json, text/plain, */*',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'en-US,en-IN;q=0.9,en;q=0.8',
            'origin': 'https://partner.swiggy.com',
            'referer': 'https://partner.swiggy.com/orders',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'Content-Type': 'application/json;charset=UTF-8'
        }
        data = {
            "sourceMessageIdMap": {
                "source": "POLLING_SERVICE"
            },
            "restaurantTimeMap": []
        }
        for rid in restaurant_ids:
            data["restaurantTimeMap"].append(
                {
                    "rest_rid": rid
                }
            )
        if(lastUpdatedTime):
            data['restaurantTimeMap'][0]['lastUpdatedTime']=lastUpdatedTime
        self.logger.info(f"Hitting Order Endpoint: {ORDERS_URL}")
        response = self.session.post(ORDERS_URL, headers=headers, json=data)
        if response.ok:
            self.logger.info(f"RESPONSE OK")
            response_json = response.json()
            self.logger.debug(f"JSON Response: {response_json}")
            return response_json
        else:
            self.logger.error(f"RESPONSE NOT OK: STATUS {response.status_code} {response.reason}")
            response.reason

    def _init_session(self):
        self.logged_in = False
        self.session = requests.Session()
        # TODO: Stuff session with cookies / user-agent here to be more robust

    def login(self, username, password):
        login_body = {
            "username": username,
            "password": password,
            "accept_tnc": True
        }
        if self.session is None:
            self.logger.error("requests.Session not initialized...")
            raise RuntimeError("requests.Session not initialized...")

        resp = self.session.post("https://partner.swiggy.com/authentication/v1/login", json=login_body)
        if resp.ok: 
            resp_json = resp.json()
            self.logger.debug(f"Received resp when trying to login: {resp_json}")
            if 'statusMessage' in resp_json and 'Successful' in resp_json['statusMessage']:
                self.logged_in = True
                return True
        raise RuntimeError("Unable to login")

    def poll(self,  polltime_ms=None):

        if not self.logged_in:
            self.logger.error("Cannot call poll() before calling login()")
            raise RuntimeError("poll() invoked before login()")

        clientTime=None
        if polltime_ms is None:
            polltime_ms = POLLING_TIME_MS

        while True:
            self.logger.info("calling get_orders()")
            resp = self.get_orders(self.restaurant_ids, lastUpdatedTime=clientTime)
            if resp is None:
                self.logger.info('Whoops! something must have gone wrong while fetching orders')
            else:
                self.logger.info("Received a non-null response")
                for rest_data_dict in resp['restaurantData']:
                    try:
                        restaurant_data = dacite.from_dict(data_class=RestaurantData, data=rest_data_dict)
                    except DaciteError as e:
                        self.logger.error(f"Unable to parse Restaurant Data: {rest_data_dict}. Skipping...")
                        continue

                    rid_prefix = f"RID {restaurant_data.restaurantId}:"
                    self.logger.debug(f"{rid_prefix} {restaurant_data}")
                    orders = restaurant_data.orders
                    if orders:
                        self.logger.info(f"{rid_prefix} Received {len(orders)} order updates")
                        self.logger.debug(f"{rid_prefix} Orders = {orders}")

                        # Call each hook sequentially on the received orders.
                        # TODO: Make this async? 
                        for o in orders:
                            for processor in self.order_processor_hooks:
                                self.logger.info(f"{rid_prefix} Processing {processor}")
                                try:
                                    processor.process_order(restaurant_data.restaurantId, o)
                                except Exception as e:
                                    self.logger.error(f"{rid_prefix} Encountered exception: {e} while processing {processor}")
                                self.logger.info(f"{rid_prefix} Done processing {processor}")
                    else:
                        self.logger.info("{rid_prefix} No orders yet!")
                    clientTime = restaurant_data.serverTime

            # nap for a bit...
            polltime = polltime_ms // 1000
            self.logger.info(f"Sleeping for {polltime} S")
            sleep(polltime)

    def add_hook(self, order_processor: AbstractOrderProcessor):
        if(order_processor not in self.order_processor_hooks):
            self.order_processor_hooks.append(order_processor)

    def __init__(self, restaurant_ids: List[int] = []):
        self.order_processor_hooks: List[AbstractOrderProcessor] = []
        self.logger = logging.getLogger("OrderListener")
        self.session = None
        self.logged_in = False
        self._init_session()
        if not restaurant_ids:
            # Try to get all available rids for this login
            pass
        else:
            self.restaurant_ids = restaurant_ids
