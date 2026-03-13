"""
WhatsApp notification via CallMeBot.
"""
import os
from datetime import date
from urllib.parse import quote

import requests

CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"


def send_summary(report_date: date, summary: dict) -> None:
    """
    Send the daily sales summary to WhatsApp via CallMeBot.

    summary keys:
        total_donations (float)
        total_tickets (int)
        donor_names (list[str])
        ticket_buyers (list[{name: str, tickets: int}])
        total_after_fees (float)
    """
    phone = os.environ["CALLMEBOT_PHONE"]
    api_key = os.environ["CALLMEBOT_API_KEY"]

    date_str = report_date.strftime("%b %-d, %Y")

    total_donations = summary.get("total_donations", 0.0)
    total_tickets = summary.get("total_tickets", 0)
    donor_names = summary.get("donor_names") or []
    ticket_buyers = summary.get("ticket_buyers") or []
    total_after_fees = summary.get("total_after_fees", 0.0)

    donor_names_str = ", ".join(donor_names) if donor_names else "None"
    ticket_buyers_str = (
        ", ".join(f"{b['name']}({b['tickets']})" for b in ticket_buyers)
        if ticket_buyers
        else "None"
    )

    message = (
        f"Daily Sales Report - {date_str}\n"
        f"Donations: ${total_donations:,.2f}\n"
        f"Tickets: {total_tickets}\n"
        f"Donor Names: {donor_names_str}\n"
        f"Ticket buyer Names: {ticket_buyers_str}\n"
        f"TRRP total after fees: ${total_after_fees:,.2f}"
    )

    params = {
        "phone": phone,
        "text": quote(message),
        "apikey": api_key,
    }

    response = requests.get(CALLMEBOT_URL, params=params, timeout=30)
    response.raise_for_status()


def send_error(report_date: date, error_message: str) -> None:
    """Send an error alert via WhatsApp."""
    phone = os.environ["CALLMEBOT_PHONE"]
    api_key = os.environ["CALLMEBOT_API_KEY"]

    date_str = report_date.strftime("%b %-d, %Y")
    message = f"TRRP Sales Report ERROR - {date_str}\n{error_message}"

    params = {
        "phone": phone,
        "text": quote(message),
        "apikey": api_key,
    }

    response = requests.get(CALLMEBOT_URL, params=params, timeout=30)
    response.raise_for_status()
