# VSP Finance App

A simple money tracker for The Virginia Strings Project. The Google Sheet is the
**single source of truth** — the app and the spreadsheet are two windows into the
same data, always in sync. Edit in whichever you prefer.

## The four tabs / pages

- **Dashboard** — where the money stands: account balance, VSP fund, what each
  person is still owed (what to pay next), the pipeline still to collect, and the
  next events.
- **Events** — one row per booking. Name, date, location, status, the total fee,
  and each person's percentage and dollar share. **The status drives the money:**
  set an event to **Deposit In** and it counts 50% of the total as received; set it
  to **Paid in Full** and it counts the whole amount. Balance and "still owed"
  update automatically. Status: Inquiry → Tentative → Confirmed → Deposit In → Paid in Full.
- **Payouts** — money paid out to Joseph, Ethan, Josh, or VSP. Logging a payout
  reduces what that person is "still owed" on the Dashboard.
- **History** — every month's money in and money out, automatic.

## How the money ties together

- **Account balance** = starting cash + everything received on events − everything paid out.
- **Still owed to a person** = their share of money received − what they've been paid.
- **VSP fund** = reserve + VSP's cut of money received − VSP payouts.

Everything recalculates the moment you change anything, in the app or the sheet.

## Editing in the spreadsheet directly

"The Excel" is now the Google Sheet. Open it from the sidebar link (or
[sheets.google.com](https://sheets.google.com)), edit the **blue** cells (black
cells are formulas — don't overwrite them). Want a downloadable Excel copy? In the
sheet: **File → Download → Microsoft Excel (.xlsx)**.

## Deployment

Runs on Streamlit Community Cloud, deploying from this GitHub repo. Secrets (the
password, the Sheet ID, and the Google service-account key) live in Streamlit
Cloud's Secrets box, never in the repo. See `.streamlit/secrets.toml.example` for
the shape.

## If something looks off

- Changes not showing instantly: the app caches reads for ~20 seconds. Refresh.
- Wrong number: check the sheet directly first — the app only shows what's there.
- A red "% total" cell on the Events tab means an event's four percentages don't
  add up to 100.
