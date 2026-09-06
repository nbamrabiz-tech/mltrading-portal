# ── Settings Tab ─────────────────
import streamlit as st
from db import get_engine
from datetime import date, timedelta, datetime
from sqlalchemy import text
import pytz
EST = pytz.timezone("America/New_York")

from queries.trades import get_latest_report


def render(engine, **kwargs):
    # TAB 8 — SETTINGS
    # ══════════════════════════════════════════════
    st.subheader("⚙️ Settings & Status")

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        st.success("✅ Supabase connected")
    except:
        st.error("❌ Connection failed")

    st.divider()
    st.markdown("### Data Summary")
    try:
        with engine.connect() as conn:
            tables={
                "price_data":    "Price rows",
                "economic_events":"Events",
                "news_headlines": "Headlines",
                "intelligence_reports":"Reports",
                "learning_log":  "Learning log",
                "trade_journal": "Trade journal",
                "behavioral_events":"Behavioral",
                "behavioral_scores":"B. Scores"
            }
            cols=st.columns(4)
            i=0
            for table,label in tables.items():
                try:
                    r=conn.execute(text(
                        f"SELECT COUNT(*) "
                        f"FROM {table}"))
                    count=r.fetchone()[0]
                    cols[i%4].metric(
                        label,f"{count:,}")
                except:
                    cols[i%4].metric(label,"N/A")
                i+=1
    except Exception as e:
        st.error(f"Stats error: {e}")

    st.divider()
    st.markdown("### Layer Status")
    layers={
        "Layer 1 — Data Pipeline":
            "✅ Railway 24/7",
        "Layer 2 — Probability Engine":
            "✅ Matrix lookup (204 days)",
        "Layer 3 — Decision Support":
            "✅ Complete",
        "Layer 4 — Risk + Drawdown":
            "✅ Complete",
        "Layer 5 — Trade Execution":
            "✅ Complete",
        "Layer 6 — Portal":
            "✅ Live v6",
        "Layer 7 — Behavioral Intel":
            "✅ Full auto-detection"
    }
    for layer,status in layers.items():
        st.markdown(f"**{layer}:** {status}")

