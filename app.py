"""VSP Finance — a simple money tracker for The Virginia Strings Project.

Backed by one Google Sheet (the single source of truth):
  Dashboard — where the money stands
  Events    — every booking, its money, each person's share, and status
  Payouts   — money paid out to the group
  History   — every past month
  Leads     — potential clients found on Reddit (separate from the finance tabs)
"""
import datetime as dt

import plotly.graph_objects as go
import streamlit as st

import sheets
import leads
from utils import fmt_money, parse_money

COLORS = {"Joseph": "#2a78d6", "Ethan": "#1baf7a", "Josh": "#eda100", "VSP": "#008300"}
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
STATUS_COLOR = {"Inquiry": "gray", "Tentative": "orange", "Confirmed": "blue",
                "Deposit In": "violet", "Paid in Full": "green"}
LEAD_TIER_COLOR = {"Hot": "red", "Warm": "orange", "Cold": "blue"}
LEAD_TIER_EMOJI = {"Hot": "🔥", "Warm": "🌤️", "Cold": "❄️"}

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
    with st.expander("Details"):
        st.code(str(e))
    st.stop()

st.sidebar.title("🎻 VSP Finance")
st.sidebar.markdown(f"[📊 Open the spreadsheet]({sheets.spreadsheet_url()})")
st.sidebar.divider()
page = st.sidebar.radio("Go to", ["Dashboard", "Events", "Payouts", "History", "Leads"])


def money(x):
    return fmt_money(parse_money(x))


def _to_int(x):
    try:
        return int(round(float(str(x).strip() or 0)))
    except ValueError:
        return 0


def _to_date(s):
    try:
        return dt.date.fromisoformat(str(s).strip())
    except ValueError:
        return None


# ============================================================== DASHBOARD
if page == "Dashboard":
    st.title("Dashboard")
    d = sheets.read_dashboard()

    c1, c2 = st.columns(2)
    c1.metric("💰 Account balance", money(d["balance"]), help="Actual cash on hand right now.")
    c2.metric("🏦 VSP fund", money(d["vsp_fund"]), help="Company's cut plus the reserve.")

    st.subheader("Still owed to each person")
    st.caption("Money earned from payments received, but not yet paid out. This is what to pay next.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Joseph", money(d["owed_joseph"]))
    c2.metric("Ethan", money(d["owed_ethan"]))
    c3.metric("Josh", money(d["owed_josh"]))
    c4.metric("Total to pay out", money(d["owed_total"]))

    st.subheader("Pipeline")
    st.metric("Still to collect on confirmed events", money(d["pipeline"]),
              help="Money still coming in from events marked Confirmed.")

    st.subheader("Next events")
    events = [e for e in sheets.read_events()
              if e["status"] not in ("Paid in Full",) and e["date"]]
    events.sort(key=lambda e: e["date"])
    if events:
        for e in events[:5]:
            total = money(e["total"]) if parse_money(e["total"]) else "TBD"
            st.write(f"**{e['event']}** — {e['date']} · {e['location'] or 'TBD'} · "
                     f"{total} · _{e['status']}_")
    else:
        st.info("No upcoming events. Add one on the Events page.")

