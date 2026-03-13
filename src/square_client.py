"""
Square API client — fetches daily orders and extracts transaction details.
"""
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

from square.client import Client


EASTERN = ZoneInfo("America/New_York")


def _build_client() -> Client:
    return Client(
        access_token=os.environ["SQUARE_ACCESS_TOKEN"],
        environment="production",
    )


def _cents_to_dollars(cents: int | None) -> float:
    if cents is None:
        return 0.0
    return round(cents / 100, 2)


def _get_processing_fee(payment: dict) -> float:
    total_fee = 0
    for fee in payment.get("processing_fee") or []:
        amount = fee.get("amount_money", {}).get("amount") or 0
        total_fee += amount
    return _cents_to_dollars(total_fee)


def _get_customer(client: Client, customer_id: str) -> dict:
    result = client.customers.retrieve_customer(customer_id=customer_id)
    if result.is_success():
        return result.body.get("customer", {})
    return {}


def _classify_order(order: dict) -> str:
    """
    Return 'Donation' or 'Ticket' by matching line item names against
    SQUARE_DONATION_ITEM_NAME and SQUARE_TICKET_ITEM_NAME (case-insensitive
    substring match). Falls back to built-in keywords if env vars are unset.
    """
    donation_keyword = os.environ.get("SQUARE_DONATION_ITEM_NAME", "donation").lower()
    ticket_keyword = os.environ.get("SQUARE_TICKET_ITEM_NAME", "ticket").lower()

    for item in order.get("line_items") or []:
        item_name = item.get("name", "").lower()
        if donation_keyword and donation_keyword in item_name:
            return "Donation"
        if ticket_keyword and ticket_keyword in item_name:
            return "Ticket"

    # If no line items matched, default to Ticket
    return "Ticket"


def _ticket_count(order: dict) -> int:
    ticket_keyword = os.environ.get("SQUARE_TICKET_ITEM_NAME", "ticket").lower()
    total = 0
    for item in order.get("line_items") or []:
        if ticket_keyword in item.get("name", "").lower():
            try:
                total += int(float(item.get("quantity", "0")))
            except ValueError:
                pass
    return total


def get_daily_sales(date: datetime.date, full_day: bool = False) -> tuple[list[dict], dict]:
    """
    Fetch all completed orders for `date` (Eastern time).

    Returns:
        transactions: list of dicts with keys:
            name, phone, email, type, num_tickets,
            amount_paid, amount_after_fees, date
        summary: dict with keys:
            total_donations, total_tickets, donor_names,
            ticket_buyers (list of {name, tickets}), total_after_fees
    """
    client = _build_client()
    location_id = os.environ["SQUARE_LOCATION_ID"]

    start_dt = datetime.combine(date, time.min).replace(tzinfo=EASTERN)
    # For past dates (backfill), fetch the full day; for today, stop at 10 PM
    end_time = time(23, 59, 59) if full_day else time(22, 0)
    end_dt = datetime.combine(date, end_time).replace(tzinfo=EASTERN)

    start_at = start_dt.isoformat()
    end_at = end_dt.isoformat()

    body = {
        "location_ids": [location_id],
        "query": {
            "filter": {
                "state_filter": {"states": ["OPEN", "COMPLETED"]},
                "date_time_filter": {
                    "created_at": {
                        "start_at": start_at,
                        "end_at": end_at,
                    }
                },
            }
        },
        "return_entries": False,
    }

    orders = []
    cursor = None
    while True:
        if cursor:
            body["cursor"] = cursor
        result = client.orders.search_orders(body=body)
        if result.is_error():
            raise RuntimeError(f"Square SearchOrders error: {result.errors}")
        body_resp = result.body
        orders.extend(body_resp.get("orders") or [])
        cursor = body_resp.get("cursor")
        if not cursor:
            break

    transactions = []
    for order in orders:
        tenders = order.get("tenders") or []
        if not tenders:
            # No payment captured — abandoned/incomplete order; skip it
            continue

        order_type = _classify_order(order)
        amount_paid = _cents_to_dollars(
            (order.get("total_money") or {}).get("amount")
        )

        # Fetch payment(s) for processing fee and buyer info
        processing_fee = 0.0
        first_payment: dict = {}
        for tender in tenders:
            payment_id = tender.get("payment_id")
            if payment_id:
                pay_result = client.payments.get_payment(payment_id=payment_id)
                if pay_result.is_success():
                    payment = pay_result.body.get("payment", {})
                    processing_fee += _get_processing_fee(payment)
                    if not first_payment:
                        first_payment = payment

        amount_after_fees = round(amount_paid - processing_fee, 2)

        # Buyer info — try billing_address first, then customer profile, then fulfillments
        billing = first_payment.get("billing_address") or {}
        first_name = billing.get("first_name", "")
        last_name = billing.get("last_name", "")
        name = f"{first_name} {last_name}".strip()
        email = first_payment.get("buyer_email_address", "")
        phone = ""

        if not name:
            customer_id = first_payment.get("customer_id")
            if customer_id:
                customer = _get_customer(client, customer_id)
                given = customer.get("given_name", "")
                family = customer.get("family_name", "")
                name = f"{given} {family}".strip()
                email = email or customer.get("email_address", "")
                phone = customer.get("phone_number", "")

        if not name:
            for fulfillment in order.get("fulfillments") or []:
                recipient = (fulfillment.get("shipment_details") or {}).get("recipient") or {}
                name = recipient.get("display_name", "")
                email = email or recipient.get("email_address", "")
                phone = phone or recipient.get("phone_number", "")
                if name:
                    break

        if not name:
            print(f"[NAMELESS] order_id={order.get('id')} tenders={[t.get('type') for t in tenders]} amount={amount_paid}")

        num_tickets = _ticket_count(order) if order_type == "Ticket" else 0

        created_at_str = order.get("created_at", "")
        try:
            created_dt = datetime.fromisoformat(
                created_at_str.replace("Z", "+00:00")
            ).astimezone(EASTERN)
            order_date = created_dt.date().isoformat()
        except Exception:
            order_date = date.isoformat()

        transactions.append(
            {
                "name": name,
                "phone": phone,
                "email": email,
                "type": order_type,
                "num_tickets": num_tickets,
                "amount_paid": amount_paid,
                "amount_after_fees": amount_after_fees,
                "date": order_date,
            }
        )

    # Build summary
    donations = [t for t in transactions if t["type"] == "Donation"]
    tickets = [t for t in transactions if t["type"] == "Ticket"]

    summary = {
        "total_donations": round(sum(t["amount_paid"] for t in donations), 2),
        "total_tickets": sum(t["num_tickets"] for t in tickets),
        "donor_names": [t["name"] for t in donations if t["name"]],
        "ticket_buyers": [
            {"name": t["name"], "tickets": t["num_tickets"]}
            for t in tickets
            if t["name"]
        ],
        "total_after_fees": round(
            sum(t["amount_after_fees"] for t in transactions), 2
        ),
    }

    return transactions, summary
