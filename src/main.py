"""
Orchestrator — runs the nightly Square → Sheets → Email pipeline.
"""
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import email_notifier
import sheets_client
import square_client

EASTERN = ZoneInfo("America/New_York")


def _is_repeat(name: str, guest_set: set[str]) -> str:
    """Return 'Repeat' if name is in guest_set (case-insensitive), else 'New'."""
    return "Repeat" if name.strip().lower() in guest_set else "New"


def main() -> None:
    today = datetime.now(tz=EASTERN).date()

    # 1. Fetch Square sales
    try:
        transactions, summary = square_client.get_daily_sales(today)
    except Exception as exc:
        error_msg = f"Square fetch failed: {exc}"
        print(f"ERROR: {error_msg}", file=sys.stderr)
        try:
            email_notifier.send_error(today, error_msg)
        except Exception as email_exc:
            print(f"Error email alert also failed: {email_exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetched {len(transactions)} transaction(s) from Square.")

    # 2. Load 2025 guest list for repeat detection
    try:
        guest_set = sheets_client.load_guest_list_2025()
        print(f"Loaded {len(guest_set)} names from GuestList-2025.")
    except Exception as exc:
        print(f"WARNING: Could not load GuestList-2025: {exc}", file=sys.stderr)
        guest_set = set()

    # 3. Tag each transaction as New or Repeat
    for t in transactions:
        t["new_or_repeat"] = _is_repeat(t["name"], guest_set)

    # 4. Append to SquareSales tab
    sheet_error = None
    try:
        sheets_client.append_to_square_sales(transactions)
        print("Appended rows to SquareSales tab.")
    except Exception as exc:
        sheet_error = str(exc)
        print(f"ERROR: Sheet update failed: {sheet_error}", file=sys.stderr)

    # 5. Send email summary
    if sheet_error:
        summary_note = f"\n(NOTE: Sheet update failed: {sheet_error})"
    else:
        summary_note = ""

    try:
        email_notifier.send_summary(today, summary)
        if summary_note:
            email_notifier.send_error(today, f"Sheet update failed: {sheet_error}")
        print("Email summary sent.")
    except Exception as exc:
        print(f"ERROR: Email notification failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if sheet_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