# ================================================================= EVENTS
elif page == "Events":
    st.title("Events")
    st.caption("Every booking, how much it's worth, each person's share, and where the money is.")

    # ---- add event ----
    with st.popover("➕ Add event", use_container_width=False):
        st.subheader("New event")
        name = st.text_input("Event / client name")
        c1, c2 = st.columns(2)
        date = c1.date_input("Date", value=dt.date.today())
        location = c2.text_input("Location")
        status = st.selectbox("Status", sheets.STATUSES, index=2)
        total = st.number_input("Total fee ($)", min_value=0.0, step=50.0,
                                help="The full amount the client pays.")
        preset = st.selectbox("Split", list(sheets.SPLIT_PRESETS.keys()), index=0,
                              help="Pick a preset, then adjust the four percentages if needed. "
                                   "They must add up to 100.")
        defaults = sheets.SPLIT_PRESETS[preset] or (0, 50, 25, 25)
        c1, c2, c3, c4 = st.columns(4)
        vsp_pct = c1.number_input("VSP %", 0, 100, defaults[0], step=5)
        jo_pct = c2.number_input("Joseph %", 0, 100, defaults[1], step=5)
        e_pct = c3.number_input("Ethan %", 0, 100, defaults[2], step=5)
        josh_pct = c4.number_input("Josh %", 0, 100, defaults[3], step=5)
        pct_sum = vsp_pct + jo_pct + e_pct + josh_pct
        if pct_sum != 100:
            st.warning(f"Percentages add up to {pct_sum}%, not 100%.")
        notes = st.text_area("Notes / details")
        if st.button("Add event", type="primary"):
            if not name.strip():
                st.error("Event name is required.")
            elif pct_sum != 100 and total > 0:
                st.error("The four percentages must add up to 100.")
            else:
                sheets.add_event(name, date, location, status,
                                 total if total > 0 else "", vsp_pct, jo_pct, e_pct, josh_pct,
                                 notes=notes)
                st.success(f"Added {name}.")
                st.rerun()

    events = sheets.read_events()
    events.sort(key=lambda e: (e["status"] == "Paid in Full", e["date"] or "9999"))
    if not events:
        st.info("No events yet — click **➕ Add event**.")

    for e in events:
        total_disp = money(e["total"]) if parse_money(e["total"]) else "TBD"
        with st.container(border=True):
            top1, top2 = st.columns([4, 1])
            top1.markdown(f"### {e['event']}")
            top2.badge(e["status"], color=STATUS_COLOR.get(e["status"], "gray"))
            st.write(f"📅 {e['date'] or 'TBD'} · 📍 {e['location'] or 'TBD'} · **{total_disp}**")

            if parse_money(e["total"]):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Joseph", money(e["joseph_amt"]))
                c2.metric("Ethan", money(e["ethan_amt"]))
                c3.metric("Josh", money(e["josh_amt"]))
                c4.metric("VSP", money(e["vsp_amt"]))
                recv, rem = parse_money(e["received"]), parse_money(e["remaining"])
                if recv > 0:
                    st.write(f"✅ Received **{money(e['received'])}**"
                             + (f" · still owed **{money(e['remaining'])}**" if rem > 0.005 else " · paid in full"))

            with st.expander("Details, notes & update"):
                if e["notes"]:
                    st.write(e["notes"])
                st.markdown("**Update status**")
                st.caption("Status drives the money: **Deposit In** counts 50% of the total as received, "
                           "**Paid in Full** counts the whole amount. Balance and what's owed update automatically.")
                new_status = st.selectbox("Status", sheets.STATUSES,
                                          index=sheets.STATUSES.index(e["status"]) if e["status"] in sheets.STATUSES else 0,
                                          key=f"st_{e['row']}", label_visibility="collapsed")
                rdate = None
                if new_status in ("Deposit In", "Paid in Full"):
                    rdate = st.date_input("Date the money came in (for the monthly history)",
                                          value=dt.date.today(), key=f"rd_{e['row']}")
                if st.button("Save status", key=f"savest_{e['row']}"):
                    sheets.update_event_status(e["row"], new_status, received_date=rdate)
                    st.success("Saved.")
                    st.rerun()

                st.divider()
                with st.form(f"edit_{e['row']}"):
                    st.markdown("**Edit details**")
                    en = st.text_input("Event name", value=e["event"], key=f"en_{e['row']}")
                    c1, c2 = st.columns(2)
                    ed = c1.date_input("Date", value=_to_date(e["date"]), key=f"ed_{e['row']}")
                    eloc = c2.text_input("Location", value=e["location"], key=f"eloc_{e['row']}")
                    etot = st.number_input("Total fee ($)", min_value=0.0, step=50.0,
                                           value=float(parse_money(e["total"])), key=f"etot_{e['row']}")
                    st.caption("Percentages (VSP + the three of you must add to 100).")
                    c1, c2, c3, c4 = st.columns(4)
                    evsp = c1.number_input("VSP %", 0, 100, _to_int(e["vsp_pct"]), step=5, key=f"evsp_{e['row']}")
                    ejo = c2.number_input("Joseph %", 0, 100, _to_int(e["joseph_pct"]), step=5, key=f"ejo_{e['row']}")
                    eet = c3.number_input("Ethan %", 0, 100, _to_int(e["ethan_pct"]), step=5, key=f"eet_{e['row']}")
                    ejosh = c4.number_input("Josh %", 0, 100, _to_int(e["josh_pct"]), step=5, key=f"ejosh_{e['row']}")
                    enotes = st.text_area("Notes", value=e["notes"], key=f"enotes_{e['row']}")
                    if st.form_submit_button("Save details"):
                        psum = evsp + ejo + eet + ejosh
                        if not en.strip():
                            st.error("Event name is required.")
                        elif etot > 0 and psum != 100:
                            st.error(f"Percentages add up to {psum}%, not 100%.")
                        else:
                            sheets.update_event_details(
                                e["row"], en, ed, eloc, e["status"],
                                etot if etot > 0 else "", evsp, ejo, eet, ejosh, notes=enotes)
                            st.success("Saved.")
                            st.rerun()

                st.divider()
                st.markdown("**Delete this event**")
                confirm = st.checkbox("Yes, remove this event from the list",
                                      key=f"delchk_{e['row']}")
                if st.button("🗑️ Delete event", key=f"delbtn_{e['row']}", disabled=not confirm):
                    sheets.delete_event(e["row"])
                    st.success("Deleted.")
                    st.rerun()

