import json
import logging
import uuid

import requests
import dacite
from dacite import DaciteError
from typing import List
from time import sleep

from .model.restaurant_data import RestaurantData
from .abstract_processor import AbstractOrderProcessor

PARTNER_ORIGIN = "https://partner.swiggy.com"
# New auth: GraphQL login (vhc-composer) and orders (rms) — see RCA in repo.
VHC_LOGIN_URL = "https://vhc-composer.swiggy.com/query?mutation=loginMutation"
ORDERS_URL = "https://rms.swiggy.com/orders/v1/fetchOrders"
POLLING_TIME_MS = 30000

LOGIN_MUTATION_QUERY = """
  mutation loginMutation($input: LoginRequest!) {
    login(input: $input) {
      ID mobile rid name city access_token change_password userType userRole
      permissions restaurants { rest_id rest_name city_name enabled }
      user_restaurant_permissions
    }
  }
"""


 
class SwiggyOrderListener:
    def get_orders(self, restaurant_ids: List[int], lastUpdatedTime=None):
        data = {
            "restaurantTimeMap": [
                {"restaurantId": rid, "lastUpdatedTime": lastUpdatedTime}
                for rid in restaurant_ids
            ],
            "sourceMessageIdMap": {"source": "POLLING_SERVICE"},
        }
        headers = {
            "accept": "application/json, text/plain, */*",
            "accesstoken": self._access_token,
            "content-type": "application/json",
            "referer": f"{PARTNER_ORIGIN}/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        self.logger.info("Hitting Order Endpoint: %s", ORDERS_URL)
        response = self.session.post(ORDERS_URL, headers=headers, json=data)
        if response.ok:
            self.logger.info("RESPONSE OK")
            return response.json()
        self.logger.error("RESPONSE NOT OK: STATUS %s %s", response.status_code, response.reason)
        return None

    def _init_session(self):
        self.logged_in = False
        self._access_token = None
        self.session = requests.Session()

    def login(self, username, password):
        if self.session is None:
            raise RuntimeError("requests.Session not initialized...")
        graphql_body = {
            "operationName": "loginMutation",
            "query": LOGIN_MUTATION_QUERY,
            "variables": {
                "input": {
                    "username": username,
                    "password": password,
                    "accept_tnc": True,
                    "existing_user": True,
                    "include_dineout": True,
                    "is_otp_login": False,
                    "source": "VMS",
                }
            },
        }
        headers = {
            "Accept": "application/graphql-response+json, application/json",
            "Content-Type": "application/json",
            "access_token": str(uuid.uuid4()),
            "Origin": PARTNER_ORIGIN,
            "Referer": f"{PARTNER_ORIGIN}/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        resp = self.session.post(VHC_LOGIN_URL, json=graphql_body, headers=headers)
        if not resp.ok:
            self.logger.error("Login failed: HTTP %s", resp.status_code)
            raise RuntimeError("Unable to login")
        try:
            data = resp.json()
        except json.JSONDecodeError:
            self.logger.error("Login response is not JSON")
            raise RuntimeError("Unable to login")
        login_data = (data.get("data") or {}).get("login")
        if not login_data or not login_data.get("access_token"):
            self.logger.error("Login rejected or no access_token in response")
            raise RuntimeError("Unable to login")
        self._access_token = login_data["access_token"]
        self.logged_in = True
        return True

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
                        self.logger.info(f"{rid_prefix} No orders yet!")
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
