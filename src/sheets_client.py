"""
Google Sheets client — reads GuestList-2025, appends rows to SquareSales.
"""
import json
import os

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

SQUARE_SALES_HEADERS = [
    "Name",
    "Phone Number",
    "Email",
    "Donation or Ticket",
    "Number of Tickets",
    "Amount Paid",
    "Amount after fees",
    "New or Repeat",
    "Date",
]


def _open_spreadsheet() -> gspread.Spreadsheet:
    service_account_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    spreadsheet_id = os.environ["GOOGLE_SPREADSHEET_ID"]

    info = json.loads(service_account_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(spreadsheet_id)


def load_guest_list_2025() -> set[str]:
    """Return a set of lowercased, stripped names from the GuestList-2025 tab."""
    sheet = _open_spreadsheet()
    worksheet = sheet.worksheet("GuestList-2025")
    all_values = worksheet.get_all_values()

    names: set[str] = set()
    for row in all_values:
        for cell in row:
            normalized = cell.strip().lower()
            if normalized:
                names.add(normalized)
    return names


def append_to_square_sales(transactions: list[dict]) -> None:
    """
    Append transaction rows to the SquareSales tab.
    Each transaction dict must contain the 'new_or_repeat' key (set by main.py).
    """
    if not transactions:
        return

    sheet = _open_spreadsheet()
    worksheet = sheet.worksheet("SquareSales")

    rows = []
    for t in transactions:
        rows.append(
            [
                t.get("name", ""),
                t.get("phone", ""),
                t.get("email", ""),
                t.get("type", ""),
                t.get("num_tickets", 0) if t.get("type") == "Ticket" else "",
                t.get("amount_paid", 0.0),
                t.get("amount_after_fees", 0.0),
                t.get("new_or_repeat", ""),
                t.get("date", ""),
            ]
        )

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")
