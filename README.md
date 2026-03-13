# TRRP Nightly Sales Automation

Runs every night at 10 PM ET via GitHub Actions. Pulls daily sales from Square (donations + tickets), appends them to the `SquareSales` tab in the `TheRedRoomProject-2026` Google Spreadsheet, and sends a summary email via Gmail.

## Project Structure

```
TRRP/
├── .github/workflows/
│   └── nightly-sales-report.yml   # Cron trigger + secrets
├── src/
│   ├── main.py                    # Orchestrator
│   ├── square_client.py           # Square Orders API
│   ├── sheets_client.py           # Google Sheets read/write
│   └── email_notifier.py          # Gmail SMTP notification
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Square API

1. Go to [Square Developer Dashboard](https://developer.squareup.com/apps) and create (or select) your app.
2. Under **Credentials**, copy the **Production Access Token** → `SQUARE_ACCESS_TOKEN`.
3. Under **Locations**, copy the **Location ID** for your venue → `SQUARE_LOCATION_ID`.
4. Find the **line item names** used in each payment link (see note below) → `SQUARE_DONATION_ITEM_NAME`, `SQUARE_TICKET_ITEM_NAME`.

**How to find line item names**: In the Square Dashboard, go to **Items & Orders → Payment Links**, open each link, and note the item name attached to it (e.g. `"Donation"` or `"General Admission"`). Set `SQUARE_DONATION_ITEM_NAME` to the exact name (or a unique substring) of the donation link's item, and `SQUARE_TICKET_ITEM_NAME` to the ticket link's item name. Matching is case-insensitive substring. If unset, defaults to `"donation"` and `"ticket"` respectively.

---

### 2. Google Sheets Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project (or use an existing one).
2. Enable the **Google Sheets API** and **Google Drive API**.
3. Create a **Service Account**: IAM & Admin → Service Accounts → Create.
4. Download the JSON key file for the service account.
5. Share the `TheRedRoomProject-2026` spreadsheet with the service account's email address (give it **Editor** access).
6. Copy the spreadsheet ID from its URL (the long string between `/d/` and `/edit`) → `GOOGLE_SPREADSHEET_ID`.
7. Paste the entire contents of the JSON key file as the `GOOGLE_SERVICE_ACCOUNT_JSON` secret.

**Expected sheet tabs**:
- `SquareSales` — must exist with this header row in row 1:
  `Name | Phone Number | Email | Donation or Ticket | Number of Tickets | Amount Paid | Amount after fees | New or Repeat | Date`
- `GuestList-2025` — must exist, containing prior-year guest names (used for New/Repeat detection). Read-only.

---

### 3. Gmail App Password

The script sends email from your Gmail address to yourself using an App Password (no OAuth needed).

1. Go to [myaccount.google.com](https://myaccount.google.com) → **Security**
2. Make sure **2-Step Verification** is enabled (required for App Passwords)
3. Search **"App passwords"** in the Security page search bar
4. Click **App passwords** → create one named e.g. `TRRP Script`
5. Copy the 16-character password → `GMAIL_APP_PASSWORD` secret
6. Your Gmail address (e.g. `you@gmail.com`) → `GMAIL_ADDRESS` secret

---

### 4. GitHub Secrets

In your GitHub repo, go to **Settings → Secrets and Variables → Actions → New repository secret** and add each of these:

| Secret name | Description |
|---|---|
| `SQUARE_ACCESS_TOKEN` | Square production access token |
| `SQUARE_LOCATION_ID` | Square location ID |
| `SQUARE_DONATION_ITEM_NAME` | Line item name (or substring) on the donation payment link |
| `SQUARE_TICKET_ITEM_NAME` | Line item name (or substring) on the ticket payment link |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON content of the service account key file |
| `GOOGLE_SPREADSHEET_ID` | ID from the TheRedRoomProject-2026 spreadsheet URL |
| `GMAIL_ADDRESS` | Your Gmail address (send-from and send-to) |
| `GMAIL_APP_PASSWORD` | 16-character App Password from Google Account → Security |

---

## Running Manually

```bash
pip install -r requirements.txt

export SQUARE_ACCESS_TOKEN=...
export SQUARE_LOCATION_ID=...
export SQUARE_DONATION_ITEM_NAME=...
export SQUARE_TICKET_ITEM_NAME=...
export GOOGLE_SERVICE_ACCOUNT_JSON='{ ... }'
export GOOGLE_SPREADSHEET_ID=...
export GMAIL_ADDRESS=...
export GMAIL_APP_PASSWORD=...

python src/main.py
```

You can also trigger the workflow manually from the GitHub Actions tab using the **Run workflow** button.

---

## Email Format

**Subject:** `TRRP Daily Sales Report - Mar 12, 2026`

**Body:**
```
Daily Sales Report - Mar 12, 2026
Donations: $100.00
Tickets: 2
Donor Names: Alice Smith, Bob Jones
Ticket buyer Names: Carol White(1), Dave Brown(2)
TRRP total after fees: $185.50
```

---

## Notes

- **DST drift**: The cron is fixed at 3 AM UTC. This equals 10 PM EST (Nov–Mar) and 11 PM EDT (Mar–Nov). One hour of drift during summer is acceptable since all same-day sales are still captured.
- **Name matching**: New/Repeat detection uses exact case-insensitive matching against the `GuestList-2025` tab. If you need fuzzy matching (e.g., "Bob" vs "Robert"), add `thefuzz` to `requirements.txt` and update `main.py`.
- **Square sandbox**: Set `environment="sandbox"` in `square_client.py` and use sandbox credentials to test without real transactions.
