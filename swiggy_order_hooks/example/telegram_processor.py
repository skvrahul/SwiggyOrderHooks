# from .deduplicated_processer import DeduplicatedOrderProcessor
from swiggy_order_hooks.abstract_processor import AbstractOrderProcessor
from telegram import Bot
import asyncio

from swiggy_order_hooks.model.order import Order
from .deduplicated_processor import DeduplicatedOrderProcessor

class TelegramOrderProcessor(DeduplicatedOrderProcessor):

    def __init__(self, token, message_id):
        self._token = token
        self.message_id = message_id
        self.bot = Bot(token=token) 
        self.sent = set()
        super().__init__()

    async def _send_message(self, message):
        print("Trying to send message = ", message)
        await self.bot.send_message(chat_id=self.message_id, text=message)


    def process_unique_order(self, rid: int, order: Order):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._generate_and_send_message(rid, order))


    async def _generate_and_send_message(self, rid: int, order: Order):
        message_string = f"New order on RID({rid}) Order #{order.order_id[-4:]}\n"
        order_summary = order.cart.display_string()
        message_string += order_summary
        message_string += '\n'
        message_string += f"Order by : {order.customer.customer_name}"
        await self._send_message(message_string)