# ================================================================ PAYOUTS
elif page == "Payouts":
    st.title("Payouts")
    st.caption("Money paid out to the group. Log each dividend or payment here so the Dashboard "
               "knows what's still owed.")

    d = sheets.read_dashboard()
    c1, c2, c3 = st.columns(3)
    c1.metric("Owed to Joseph", money(d["owed_joseph"]))
    c2.metric("Owed to Ethan", money(d["owed_ethan"]))
    c3.metric("Owed to Josh", money(d["owed_josh"]))

    with st.popover("➕ Log a payout", use_container_width=False):
        st.subheader("New payout")
        c1, c2 = st.columns(2)
        pdate = c1.date_input("Date", value=dt.date.today())
        person = c2.selectbox("Person", sheets.PEOPLE)
        amount = st.number_input("Amount ($)", min_value=0.0, step=50.0)
        note = st.text_input("For / notes", placeholder="e.g. August dividend")
        if st.button("Log payout", type="primary"):
            if amount <= 0:
                st.error("Enter an amount greater than $0.")
            else:
                sheets.add_payout(pdate, person, amount, note)
                st.success(f"Logged {money(amount)} to {person}.")
                st.rerun()

    st.subheader("Payout history")
    payouts = sheets.read_payouts()
    payouts.sort(key=lambda p: p["date"], reverse=True)
    if not payouts:
        st.info("No payouts logged yet.")
    else:
        st.table([{"Date": p["date"], "Person": p["person"],
                   "Amount": money(p["amount"]), "For": p["note"]} for p in payouts])

