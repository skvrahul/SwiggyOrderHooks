import asyncio
import logging
import os
from datetime import timedelta
from logging.handlers import TimedRotatingFileHandler
from random import randint
from time import sleep

from google.oauth2 import service_account
from telegram import Bot

from swiggy_order_hooks import SwiggyOrderListener
from swiggy_order_hooks.lifecycle import parse_swiggy_dt
from swiggy_order_hooks.example import (
    TelegramOrderProcessor,
    TelegramCardProcessor,
    FirestoreOrderProcessor,
    FirestoreLifecycleProcessor,
    PickupSlaAlertProcessor,
    SlaWatchProcessor,
)
from throttled_retry import ThrottledRetry
from gspread_processor import GoogleSheetsOrderProcessor

parent_restaurant_ids = [384630]
csk_restaraunt_ids = [
        827861, 827862, 827863, 827864,920703
]
all_rids = parent_restaurant_ids + csk_restaraunt_ids
TOKEN = '5954494580:AAGCZmfxtttDmBxTmnWah89iL-2p_56sQo8'

# Telegram user ID (replace with your own ID)
RAHUL_USER_ID = 68173408
HYDRA_GROUP_ID = -291011790
SWIGGY_UPDATES_GRP_ID = -4144672359


# Configure logging (optional)
def logSetup():
    # Define the logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Create a handler that rotates the log file daily and appends the current date to the filename
    handler = TimedRotatingFileHandler(filename=f'./logs/swiggy_listener.log', when="midnight", interval=1, backupCount=30)

    # Set the logging level for the handler
    handler.setLevel(logging.DEBUG)

    # Create a formatter and set it for the handler
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(handler)

logSetup()

def _telegram_breach_alert(token, chat_id, label):
    """Returns an on_breach callable that sends a Telegram message."""
    bot = Bot(token=token)
    def on_breach(restaurant_id, order, elapsed):
        mins, secs = divmod(int(elapsed.total_seconds()), 60)
        order_id_short = str(order.order_id)[-6:]
        items_str = (
            ", ".join(f"{i.quantity}x {i.name}" for i in (order.cart.items or []))
            if order.cart else "?"
        )
        msg = (
            f"⏰ {label} — RID {restaurant_id}\n"
            f"Order #{order_id_short}: {items_str}\n"
            f"Waiting {mins}m {secs}s"
        )
        asyncio.get_event_loop().run_until_complete(
            bot.send_message(chat_id=chat_id, text=msg)
        )
    return on_breach

def run_listener():
    key_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '/root/swiggy_order_svc/custom_hooks/firebase-orderflow-svc.json')
    print(key_path)
    if os.path.exists(key_path):
        creds = service_account.Credentials.from_service_account_file(key_path)
    else:
        print("ERRRRRROR:  Couldn't create creds")

    l = SwiggyOrderListener(restaurant_ids=all_rids)
    l.login('9676453332', 'hailHydr4ForLyf')

    # ----
    l.add_hook(TelegramOrderProcessor(TOKEN, SWIGGY_UPDATES_GRP_ID))
    l.add_hook(TelegramCardProcessor(
        token=TOKEN,
        chat_id=SWIGGY_UPDATES_GRP_ID,
        mini_app_base_url="https://YOUR_HOST/flag.html",  # set after hosting mini_app/flag.html
    ))
    l.add_hook(FirestoreOrderProcessor('orderflow-lp3bq', creds))
    l.add_hook(FirestoreLifecycleProcessor('orderflow-lp3bq', creds))
    l.add_hook(PickupSlaAlertProcessor(TOKEN, SWIGGY_UPDATES_GRP_ID, threshold_minutes=4))

    # ── SLA: order not accepted within 2 min of being placed ─────────────────
    l.add_hook(SlaWatchProcessor(
        name="acceptance_delay",
        anchor_fn=lambda o: parse_swiggy_dt(o.status.ordered_time if o.status else None),
        waiting_fn=lambda o: bool(
            o.status
            and o.status.placed_status != "placed"
            and not o.status.cancelled_time
        ),
        threshold=timedelta(minutes=2),
        on_breach=_telegram_breach_alert(TOKEN, SWIGGY_UPDATES_GRP_ID, "⚠️ Order not accepted"),
    ))
    # ── SLA: food not marked ready within 2 min of acceptance ────────────────
    l.add_hook(SlaWatchProcessor(
        name="mfr_delay",
        anchor_fn=lambda o: parse_swiggy_dt(o.status.placed_time if o.status else None),
        waiting_fn=lambda o: bool(
            o.status
            and o.status.placed_status == "placed"
            and not (o.vendorData or {}).get("foodPreparedTime")
            and not o.status.cancelled_time
        ),
        threshold=timedelta(minutes=2),
        on_breach=_telegram_breach_alert(TOKEN, SWIGGY_UPDATES_GRP_ID, "🍳 Food not ready (MFR)"),
    ))

    l.poll()

def random_errors():
    while True:
        if randint(0, 10) >  8:
            raise Exception("WHOOOOPSIEEE")
        print("all okay bud...")
        sleep(1)


logger = logging.getLogger()

logger.debug("We are good to go!")
r = ThrottledRetry(retry_interval = 15, max_retries_per_minute=3)
r.run(run_listener)

