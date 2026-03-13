# TRRP Nightly Sales Automation

Runs every night at 10 PM ET via GitHub Actions. Pulls daily sales from Square (donations + tickets), appends them to the `SquareSales` tab in the `TheRedRoomProject-2026` Google Spreadsheet, and sends a WhatsApp summary via CallMeBot.

## Project Structure

```
TRRP/
├── .github/workflows/
│   └── nightly-sales-report.yml   # Cron trigger + secrets
├── src/
│   ├── main.py                    # Orchestrator
│   ├── square_client.py           # Square Orders API
│   ├── sheets_client.py           # Google Sheets read/write
│   └── whatsapp_notifier.py       # CallMeBot WhatsApp
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Square API

1. Go to [Square Developer Dashboard](https://developer.squareup.com/apps) and create (or select) your app.
2. Under **Credentials**, copy the **Production Access Token** → `SQUARE_ACCESS_TOKEN`.
3. Under **Locations**, copy the **Location ID** for your venue → `SQUARE_LOCATION_ID`.
4. Find the identifiers for your two payment links (see note below) → `SQUARE_DONATION_LINK_ID`, `SQUARE_TICKET_LINK_ID`.

**How to find payment link identifiers**: After placing a test order through each link, look at the order in the Square Dashboard or via the API. The `source.name` field on the order typically contains the payment link name. Set `SQUARE_DONATION_LINK_ID` to a substring of that name (e.g., `"donation"`) and `SQUARE_TICKET_LINK_ID` to a substring of the ticket link name (e.g., `"ticket"`). The classification is case-insensitive substring match.

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

### 3. CallMeBot WhatsApp

1. Save the CallMeBot WhatsApp number in your phone contacts: **+34 644 37 79 39** (verify at [callmebot.com](https://www.callmebot.com/blog/free-api-whatsapp-messages/)).
2. Send this message to that contact on WhatsApp: `I allow callmebot to send me messages`
3. You will receive a reply with your **API key** → `CALLMEBOT_API_KEY`.
4. Your phone number in international format (e.g., `+15551234567`) → `CALLMEBOT_PHONE`.

---

### 4. GitHub Secrets

In your GitHub repo, go to **Settings → Secrets and Variables → Actions → New repository secret** and add each of these:

| Secret name | Description |
|---|---|
| `SQUARE_ACCESS_TOKEN` | Square production access token |
| `SQUARE_LOCATION_ID` | Square location ID |
| `SQUARE_DONATION_LINK_ID` | Substring of donation payment link source name |
| `SQUARE_TICKET_LINK_ID` | Substring of ticket payment link source name |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON content of the service account key file |
| `GOOGLE_SPREADSHEET_ID` | ID from the TheRedRoomProject-2026 spreadsheet URL |
| `CALLMEBOT_PHONE` | Your WhatsApp phone number (international format) |
| `CALLMEBOT_API_KEY` | API key received from CallMeBot activation |

---

## Running Manually

```bash
pip install -r requirements.txt

export SQUARE_ACCESS_TOKEN=...
export SQUARE_LOCATION_ID=...
export SQUARE_DONATION_LINK_ID=...
export SQUARE_TICKET_LINK_ID=...
export GOOGLE_SERVICE_ACCOUNT_JSON='{ ... }'
export GOOGLE_SPREADSHEET_ID=...
export CALLMEBOT_PHONE=...
export CALLMEBOT_API_KEY=...

python src/main.py
```

You can also trigger the workflow manually from the GitHub Actions tab using the **Run workflow** button.

---

## WhatsApp Message Format

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
- **CallMeBot limits**: Free tier, not SLA-backed. For production reliability consider [Green API](https://green-api.com/) or Telegram.
