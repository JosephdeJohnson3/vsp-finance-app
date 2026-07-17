"""Google Sheets data layer for the VSP finance app.

The Google Sheet is the single source of truth. It has 4 simple tabs:
  Dashboard  — read-only summary (balances, who's owed, pipeline)
  Events     — one row per booking: money in, each person's share, status
  Payouts    — money paid out to each member/VSP
  History    — auto monthly rollup

The app reads and writes those tabs; the sheet's own formulas do all the math.
"""
import datetime as dt
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

from utils import parse_money

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

EVENTS_FIRST, EVENTS_LAST = 4, 63
PAY_FIRST, PAY_LAST = 4, 203

STATUSES = ["Inquiry", "Tentative", "Confirmed", "Deposit In", "Paid in Full"]
PEOPLE = ["Joseph", "Ethan", "Josh", "VSP"]

# Common split presets: (VSP%, Joseph%, Ethan%, Josh%)
SPLIT_PRESETS = {
    "Legacy — even (0 / 50 / 25 / 25)": (0, 50, 25, 25),
    "New — equal (10 / 30 / 30 / 30)": (10, 30, 30, 30),
    "New — Joseph led (10 / 40 / 25 / 25)": (10, 40, 25, 25),
    "New — Ethan led (10 / 25 / 40 / 25)": (10, 25, 40, 25),
    "New — Josh led (10 / 25 / 25 / 40)": (10, 25, 25, 40),
    "Custom": None,
}


@st.cache_resource
def _client():
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource
def _spreadsheet():
    return _client().open_by_key(st.secrets["sheet_id"])


def _ws(name):
    return _spreadsheet().worksheet(name)


def check_connection():
    _spreadsheet().title


def spreadsheet_url():
    return f"https://docs.google.com/spreadsheets/d/{st.secrets['sheet_id']}/edit"


# ------------------------------------------------------------------ Dashboard
@st.cache_data(ttl=20)
def read_dashboard():
    ws = _ws("Dashboard")
    g = ws.get("B4:B24")

    def v(row):
        idx = row - 4
        return g[idx][0] if idx < len(g) and g[idx] else ""

    return {
        "balance": v(4), "vsp_fund": v(5),
        "owed_joseph": v(8), "owed_ethan": v(9), "owed_josh": v(10), "owed_total": v(11),
        "pipeline": v(14),
        "start_cash": v(20), "reserve": v(21),
    }


# --------------------------------------------------------------------- Events
@st.cache_data(ttl=20)
def read_events():
    ws = _ws("Events")
    rows = ws.get(f"A{EVENTS_FIRST}:R{EVENTS_LAST}")
    out = []
    for i, r in enumerate(rows):
        r = r + [""] * (18 - len(r))
        if not r[0].strip():
            continue
        out.append({
            "row": EVENTS_FIRST + i,
            "event": r[0], "date": r[1], "location": r[2], "status": r[3],
            "total": r[4], "vsp_pct": r[5], "joseph_pct": r[6], "ethan_pct": r[7], "josh_pct": r[8],
            "pct_total": r[9], "vsp_amt": r[10], "joseph_amt": r[11], "ethan_amt": r[12], "josh_amt": r[13],
            "received": r[14], "remaining": r[15], "received_date": r[16], "notes": r[17],
        })
    return out


def _next_event_row():
    ws = _ws("Events")
    col_a = ws.col_values(1)
    for row in range(EVENTS_FIRST, EVENTS_LAST + 1):
        if len(col_a) < row or not col_a[row - 1].strip():
            return row
    return None


def add_event(name, date, location, status, total, vsp_pct, joseph_pct, ethan_pct, josh_pct,
              received=0, received_date=None, notes=""):
    row = _next_event_row()
    if row is None:
        raise RuntimeError("The Events tab is full. Ask Claude to add more rows.")
    ws = _ws("Events")
    date_s = date.isoformat() if hasattr(date, "isoformat") else (date or "")
    rd_s = received_date.isoformat() if hasattr(received_date, "isoformat") else (received_date or "")
    # Only the input columns; the sheet's formulas fill J,K,L,M,N,P and the helpers.
    ws.update(range_name=f"A{row}:I{row}",
              values=[[name, date_s, location, status,
                       total if total not in ("", None) else "",
                       vsp_pct, joseph_pct, ethan_pct, josh_pct]],
              value_input_option="USER_ENTERED")
    ws.update(range_name=f"O{row}", values=[[received or ""]], value_input_option="USER_ENTERED")
    ws.update(range_name=f"Q{row}:R{row}", values=[[rd_s, notes]], value_input_option="USER_ENTERED")
    st.cache_data.clear()
    return row


def update_event_status(row, status):
    _ws("Events").update(range_name=f"D{row}", values=[[status]], value_input_option="USER_ENTERED")
    st.cache_data.clear()


def update_event_received(row, received_amount, received_date=None, status=None):
    ws = _ws("Events")
    rd = received_date.isoformat() if hasattr(received_date, "isoformat") else (received_date or "")
    ws.update(range_name=f"O{row}", values=[[received_amount]], value_input_option="USER_ENTERED")
    ws.update(range_name=f"Q{row}", values=[[rd]], value_input_option="USER_ENTERED")
    if status:
        ws.update(range_name=f"D{row}", values=[[status]], value_input_option="USER_ENTERED")
    st.cache_data.clear()


def update_event_notes(row, notes):
    _ws("Events").update(range_name=f"R{row}", values=[[notes]], value_input_option="USER_ENTERED")
    st.cache_data.clear()


# -------------------------------------------------------------------- Payouts
@st.cache_data(ttl=20)
def read_payouts():
    ws = _ws("Payouts")
    rows = ws.get(f"A{PAY_FIRST}:D{PAY_LAST}")
    out = []
    for i, r in enumerate(rows):
        r = r + [""] * (4 - len(r))
        if not r[0].strip():
            continue
        out.append({"row": PAY_FIRST + i, "date": r[0], "person": r[1], "amount": r[2], "note": r[3]})
    return out


def _next_payout_row():
    ws = _ws("Payouts")
    col_a = ws.col_values(1)
    for row in range(PAY_FIRST, PAY_LAST + 1):
        if len(col_a) < row or not col_a[row - 1].strip():
            return row
    return None


def add_payout(date, person, amount, note=""):
    row = _next_payout_row()
    if row is None:
        raise RuntimeError("The Payouts tab is full. Ask Claude to add more rows.")
    ws = _ws("Payouts")
    date_s = date.isoformat() if hasattr(date, "isoformat") else (date or "")
    ws.update(range_name=f"A{row}:D{row}", values=[[date_s, person, amount, note]],
              value_input_option="USER_ENTERED")
    st.cache_data.clear()
    return row


# -------------------------------------------------------------------- History
@st.cache_data(ttl=20)
def read_history():
    ws = _ws("History")
    rows = ws.get("A4:H33")
    out = []
    for r in rows:
        r = r + [""] * (8 - len(r))
        if not r[0]:
            continue
        out.append({"month": r[0], "money_in": r[1], "joseph": r[2], "ethan": r[3],
                    "josh": r[4], "vsp": r[5], "total_paid": r[6], "net": r[7]})
    return out
