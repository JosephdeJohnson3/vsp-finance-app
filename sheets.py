"""Google Sheets data layer for the VSP finance app. Talks to the same spreadsheet
the team already uses; never touches the 7 original tabs' formulas, only their
designated input cells, plus one new tab this app owns entirely."""
import datetime as dt
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

AR_FIRST_ROW = 4
AR_LAST_ROW = 7
EVENTLOG_FIRST_ROW = 4
EVENTLOG_LAST_ROW = 33
SPLIT_TYPES = ["Equal (30/30/30)", "Lead Bonus (40/25/25)", "Partial Lead (35/27.5/27.5)"]
LEAD_GENERATORS = ["Joseph", "Ethan", "Josh", "N/A"]
UPCOMING_TAB = "Upcoming Events"
UPCOMING_HEADERS = ["Event Name", "Date", "Location", "Status", "Notes", "Created By", "Last Updated"]
UPCOMING_STATUSES = ["Inquiry", "Tentative", "Confirmed", "Completed"]


@st.cache_resource
def _client():
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource
def _spreadsheet():
    return _client().open_by_key(st.secrets["sheet_id"])


def ensure_upcoming_tab_exists():
    sh = _spreadsheet()
    titles = [ws.title for ws in sh.worksheets()]
    if UPCOMING_TAB not in titles:
        ws = sh.add_worksheet(title=UPCOMING_TAB, rows=200, cols=len(UPCOMING_HEADERS))
        ws.update(range_name="A1", values=[UPCOMING_HEADERS])
        ws.format("A1:G1", {"textFormat": {"bold": True}})


def _ws(name):
    return _spreadsheet().worksheet(name)


def check_connection():
    """Cheap call that fails the same way any real read would, used to show one
    friendly message up front instead of a raw traceback on every page."""
    _spreadsheet().title


@st.cache_data(ttl=30)
def read_dashboard():
    ws = _ws("Dashboard")
    col_b = ws.get("B3:B20")

    def v(row_offset):
        idx = row_offset - 3
        return col_b[idx][0] if idx < len(col_b) and col_b[idx] else ""

    combined = ws.get("B24:D27")  # Joseph, Ethan, Josh, Grand Total rows; cols = Liquidation, AR, Combined
    combined = combined + [["", "", ""]] * (4 - len(combined))
    combined = [row + [""] * (3 - len(row)) for row in combined]

    return {
        "current_month": v(3),
        "current_balance": v(6),
        "reserve": v(7),
        "available_liquidation": v(8),
        "vsp_fund_balance": v(9),
        "ar_outstanding": v(12),
        "ar_received_this_month": v(13),
        "this_month_joseph": v(17),
        "this_month_ethan": v(18),
        "this_month_josh": v(19),
        "this_month_total": v(20),
        "combined_joseph": {"liquidation": combined[0][0], "ar": combined[0][1], "total": combined[0][2]},
        "combined_ethan": {"liquidation": combined[1][0], "ar": combined[1][1], "total": combined[1][2]},
        "combined_josh": {"liquidation": combined[2][0], "ar": combined[2][1], "total": combined[2][2]},
        "grand_total": {"liquidation": combined[3][0], "ar": combined[3][1], "total": combined[3][2]},
    }


@st.cache_data(ttl=30)
def read_monthly_summary():
    """Reads every populated month row (currently 2026-07 through 2028-12), so
    this grows with the sheet without needing code changes. Skips the TOTAL row."""
    ws = _ws("Monthly Summary")
    rows = ws.get("A5:F200")
    out = []
    for r in rows:
        if not r or not r[0] or r[0].strip().upper() == "TOTAL":
            continue
        r = r + [""] * (6 - len(r))
        out.append({"month": r[0], "joseph": r[1], "ethan": r[2], "josh": r[3], "vsp": r[4], "total": r[5]})
    return out


def spreadsheet_url():
    return f"https://docs.google.com/spreadsheets/d/{st.secrets['sheet_id']}/edit"


