"""VSP Finance — internal Streamlit app. Reads/writes the same Google Sheet the
team already uses for financial tracking (see finance/VSP-Financial-Tracker.xlsx).
Adds one new tab ("Upcoming Events") for event notes; never edits the
original tabs' formulas, only the input cells VSP already fills by hand."""
import datetime as dt

import plotly.graph_objects as go
import streamlit as st

import sheets
from utils import fmt_money, parse_money

PEOPLE_COLORS = {"Joseph": "#2a78d6", "Ethan": "#1baf7a", "Josh": "#eda100", "VSP": "#008300"}
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

st.set_page_config(page_title="VSP Finance", page_icon="🎻", layout="wide")


def check_password():
    if st.session_state.get("authed"):
        return True
    st.title("🎻 VSP Finance")
    pw = st.text_input("Password", type="password")
    if st.button("Enter"):
        if pw == st.secrets.get("app_password"):
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Wrong password.")
    return False


if not check_password():
    st.stop()

try:
    sheets.check_connection()
except Exception as e:
    st.error("Not connected to Google Sheets yet.")
    st.write(
        "This is expected until the Google Sheets setup in `app/README.md` is finished "
        "(the Google Cloud service account + sharing the sheet with it). Once that's done "
        "this message goes away and real data shows up everywhere."
    )
    with st.expander("Technical details (for whoever's doing the setup)"):
        st.code(str(e))
    st.stop()

st.sidebar.title("🎻 VSP Finance")
st.sidebar.markdown(f"[📊 Open the Spreadsheet]({sheets.spreadsheet_url()})")
st.sidebar.divider()
page = st.sidebar.radio(
    "Go to",
    ["Dashboard", "History", "Upcoming Events", "Add Payment", "Event Log", "Accounts Receivable"],
)

def months_to_date(months_data):
    """Filters out months that haven't happened yet, so a 2+ year runway of
    pre-built formula rows doesn't clutter the UI with empty future months."""
    cutoff = dt.date.today().strftime("%Y-%m")
    return [m for m in months_data if m["month"] <= cutoff]

