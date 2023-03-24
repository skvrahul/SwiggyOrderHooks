import os
from sendgrid import SendGridAPIClient, Mail

from swiggy_order_hooks.model import Order
from swiggy_order_hooks import AbstractOrderProcessor


class EmailOrderProcessor(AbstractOrderProcessor):
    def __init__(self):
        # Initialize Email Client
        key = os.environ.get('SENDGRID_API_KEY')
        self.sg = SendGridAPIClient(key)

    
    def send_email(self, rid: int,  order: Order):
        # Set up email message

        # Edit the FROM and TO addresses
        from_email = 'from@domain.com' 
        to_emails = ['to@otherdomain.com']
        subject = f"Swiggy Order #{order.order_id} (Rs.{order.bill})" 
        cname = order.customer.customer_name

        # Edit this body's content to change the email sent out
        body = f"""
            Hi you have received a Swiggy order.
            Customer Name: {cname}
            Total Bill: Rs.{order.bill}
        """
        message = Mail(
            from_email=from_email,
            to_emails=to_emails,
            subject=subject, 
            plain_text_content=body
        )
        response = self.sg.send(message)
        print(response.status_code)
        print(response.body)
        print(response.headers)

    def process_order(self, restaurant_id: int, order: Order):
        self.send_email(restaurant_id, order)


