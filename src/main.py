"""
Orchestrator — runs the nightly Square → Sheets → Email pipeline.

Usage:
  python src/main.py                          # today (nightly cron mode)
  python src/main.py --date 2026-03-01        # single past date
  python src/main.py --from 2026-01-01 --to 2026-03-12  # backfill range
"""
import argparse
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import email_notifier
import sheets_client
import square_client

EASTERN = ZoneInfo("America/New_York")


def _is_repeat(name: str, guest_set: set[str]) -> str:
    """Return 'Repeat' if name is in guest_set (case-insensitive), else 'New'."""
    return "Repeat" if name.strip().lower() in guest_set else "New"


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Single date to run for (YYYY-MM-DD)")
    parser.add_argument("--from", dest="from_date", help="Backfill start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", help="Backfill end date (YYYY-MM-DD)")
    return parser.parse_args()


def _date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def run_for_date(target_date: date, guest_set: set[str], full_day: bool) -> tuple[list[dict], dict]:
    """Fetch Square sales for target_date, tag New/Repeat, append to Sheets. Returns (transactions, summary)."""
    transactions, summary = square_client.get_daily_sales(target_date, full_day=full_day)
    print(f"  {target_date}: {len(transactions)} transaction(s)")

    for t in transactions:
        t["new_or_repeat"] = _is_repeat(t["name"], guest_set)

    sheets_client.append_to_square_sales(transactions)
    return transactions, summary


def main() -> None:
    args = _parse_args()

    # Determine mode: backfill range, single date, or today
    if args.from_date and args.to_date:
        start = date.fromisoformat(args.from_date)
        end = date.fromisoformat(args.to_date)
        dates = list(_date_range(start, end))
        backfill = True
    elif args.date:
        dates = [date.fromisoformat(args.date)]
        backfill = True
    else:
        dates = [datetime.now(tz=EASTERN).date()]
        backfill = False

    # Load guest list once
    try:
        guest_set = sheets_client.load_guest_list_2025()
        print(f"Loaded {len(guest_set)} names from GuestList-2025.")
    except Exception as exc:
        print(f"WARNING: Could not load GuestList-2025: {exc}", file=sys.stderr)
        guest_set = set()

    # Process each date
    all_transactions = []
    sheet_error = None

    if backfill:
        print(f"Backfilling {len(dates)} date(s): {dates[0]} → {dates[-1]}")

    for target_date in dates:
        try:
            transactions, _ = square_client.get_daily_sales(target_date, full_day=backfill)
            print(f"  {target_date}: fetched {len(transactions)} transaction(s)")
        except Exception as exc:
            error_msg = f"Square fetch failed for {target_date}: {exc}"
            print(f"ERROR: {error_msg}", file=sys.stderr)
            try:
                email_notifier.send_error(target_date, error_msg)
            except Exception as email_exc:
                print(f"Error email alert also failed: {email_exc}", file=sys.stderr)
            sys.exit(1)

        for t in transactions:
            t["new_or_repeat"] = _is_repeat(t["name"], guest_set)

        try:
            sheets_client.append_to_square_sales(transactions)
        except Exception as exc:
            sheet_error = str(exc)
            print(f"ERROR: Sheet update failed for {target_date}: {sheet_error}", file=sys.stderr)

        all_transactions.extend(transactions)

    if all_transactions or not backfill:
        print(f"Appended {len(all_transactions)} total row(s) to SquareSales tab.")

    # Build combined summary for email
    donations = [t for t in all_transactions if t["type"] == "Donation"]
    tickets = [t for t in all_transactions if t["type"] == "Ticket"]
    summary = {
        "total_donations": round(sum(t["amount_paid"] for t in donations), 2),
        "total_tickets": sum(t["num_tickets"] for t in tickets),
        "donor_names": [t["name"] for t in donations if t["name"]],
        "ticket_buyers": [
            {"name": t["name"], "tickets": t["num_tickets"]}
            for t in tickets if t["name"]
        ],
        "total_after_fees": round(sum(t["amount_after_fees"] for t in all_transactions), 2),
    }

    report_date = dates[-1]

    try:
        email_notifier.send_summary(report_date, summary)
        if sheet_error:
            email_notifier.send_error(report_date, f"Sheet update failed: {sheet_error}")
        print("Email summary sent.")
    except Exception as exc:
        print(f"ERROR: Email notification failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if sheet_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
