"""Leads engine for the VSP app — completely separate from the finance tabs.

Finds potential clients on Reddit (public posts, read-only, official API), tiers
them by brand fit, and writes them to a "Leads" tab in the same Google Sheet.
No formulas link this tab to Events/Payouts — it is a standalone data list.

Compliant by design: read-only (never posts), public data + official API only.
Source-pluggable so Eventbrite / Meetup / search / B2B directories can be added
later as more find_* functions writing to the same tab.
"""
import datetime as dt

import streamlit as st

import sheets  # reuse the cached gspread connection (_spreadsheet, _ws)

LEADS_TAB = "Leads"
LEADS_HEADERS = ["Found", "Tier", "Source", "Title", "Why", "Link", "Subreddit",
                 "Status", "Notes", "Contacted by", "Contacted date"]
LEAD_STATUSES = ["New", "Contacted", "Replied", "Booked", "Dead"]
LEAD_TIERS = ["Hot", "Warm", "Cold"]

# Subreddits to scan (editable). Mix of wedding/event/brand + a few metros.
SUBREDDITS = ["weddingplanning", "weddingsunder10k", "wedding", "Bridgerton",
              "EventPlanning", "partyplanning", "nova", "washingtondc", "nashville"]

# Search queries run across the subreddits above.
QUERIES = ['"string trio"', '"string quartet"', "violinist", '"live music"',
           '"wedding music"', '"ceremony music"', "Bridgerton", "classical",
           '"cocktail hour" music', '"hire a" musician']

# Keyword tiers (all lowercase). A lead's tier is the highest it matches.
HOT = ["string trio", "string quartet", "string ensemble", "string duo", "string quintet",
       "violin", "violinist", "viola", "cello", "cellist", "pianist", "piano",
       "classical music", "chamber music", "bridgerton", "string players"]
WARM = ["live music", "live musician", "musician", "acoustic", "ceremony music",
        "cocktail hour", "wedding music", "instrumental", "hire music", "band for",
        "music for our", "string"]
COLD = ["getting married", "engaged", "wedding", "reception", "gala", "fundraiser",
        "corporate event", "party", "celebration", "anniversary", "bridal",
        "elopement", "vow renewal", "gathering"]


# ---------------------------------------------------------------- classification
def classify(title, body=""):
    """Return (tier, why) or (None, None) if it doesn't look like a lead."""
    text = f"{title} {body}".lower()

    def matches(terms):
        return [t for t in terms if t in text]

    hot, warm, cold = matches(HOT), matches(WARM), matches(COLD)
    if hot:
        tier, hits = "Hot", hot
    elif warm:
        tier, hits = "Warm", warm
    elif cold:
        tier, hits = "Cold", cold
    else:
        return None, None
    why = f"{tier} — mentions: " + ", ".join(dict.fromkeys(hits[:4]))
    return tier, why


# ------------------------------------------------------------------- Leads tab
def ensure_leads_tab():
    sh = sheets._spreadsheet()
    if LEADS_TAB not in [w.title for w in sh.worksheets()]:
        ws = sh.add_worksheet(title=LEADS_TAB, rows=500, cols=len(LEADS_HEADERS))
        ws.update(range_name="A1", values=[LEADS_HEADERS])
        ws.format("A1:K1", {"textFormat": {"bold": True}})
        ws.freeze(rows=1)


@st.cache_data(ttl=20)
def read_leads():
    ensure_leads_tab()
    ws = sheets._ws(LEADS_TAB)
    rows = ws.get("A2:K1000")
    out = []
    for i, r in enumerate(rows):
        r = r + [""] * (11 - len(r))
        if not r[3].strip() and not r[5].strip():  # no title and no link -> empty row
            continue
        out.append({
            "row": i + 2, "found": r[0], "tier": r[1], "source": r[2], "title": r[3],
            "why": r[4], "link": r[5], "subreddit": r[6], "status": r[7],
            "notes": r[8], "contacted_by": r[9], "contacted_date": r[10],
        })
    return out


def update_lead(row, status, notes, contacted_by=""):
    ws = sheets._ws(LEADS_TAB)
    cdate = dt.date.today().isoformat() if status != "New" else ""
    ws.update(range_name=f"H{row}:K{row}",
              values=[[status, notes, contacted_by, cdate]],
              value_input_option="USER_ENTERED")
    st.cache_data.clear()


# ----------------------------------------------------------------- Reddit find
@st.cache_resource
def _reddit():
    import praw
    r = st.secrets["reddit"]
    return praw.Reddit(client_id=r["client_id"], client_secret=r["client_secret"],
                       user_agent=r.get("user_agent", "vsp-leads"), check_for_async=False)


def reddit_configured():
    return "reddit" in st.secrets and st.secrets["reddit"].get("client_id")


def find_new_leads(per_query=25):
    """Search Reddit, classify, and append genuinely new leads. Returns count added."""
    if not reddit_configured():
        raise RuntimeError("Reddit isn't set up yet. Add your [reddit] credentials "
                           "in the app's secrets (see the README).")
    ensure_leads_tab()
    ws = sheets._ws(LEADS_TAB)

    existing = set(x for x in ws.col_values(6) if x)  # column F = Link
    reddit = _reddit()
    multi = reddit.subreddit("+".join(SUBREDDITS))

    seen, new_rows = set(existing), []
    today = dt.date.today().isoformat()
    for q in QUERIES:
        try:
            for sub in multi.search(q, sort="new", time_filter="year", limit=per_query):
                link = "https://www.reddit.com" + sub.permalink
                if link in seen:
                    continue
                tier, why = classify(sub.title, (sub.selftext or "")[:2000])
                if not tier:
                    continue
                seen.add(link)
                new_rows.append([today, tier, "Reddit", str(sub.title)[:250], why, link,
                                 str(sub.subreddit), "New", "", "", ""])
        except Exception:
            continue  # one bad query shouldn't kill the run

    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")
        st.cache_data.clear()
    return len(new_rows)