# ---------------------------------------------------------------- DASHBOARD
if page == "Dashboard":
    st.title("Dashboard")
    d = sheets.read_dashboard()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Balance", fmt_money(parse_money(d["current_balance"])))
    c2.metric("Reserve Floor", fmt_money(parse_money(d["reserve"])))
    c3.metric("VSP Fund Balance", fmt_money(parse_money(d["vsp_fund_balance"])))
    c4.metric("AR Outstanding", fmt_money(parse_money(d["ar_outstanding"])))

    st.subheader(f"This Month's Payout ({d['current_month']})")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Joseph", fmt_money(parse_money(d["this_month_joseph"])))
    c2.metric("Ethan", fmt_money(parse_money(d["this_month_ethan"])))
    c3.metric("Josh", fmt_money(parse_money(d["this_month_josh"])))
    c4.metric("Total", fmt_money(parse_money(d["this_month_total"])))

    st.subheader("Monthly Payout by Person (last 6 months)")
    months_data = months_to_date(sheets.read_monthly_summary())[-6:]
    if months_data:
        month_labels = [m["month"] for m in months_data]
        fig = go.Figure()
        for person, color in [("joseph", PEOPLE_COLORS["Joseph"]), ("ethan", PEOPLE_COLORS["Ethan"]),
                               ("josh", PEOPLE_COLORS["Josh"])]:
            values = [parse_money(m[person]) for m in months_data]
            fig.add_bar(
                name=person.capitalize(), x=month_labels, y=values,
                marker_color=color,
                text=[fmt_money(v) if v else "" for v in values],
                textposition="outside",
            )
        fig.update_layout(
            barmode="group", plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
            font=dict(color=INK), legend_title_text="",
            xaxis=dict(showgrid=False, linecolor=MUTED),
            yaxis=dict(showgrid=True, gridcolor=GRID, tickprefix="$", zeroline=False),
            margin=dict(t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No monthly data yet.")

    st.subheader("Combined Total Payout (Liquidation + Accounts Receivable)")
    rows = []
    for name, key in [("Joseph", "combined_joseph"), ("Ethan", "combined_ethan"), ("Josh", "combined_josh")]:
        c = d[key]
        rows.append({"Person": name, "Liquidation": c["liquidation"], "Accounts Receivable": c["ar"], "Total": c["total"]})
    st.table(rows)
    st.caption(f"Grand total once everything is collected: {d['grand_total']['total']}")

# ------------------------------------------------------------------- HISTORY
elif page == "History":
    st.title("History")
    st.caption("Every month to date, plus lifetime totals. Automatically grows as new months pass "
               "(the spreadsheet has formula rows built out through the end of 2028).")

    months_data = months_to_date(sheets.read_monthly_summary())

    if not months_data:
        st.info("No historical data yet.")
    else:
        lifetime = {"joseph": 0.0, "ethan": 0.0, "josh": 0.0, "vsp": 0.0, "total": 0.0}
        for m in months_data:
            for key in lifetime:
                lifetime[key] += parse_money(m[key])

        st.subheader("Lifetime Totals")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Joseph", fmt_money(lifetime["joseph"]))
        c2.metric("Ethan", fmt_money(lifetime["ethan"]))
        c3.metric("Josh", fmt_money(lifetime["josh"]))
        c4.metric("VSP Contributions", fmt_money(lifetime["vsp"]))
        c5.metric("Grand Total", fmt_money(lifetime["total"]))
        st.caption("VSP Contributions = the 10% collected from paid events only, not counting the "
                   "$1,000 reserve (see Dashboard for the full VSP Fund Balance).")

        st.subheader("Every Month to Date")
        month_labels = [m["month"] for m in months_data]
        fig = go.Figure()
        for person, color in [("joseph", PEOPLE_COLORS["Joseph"]), ("ethan", PEOPLE_COLORS["Ethan"]),
                               ("josh", PEOPLE_COLORS["Josh"])]:
            values = [parse_money(m[person]) for m in months_data]
            fig.add_bar(
                name=person.capitalize(), x=month_labels, y=values,
                marker_color=color,
                text=[fmt_money(v) if v else "" for v in values],
                textposition="outside",
            )
        fig.update_layout(
            barmode="group", plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
            font=dict(color=INK), legend_title_text="",
            xaxis=dict(showgrid=False, linecolor=MUTED),
            yaxis=dict(showgrid=True, gridcolor=GRID, tickprefix="$", zeroline=False),
            margin=dict(t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Monthly Breakdown Table")
        table_rows = [{"Month": m["month"], "Joseph": m["joseph"], "Ethan": m["ethan"],
                       "Josh": m["josh"], "VSP Contributions": m["vsp"], "Total": m["total"]}
                      for m in reversed(months_data)]
        st.table(table_rows)

# ------------------------------------------------------------- UPCOMING EVENTS
elif page == "Upcoming Events":
    STATUS_BADGE = {"Confirmed": "green", "Tentative": "orange", "Inquiry": "blue", "Completed": "gray"}

    title_col, add_col = st.columns([5, 1])
    title_col.title("Upcoming Events")
    with add_col:
        st.write("")  # vertical alignment nudge
        with st.popover("➕ Add Event", use_container_width=True):
            st.subheader("Add a new event")
            name = st.text_input("Event name")
            date = st.date_input("Date", value=dt.date.today())
            location = st.text_input("Location")
            status = st.selectbox("Status", sheets.UPCOMING_STATUSES)
            notes = st.text_area("Notes")
            who = st.selectbox("Added by", ["Joseph", "Ethan", "Josh"])
            if st.button("Add", type="primary"):
                if name.strip():
                    sheets.add_upcoming_event(name, date, location, status, notes, who)
                    st.success(f"Added {name}.")
                    st.rerun()
                else:
                    st.error("Event name is required.")

    items = sheets.read_upcoming_events()
    items.sort(key=lambda x: x["date"])

    if not items:
        st.info("Nothing here yet — click **➕ Add Event** to add one.")
    else:
        today = dt.date.today()
        for item in items:
            try:
                event_date = dt.date.fromisoformat(item["date"])
                days_out = (event_date - today).days
                when = ("Today" if days_out == 0 else
                        f"in {days_out} days" if days_out > 0 else
                        f"{-days_out} days ago")
            except ValueError:
                when = ""

            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"### {item['event']}")
                with c2:
                    st.badge(item["status"], color=STATUS_BADGE.get(item["status"], "gray"))
                st.write(f"📅 **{item['date']}**" + (f"  ·  {when}" if when else "") +
                         f"  ·  📍 {item['location'] or 'TBD'}")

                with st.expander("Details & edit"):
                    st.write(f"**Added by:** {item['created_by']} · **Last updated:** {item['last_updated']}")
                    if item["notes"]:
                        st.write(f"**Notes:** {item['notes']}")
                    new_status = st.selectbox(
                        "Status", sheets.UPCOMING_STATUSES,
                        index=sheets.UPCOMING_STATUSES.index(item["status"]) if item["status"] in sheets.UPCOMING_STATUSES else 0,
                        key=f"status_{item['row']}")
                    new_notes = st.text_area("Notes", value=item["notes"], key=f"notes_{item['row']}")
                    if st.button("Save changes", key=f"save_{item['row']}"):
                        sheets.update_upcoming_event(item["row"], new_status, new_notes)
                        st.success("Saved.")
                        st.rerun()

# ------------------------------------------------------------- ADD PAYMENT
elif page == "Add Payment":
    st.title("Add a New Payment")
    st.caption("This writes directly into the Event Log tab of the spreadsheet. VSP automatically "
               "takes 10% off the top; the rest splits per whichever option you pick below.")

    with st.form("add_payment"):
        name = st.text_input("Event / client name")
        col1, col2 = st.columns(2)
        date = col1.date_input("Event date", value=dt.date.today())
        gross = col2.number_input("Gross amount ($)", min_value=0.0, step=50.0)
        split_type = st.selectbox("Split type", sheets.SPLIT_TYPES)
        lead = st.selectbox("Who found / ran point on this booking?", sheets.LEAD_GENERATORS)
        notes = st.text_input("Notes (optional)")
        submitted = st.form_submit_button("Add payment")

    if submitted:
        if not name.strip() or gross <= 0:
            st.error("Event name and a gross amount greater than $0 are required.")
        else:
            try:
                result = sheets.append_event_log_entry(name, date, gross, split_type, lead, notes)
                st.success(f"Added to Event Log, row {result['row']}.")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("VSP (10%)", fmt_money(parse_money(result["vsp_amt"])))
                c2.metric("Joseph", fmt_money(parse_money(result["joseph_amt"])))
                c3.metric("Ethan", fmt_money(parse_money(result["ethan_amt"])))
                c4.metric("Josh", fmt_money(parse_money(result["josh_amt"])))
            except RuntimeError as e:
                st.error(str(e))

# ----------------------------------------------------------------- EVENT LOG
elif page == "Event Log":
    st.title("Event Log")
    st.caption("Every payment entered through this app or directly in the spreadsheet. "
               "Mark an event Paid once the money actually arrives, so it flows into Monthly Summary.")
    entries = sheets.read_event_log()
    if not entries:
        st.info("No events logged yet.")
    for e in entries:
        label = f"{e['event']} — {e['date']} — {fmt_money(parse_money(e['gross']))} ({e['status']})"
        with st.expander(label):
            st.write(f"**Split:** {e['split_type']} · **Lead:** {e['lead']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("VSP", fmt_money(parse_money(e["vsp_amt"])))
            c2.metric("Joseph", fmt_money(parse_money(e["joseph_amt"])))
            c3.metric("Ethan", fmt_money(parse_money(e["ethan_amt"])))
            c4.metric("Josh", fmt_money(parse_money(e["josh_amt"])))
            if e["notes"]:
                st.write(f"**Notes:** {e['notes']}")
            if e["status"] == "Pending":
                if st.button("Mark Paid", key=f"paid_{e['row']}"):
                    sheets.mark_event_log_paid(e["row"])
                    st.success("Marked paid.")
                    st.rerun()
            else:
                st.write(f"Paid {e['date_paid']}")

# ------------------------------------------------------- ACCOUNTS RECEIVABLE
elif page == "Accounts Receivable":
    st.title("Accounts Receivable")
    st.caption("The already-booked events, split 50/25/25 the old way. Mark one Received once "
               "the money actually arrives.")
    ar = sheets.read_accounts_receivable()
    for row in ar:
        label = f"{row['event']} — {row['location']} — {fmt_money(parse_money(row['gross']))} ({row['status']})"
        with st.expander(label):
            c1, c2, c3 = st.columns(3)
            c1.metric("Joseph", fmt_money(parse_money(row["joseph_amt"])))
            c2.metric("Ethan", fmt_money(parse_money(row["ethan_amt"])))
            c3.metric("Josh", fmt_money(parse_money(row["josh_amt"])))
            if row["notes"]:
                st.write(f"**Notes:** {row['notes']}")
            if row["status"] == "Pending":
                if st.button("Mark Received", key=f"recv_{row['row']}"):
                    sheets.mark_ar_received(row["row"])
                    st.success("Marked received.")
                    st.rerun()
            else:
                st.write(f"Received {row['date_received']}")