# ================================================================ HISTORY
elif page == "History":
    st.title("History")
    st.caption("Every month's money in and money out. Fills in automatically as payments and payouts happen.")

    rows = sheets.read_history()
    cutoff = dt.date.today().strftime("%Y-%m")
    rows = [r for r in rows if r["month"] <= cutoff]

    active = [r for r in rows if any(parse_money(r[k]) for k in ("money_in", "total_paid"))]
    if not active:
        st.info("No activity yet. Months will appear here as money moves.")
    else:
        lifetime_in = sum(parse_money(r["money_in"]) for r in rows)
        lifetime_out = sum(parse_money(r["total_paid"]) for r in rows)
        c1, c2, c3 = st.columns(3)
        c1.metric("Lifetime money in", fmt_money(lifetime_in))
        c2.metric("Lifetime paid out", fmt_money(lifetime_out))
        c3.metric("Months tracked", str(len(active)))

        labels = [r["month"] for r in active]
        fig = go.Figure()
        fig.add_bar(name="Money in", x=labels, y=[parse_money(r["money_in"]) for r in active],
                    marker_color="#1baf7a")
        fig.add_bar(name="Paid out", x=labels, y=[parse_money(r["total_paid"]) for r in active],
                    marker_color="#e34948")
        fig.update_layout(barmode="group", plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                          font=dict(color=INK), legend_title_text="",
                          xaxis=dict(showgrid=False, linecolor=MUTED),
                          yaxis=dict(showgrid=True, gridcolor=GRID, tickprefix="$", zeroline=False),
                          margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Month by month")
        st.table([{"Month": r["month"], "In": money(r["money_in"]),
                   "Joseph": money(r["joseph"]), "Ethan": money(r["ethan"]),
                   "Josh": money(r["josh"]), "VSP": money(r["vsp"]),
                   "Paid out": money(r["total_paid"])} for r in reversed(active)])

# ================================================================== LEADS
elif page == "Leads":
    st.title("Leads")
    st.caption("Potential clients found on Reddit, ranked by how well they fit VSP. "
               "This is completely separate from the finance tabs. Reach out yourself "
               "through the link (follow each subreddit's rules).")

    if not leads.reddit_configured():
        st.warning("Reddit isn't connected yet, so new leads can't be pulled. "
                   "Add your [reddit] credentials in the app secrets — see the README "
                   "(reddit.com/prefs/apps → create a 'script' app, ~3 minutes, free).")
    else:
        c1, c2 = st.columns([1, 3])
        if c1.button("🔎 Find new leads", type="primary"):
            with st.spinner("Searching Reddit…"):
                try:
                    n = leads.find_new_leads()
                    st.success(f"Added {n} new lead{'s' if n != 1 else ''}." if n
                               else "No new leads this time — try again later.")
                except Exception as e:
                    st.error(str(e))

    all_leads = leads.read_leads()
    if not all_leads:
        st.info("No leads yet. Click **🔎 Find new leads** to pull some in.")
    else:
        tier_counts = {t: sum(1 for x in all_leads if x["tier"] == t) for t in leads.LEAD_TIERS}
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 Hot", tier_counts.get("Hot", 0))
        c2.metric("🌤️ Warm", tier_counts.get("Warm", 0))
        c3.metric("❄️ Cold", tier_counts.get("Cold", 0))

        f1, f2 = st.columns(2)
        tier_filter = f1.multiselect("Show tiers", leads.LEAD_TIERS, default=["Hot", "Warm"])
        hide_dead = f2.checkbox("Hide Dead / Booked", value=True)

        shown = [x for x in all_leads
                 if (not tier_filter or x["tier"] in tier_filter)
                 and not (hide_dead and x["status"] in ("Dead", "Booked"))]
        order = {"Hot": 0, "Warm": 1, "Cold": 2}
        shown.sort(key=lambda x: (order.get(x["tier"], 3), x["found"]), reverse=False)

        st.caption(f"{len(shown)} shown")
        for x in shown:
            with st.container(border=True):
                top1, top2 = st.columns([4, 1])
                emoji = LEAD_TIER_EMOJI.get(x["tier"], "")
                top1.markdown(f"**{x['title']}**")
                top2.badge(f"{emoji} {x['tier']}", color=LEAD_TIER_COLOR.get(x["tier"], "gray"))
                st.write(f"{x['why']}  ·  r/{x['subreddit']}  ·  found {x['found']}")
                if x["link"]:
                    st.markdown(f"[Open the post ↗]({x['link']})")
                with st.expander(f"Status: {x['status'] or 'New'} — update"):
                    new_status = st.selectbox("Status", leads.LEAD_STATUSES,
                                              index=leads.LEAD_STATUSES.index(x["status"]) if x["status"] in leads.LEAD_STATUSES else 0,
                                              key=f"ls_{x['row']}")
                    who = st.selectbox("By", ["", "Joseph", "Ethan", "Josh"],
                                       index=(["", "Joseph", "Ethan", "Josh"].index(x["contacted_by"])
                                              if x["contacted_by"] in ("", "Joseph", "Ethan", "Josh") else 0),
                                       key=f"lby_{x['row']}")
                    lnotes = st.text_area("Notes", value=x["notes"], key=f"ln_{x['row']}")
                    if st.button("Save", key=f"lsave_{x['row']}"):
                        leads.update_lead(x["row"], new_status, lnotes, who)
                        st.success("Saved.")
                        st.rerun()
