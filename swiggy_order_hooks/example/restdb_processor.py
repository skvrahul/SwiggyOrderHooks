import requests
from dataclasses import asdict

from swiggy_order_hooks.model import Order, Item
from swiggy_order_hooks import AbstractOrderProcessor


'''
    Takes an order and pushes it to a Simple REST Based NoSQL DB
    (in this case restdb.io)
'''
class RestDBOrderProcessor(AbstractOrderProcessor):
    def insert_record(self, collection_id, data: dict):
        url = f"https://{self.db_name}.restdb.io/rest/{collection_id}"

        headers = {
            "Content-Type": "application/json",
            "x-apikey": self.api_key,
            "cache-control": "no-cache"
        }

        print(f"Adding object: {data} to <{collection_id}>")
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 201:
            print("Object added successfully!")
            return True
        else:
            print("Error:", response.text)
            return False

    def get_records(self, collection_id, fields=[]):
        url = f"https://{self.db_name}.restdb.io/rest/{collection_id}"
        if fields:
            fields_str = ','.join(fields)
            url += '?metafields=false&fields={fields_str}&h={"$orderby":{"order_time": -1}}'

        headers = {
            "Content-Type": "application/json",
            "x-apikey": self.api_key,
            "cache-control": "no-cache"
        }

        print(f"Getting objects from <{collection_id}>")
        response = requests.get(url, headers=headers)
        print(response.status_code)
        if response.ok:
            return response.json()
        else:
            print("Error:", response.text)
            return None



    # TODO: Implement when we want to seperate items to its own schema
    def _insert_item(self, item: Item):
        raise NotImplementedError("item schema is not yet implemented")
        # item_obj = {
        #     'item_id': item.item_id,
        #     'item_name': item.name
        # }
        # if not self.insert_record('products', item_obj):
        #     raise RuntimeError("Unable to insert item into RestDB")
        # else:
        #     # update our cache table with this item
        #     self.item_cache[item.item_id] = item_obj

    def _insert_order(self, order: Order, restaurant_id):
        # Construct customer object
        customer_obj = {}
        if(order.customer):
            customer_obj['customer_id'] = order.customer.customer_id
            customer_obj['customer_lat'] = order.customer.customer_lat
            customer_obj['customer_lng'] = order.customer.customer_lng
            customer_obj['customer_name'] = order.customer.customer_name

            customer_obj['customer_area'] = order.customer_area
            customer_obj['customer_distance'] = order.customer_distance

        # Construct Order Object
        order_obj = {
            "restaurant_id": restaurant_id,
            "order_id": order.order_id,
            "customer": customer_obj,
            "items" : [],
            "raw_order_data": asdict(order),
            "order_time": order.status.ordered_time
        }

        # Add Items
        items = order.cart.items
        if items is None:
            items = []
        for i in items:
            item_obj = {
                'item_name': i.name,
                'item_id': i.item_id,
                'item_addons': [asdict(adn) for adn in i.addons],
                'item_price': i.total,
                'item_quantity': i.quantity
            }
            order_obj['items'].append(item_obj)
        if self.insert_record('orders', order_obj):
            self.orders_cache[order.order_id] = order_obj 

    def _init_item_cache(self):
        items = self.get_records('products')
        for i in items:
            self.item_cache[i['item_id']] = i

    def _init_order_cache(self):
        orders = self.get_records('orders', fields=['order_id'])
        for i in orders:
            self.orders_cache[i['order_id']] = i


    def _init_customer_cache(self):
        pass

    def __init__(self, api_key, db_name):
        self.api_key: str = api_key
        self.db_name: str = db_name
        self.item_cache = dict()
        self.orders_cache = dict()
        self.customer_cache = dict()

        self._init_order_cache()

    def process_order(self, restaurant_id: int, order: Order):
        if order.order_id in self.orders_cache:
            print(f"Order #{order.order_id} has already been processed. Skipping...")
            return False
        self._insert_order(order, restaurant_id=restaurant_id)