"""Sentinel dashboard — a single-file Streamlit view over the SQLite event log.

    streamlit run dashboard/app.py

Point a bot at a file db first: sentinel.init(..., db_path="sentinel.db").
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import streamlit as st
except ImportError:
    sys.exit("Install the dashboard extra:  pip install \"sentinel-trade[dashboard]\"")

from datetime import datetime

from sentinel.events import EventStore

st.set_page_config(page_title="Sentinel", page_icon="🛡️", layout="wide")
st.title("🛡️ Sentinel")

db_path = st.sidebar.text_input("Event DB path", value=os.environ.get("SENTINEL_DB", "sentinel.db"))
if st.sidebar.button("Refresh"):
    st.rerun()

if not os.path.exists(db_path):
    st.warning(f"No event db at `{db_path}`. Run a bot with `sentinel.init(..., db_path=\"{db_path}\")`.")
    st.stop()

store = EventStore(db_path)
events = store.recent(2000)
store.close()

ALERT_TYPES = {"halt", "drift", "silent_death", "slippage", "warning", "error"}
fills = [e for e in events if e.type == "fill"]
alerts = [e for e in events if e.type in ALERT_TYPES]

# --- headline metrics ---
cum_realized = sum(float(e.data.get("realized") or 0) for e in events if e.type == "fill")
last_halt = next((e for e in events if e.type == "halt"), None)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realized P&L (logged)", f"${cum_realized:,.2f}")
c2.metric("Fills", len(fills))
c3.metric("Alerts", len(alerts))
c4.metric("Status", "HALTED" if (last_halt and (not any(e.type == "resume" and e.ts > last_halt.ts for e in events))) else "running")

# --- alerts feed ---
st.subheader("⚠️ Guards & alerts")
if not alerts:
    st.success("No drift, halts, silent-death, or slippage alerts logged. Quiet is good.")
else:
    for e in alerts[:40]:
        ts = datetime.fromtimestamp(e.ts).strftime("%Y-%m-%d %H:%M:%S")
        icon = {"halt": "🛑", "drift": "⚠️", "silent_death": "🔴", "slippage": "📉", "warning": "🟡", "error": "❗"}.get(e.type, "•")
        detail = e.data.get("message") or ", ".join(f"{k}={v}" for k, v in e.data.items())
        st.markdown(f"{icon} **{e.type}** · `{ts}` — {detail}")

# --- cumulative P&L ---
st.subheader("📈 Cumulative realized P&L")
if fills:
    series, running = [], 0.0
    for e in reversed(fills):  # oldest first
        running += float(e.data.get("realized") or 0)
        series.append(running)
    st.line_chart(series)
else:
    st.caption("No fills logged yet.")

# --- recent events table ---
st.subheader("🧾 Recent events")
st.dataframe(
    [
        {
            "time": datetime.fromtimestamp(e.ts).strftime("%H:%M:%S"),
            "type": e.type,
            **{k: v for k, v in e.data.items()},
        }
        for e in events[:200]
    ],
    use_container_width=True,
)
