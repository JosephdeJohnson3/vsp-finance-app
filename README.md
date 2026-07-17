# VSP Finance App — Setup Guide

This app reads and writes the same Google Sheet your team already uses for financial
tracking. It adds one new tab, **Upcoming Events**, and never touches the
formulas in your existing tabs, only the same input cells you already fill in by
hand.

There are 5 steps. Steps 1–3 you only ever do once. Budget about 20 minutes.

---

## Step 1: Move the Excel file to Google Sheets (skip if already done)

1. Go to [sheets.google.com](https://sheets.google.com).
2. File → Import → Upload → select `VSP-Financial-Tracker.xlsx` → **Replace spreadsheet**.
3. Everything (formulas, dropdowns, formatting) carries over as-is.
4. Copy the URL from your browser's address bar. It looks like:
   `https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit`
   The long string between `/d/` and `/edit` is your **Sheet ID** — save it, you'll need it in Step 4.

## Step 2: Create a Google Cloud "service account" (the app's own login)

This is a robot account Google Sheets treats like any other person you'd share the
sheet with — except it belongs to the app, not to you.

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and sign in with
   your Google account (the same one that owns the Sheet, or any Google account).
2. If prompted, create a new project. Call it anything, e.g. "VSP Finance App."
3. In the search bar at the top, search for **"Google Sheets API"** and open it. Click
   **Enable**.
4. In the left sidebar, go to **APIs & Services → Credentials**.
5. Click **+ Create Credentials → Service account**.
6. Give it a name (e.g. "vsp-finance-app"), click through the remaining screens with
   the defaults, then **Done**.
7. Click into the service account you just created. Go to the **Keys** tab.
8. **Add Key → Create new key → JSON → Create**. A `.json` file downloads to your
   computer. **Keep this file private** — it's the password for your Sheet.
9. Open that JSON file in a text editor. You'll paste its values into Streamlit's
   secrets box in Step 4.

## Step 3: Share your Google Sheet with the service account

1. Open the JSON file from Step 2. Find the field called `"client_email"` — it looks
   like `something@your-project.iam.gserviceaccount.com`.
2. Open your Google Sheet, click **Share** (top right), paste that email address in,
   give it **Editor** access, and send.

## Step 4: Put this code on GitHub

Streamlit Cloud deploys from a GitHub repository.

1. If you don't have one, make a free account at [github.com](https://github.com).
2. Create a **new repository** (it can be private). Name it something like
   `vsp-finance-app`.
3. Upload every file in this `app/` folder to that repository (GitHub's web
   interface lets you drag and drop files directly — no command line needed).
   **Do not upload `secrets.toml.example` renamed to `secrets.toml` with real values
   in it** — real secrets go into Streamlit Cloud directly in Step 5, never into
   GitHub.

## Step 5: Deploy on Streamlit Community Cloud (free)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **New app**, pick the repository from Step 4, and set the main file path to
   `app.py`.
3. Before clicking Deploy, open **Advanced settings → Secrets** and paste in this
   shape, filling in your real values (see `.streamlit/secrets.toml.example` in this
   folder for the exact template):

   ```toml
   app_password = "pick-a-password-the-three-of-you-will-use"
   sheet_id = "the-id-you-copied-in-step-1"

   [gcp_service_account]
   type = "service_account"
   project_id = "..."
   private_key_id = "..."
   private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   client_email = "...@....iam.gserviceaccount.com"
   client_id = "..."
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "..."
   universe_domain = "googleapis.com"
   ```

   Copy every value straight from the JSON file you downloaded in Step 2 — the field
   names match exactly. The `private_key` field is long and contains `\n` characters;
   copy it exactly as it appears in the JSON, quotes and all.
4. Click **Deploy**. After a minute or two you'll get a public URL like
   `https://vsp-finance.streamlit.app` — that's the link all three of you use from
   then on, from any phone or laptop.

---

## Using the app day to day

- **Dashboard** — account balance, VSP fund, this month's payout, and a chart of
  everyone's monthly payout over time.
- **Upcoming Events** — add any show you're tracking (booked or not), with
  notes. This lives entirely in its own tab and never touches your financial tabs.
- **Add Payment** — enter a new booked event: name, date, total fee, split type,
  and who found the lead. It writes straight into the Event Log tab and shows you
  the computed split instantly. If the client pays a deposit first (usually 50%)
  and the rest later, pick "Deposit now, balance later" — the app creates two
  rows, "(Deposit)" and "(Balance)", so each chunk counts in the month it
  actually arrives.
- **Event Log** — every payment ever entered (via the app or by hand in the sheet).
  Mark one "Paid" once the money actually lands. For deposit/balance pairs, mark
  each row separately as each payment comes in.
- **Accounts Receivable** — the 4 already-booked events on the old 50/25/25 split.
  Mark one "Received" once it arrives.

## If something breaks

- **"Event Log is full"** error: all 30 pre-built rows in the spreadsheet's Event Log
  tab are used. Ask Claude to extend it with more formula rows.
- Changes not showing up immediately: the app caches reads for 30 seconds to avoid
  hitting Google's rate limits. Wait a moment or just refresh.
- Wrong numbers: check the spreadsheet directly first — the app only displays what's
  already there. If the sheet itself looks right but the app doesn't, something's
  broken in the app, not the data.