@st.cache_data(ttl=30)
def read_accounts_receivable():
    ws = _ws("Accounts Receivable")
    rows = ws.get(f"A{AR_FIRST_ROW}:M{AR_LAST_ROW}")
    out = []
    for i, r in enumerate(rows):
        r = r + [""] * (13 - len(r))
        out.append({
            "row": AR_FIRST_ROW + i, "event": r[0], "location": r[1], "gross": r[2],
            "joseph_amt": r[6], "ethan_amt": r[7], "josh_amt": r[8],
            "status": r[9], "date_received": r[10], "notes": r[12],
        })
    return out


def mark_ar_received(row, date_str=None):
    date_str = date_str or dt.date.today().isoformat()
    ws = _ws("Accounts Receivable")
    ws.update(range_name=f"J{row}:K{row}", values=[["Received", date_str]])
    st.cache_data.clear()


@st.cache_data(ttl=30)
def read_event_log():
    ws = _ws("Event Log")
    rows = ws.get(f"A{EVENTLOG_FIRST_ROW}:R{EVENTLOG_LAST_ROW}")
    out = []
    for i, r in enumerate(rows):
        r = r + [""] * (18 - len(r))
        if not r[0]:
            continue
        out.append({
            "row": EVENTLOG_FIRST_ROW + i, "event": r[0], "date": r[1], "gross": r[2],
            "vsp_amt": r[4], "net": r[5], "split_type": r[6], "lead": r[7],
            "joseph_amt": r[11], "ethan_amt": r[12], "josh_amt": r[13],
            "status": r[14], "date_paid": r[15], "notes": r[17],
        })
    return out


def find_next_empty_event_log_row():
    ws = _ws("Event Log")
    col_a = ws.col_values(1)
    for row in range(EVENTLOG_FIRST_ROW, EVENTLOG_LAST_ROW + 1):
        if len(col_a) < row or not col_a[row - 1].strip():
            return row
    return None


def append_event_log_entry(event_name, event_date, gross_amount, split_type, lead_generator, notes=""):
    """Writes only the input cells VSP already fills by hand; existing formulas
    in that row compute everything else. Returns the row written and the
    freshly computed split (Sheets recalculates formulas the instant cells change)."""
    row = find_next_empty_event_log_row()
    if row is None:
        raise RuntimeError("Event Log is full (all 30 pre-built rows used). Ask Claude to extend it.")
    ws = _ws("Event Log")
    ws.update(range_name=f"A{row}:C{row}", values=[[event_name, event_date.isoformat(), gross_amount]])
    ws.update(range_name=f"G{row}:H{row}", values=[[split_type, lead_generator]])
    ws.update(range_name=f"O{row}", values=[["Pending"]])
    if notes:
        ws.update(range_name=f"R{row}", values=[[notes]])
    st.cache_data.clear()
    computed = ws.get(f"E{row}:N{row}")[0]
    computed = computed + [""] * (10 - len(computed))
    return {
        "row": row, "vsp_amt": computed[0], "net": computed[1],
        "joseph_pct": computed[4], "ethan_pct": computed[5], "josh_pct": computed[6],
        "joseph_amt": computed[7], "ethan_amt": computed[8], "josh_amt": computed[9],
    }


def mark_event_log_paid(row, date_str=None):
    date_str = date_str or dt.date.today().isoformat()
    ws = _ws("Event Log")
    ws.update(range_name=f"O{row}:P{row}", values=[["Paid", date_str]])
    st.cache_data.clear()


@st.cache_data(ttl=30)
def read_upcoming_events():
    ensure_upcoming_tab_exists()
    ws = _ws(UPCOMING_TAB)
    rows = ws.get("A2:G500")
    out = []
    for i, r in enumerate(rows):
        r = r + [""] * (7 - len(r))
        if not r[0]:
            continue
        out.append({
            "row": i + 2, "event": r[0], "date": r[1], "location": r[2],
            "status": r[3], "notes": r[4], "created_by": r[5], "last_updated": r[6],
        })
    return out


def add_upcoming_event(event_name, event_date, location, status, notes, created_by):
    ensure_upcoming_tab_exists()
    ws = _ws(UPCOMING_TAB)
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    ws.append_row([event_name, event_date.isoformat(), location, status, notes, created_by, now])
    st.cache_data.clear()


def update_upcoming_event(row, status, notes):
    ws = _ws(UPCOMING_TAB)
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    ws.update(range_name=f"D{row}:G{row}", values=[[status, notes, ws.acell(f"F{row}").value, now]])
    st.cache_data.clear()
