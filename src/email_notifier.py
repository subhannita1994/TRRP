"""
Email notification via Gmail SMTP + App Password.
"""
import os
import smtplib
from datetime import date
from email.mime.text import MIMEText

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _send(subject: str, body: str) -> None:
    gmail_address = os.environ["GMAIL_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = gmail_address

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(gmail_address, app_password)
        smtp.sendmail(gmail_address, gmail_address, msg.as_string())


def send_summary(report_date: date, summary: dict) -> None:
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

    body = (
        f"Daily Sales Report - {date_str}\n"
        f"Donations: ${total_donations:,.2f}\n"
        f"Tickets: {total_tickets}\n"
        f"Donor Names: {donor_names_str}\n"
        f"Ticket buyer Names: {ticket_buyers_str}\n"
        f"TRRP total after fees: ${total_after_fees:,.2f}"
    )

    _send(subject=f"TRRP Daily Sales Report - {date_str}", body=body)


def send_error(report_date: date, error_message: str) -> None:
    date_str = report_date.strftime("%b %-d, %Y")
    _send(
        subject=f"TRRP Sales Report ERROR - {date_str}",
        body=f"TRRP Sales Report ERROR - {date_str}\n{error_message}",
    )
