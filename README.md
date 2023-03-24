# SwiggyOrderHooks

SwiggyOrderHooks allows anyone who manages a restaurant on Swiggy (the food aggregation app) to listen into order updates and run custom code/logic upon receiving an order.

## Install

```python
    pip install -r requirements.txt

    # Optionally install libs needed for running examples
    pip install -r requirements-examples.txt

    pip install .
```

## Quick Start

```python

import logging
from swiggy_order_hooks import SwiggyOrderListener, AbstractOrderProcessor


'''
    Simple OrderProcessor that just prints a new order to console
'''
class MyPrintingOrderProcessor(AbstractOrderProcessor):
    def process_order(self, restaurant_id: int, order: Order):
        # Edit this body's content to change the email sent out
        body = f"""
            Hi you have received a Swiggy order.
            Customer Name: {cname}
            Total Bill: Rs.{order.bill}
        """
        print(body)


# Configure logging (optional)
logging.basicConfig(level = logging.DEBUG, filename='swiggy_listener.log')

# Login with your credentials
rid = 12345 # replace with your RID
listener = SwiggyOrderListener(restaurant_id=rid)
listener.login('<MOBILE_NO/USERNAME>', '<PASSWORD>')

# Add the OrderProcessor we just created
listener.add_hook(MyPrintingOrderProcessor())

# Start Listening to orders!
l.poll() # poll swiggy with default wait time=30_000 (30s)

```
## Example OrderProcessors

You can leverage existing OrderProcessors under [`swiggy_order_hooks.example`](./swiggy_order_hooks/example)

1. **Email Order Processor**: Send an email whenever an order is received

2. **Rest DB Order Processor**: Add order to a simple REST based NoSQL Store [restdb.io](www.restdb.io) whenever order is received 


## Background

I own and manage a Beverage brand that is partnered with Swiggy for delivery.   
Subtle plug for [**Hydra**](https://www.hydrakombucha.com) if you wish to find out more!.   

As any owner would, I was interested in diving into data about orders to gather some insights and maybe answer some questions you have about customer's ordering patterns.    

While swiggy does have it's own (very minimal) dashboard for insights, they fail to actually provide any real insights into ordering history or patterns beyond just aggregating revenues and order counts in the last Day/Week/Month. Especially at a customer level.
Swiggy does allow you to export *some* order data over CSV. But the weird quirk is that there is a much richer (& imo very crucial) set of datapoints about your Customer that is available while an order is Active or Live(Order Placed up until Order delivered). This data for some reason stops being available the moment an order lifecycle ends.   

Over the course of a weekend I decided to hack together a quick solution that would let me hook into and capture some of this data while the order is active so I could store it in my own datastore and have full ownership of it without relying on Swiggy's opaque layer on top. This library is a result of that, with some refining to make it more usable by others.   

Gathering this data will hopefully allow me to answer questions like:

1. What are my top 3 most ordered items on Swiggy
2. How are my customers geographically distributed around my restaurant? Are there any hotsposts from where I get a larger chunk of my orders
3. What is the reorder pattern for customers?
4. What is the average time taken for restaurant staff to prepare an order? 
5. Customer LTV?    
 ... and so many more!
 

## Datapoints available
You have realtime access to order state and datapoints (previously unvailable via CSV Export) such as:
 - `Customer ID`
 - `Customer Lat/Long`
    - (this somewhat concerns me. IMO Swiggy should NOT be exposing this in their partner facing API. But as a restaurant owner, this allows me to gather some additional insights so I won't raise my voice for now :) )
 - **State Changes**:
    - `Order State`
    - `Delivery State`
 - Look in [`swiggy_order_hooks.model`](./swiggy_order_hooks/model) for the full data model that is available.
    


## :warning: Gotchas and Notes of Caution :warning: 
 - This is not an official API or client for Swiggy Restaurant Partner. Their API Contract and Data model may change anytime causing this to break. Since, I will be using this library myself too, I will try my best to keep it updated to minor API Changes.

 - This *might* be breaking their TOS.

 - I barely tested this, so use at your own risk. And ALL of that minimal testing was using a single **restaurant_id**, so I have no idea how the code holds up with a *multi-restaurant* login.

 - You could probably get all of this (AND more) by shelling out a yearly fee for a POS System that has official integrations with Swiggy(Ex: Petpooja). But they aren't Open Source and may not provide the freedom to access the raw data.


## TODO
 - [ ] Each 'OrderProcessor' is currently invoked synchronously. Should probably move that to an async model. 
 - [ ] Bake de-duplication of orders into the framework. Currently anytime an order is updated, the OrderProcessor is invoked and your custom OrderProcessor is responsible for handling duplicates.
    - See: [`swiggy_order_hooks.example.RestDBOrderProcessor`](./swiggy_order_hooks/example/restdb_processor.py) for a crude implementation
 - [ ] Add some tests
 - [ ] Add more concrete docs
