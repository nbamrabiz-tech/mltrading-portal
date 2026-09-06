# ── Sentiment Tab ────────────────
import streamlit as st
from datetime import date, timedelta, datetime
from sqlalchemy import text
import pytz
EST = pytz.timezone("America/New_York")

from queries.trades import get_latest_report
from utils.formatting import card


def render(engine, today, **kwargs):
    # TAB 4 — SENTIMENT
    # ══════════════════════════════════════════════
    st.subheader("😊 Market Sentiment")
    report = get_latest_report()
    events = get_todays_events()

    if report:
        up_pct    = report.get("up_pct",33) or \
                    report.get("matrix_score",33) or 33
        down_pct  = report.get("down_pct",8) or 8
        range_pct = report.get("range_pct",50) or 50
        ie        = report.get("is_event_day",False)
        conf      = report.get("confidence","") or ""

        sc1,sc2,sc3,sc4 = st.columns(4)
        sc1.metric("📈 Uptrend",   f"{up_pct}%")
        sc2.metric("📉 Downtrend", f"{down_pct}%")
        sc3.metric("➡️ Range",     f"{range_pct}%")
        sc4.metric("Event Day","Yes ★★★" if ie else "No")

        st.divider()
        st.markdown(card(
            f'<p style="color:#333;font-size:13px;'
            f'line-height:1.8;margin:0;">'
            f'<b>Step 1:</b> You classify narrative '
            f'(B/R/C/W/U/N)<br>'
            f'<b>Step 2:</b> System reads first '
            f'5-min candle at 9:35 AM<br>'
            f'<b>Step 3:</b> Matrix type → '
            f'historical probabilities<br>'
            f'<b>Step 4:</b> Up% / Down% / Range%<br>'
            f'<br><b>No ML. No VIX. '
            f'No arbitrary weights.</b></p>'
        ), unsafe_allow_html=True)

    if events:
        st.divider()
        st.markdown("### Today's Events")
        for ev in events:
            ic=("#CC0000" if ev[3]=="High"
                else "#FF8C00")
            actual=ev[1]; previous=ev[2]
            arrow=""
            if actual and previous:
                diff=float(actual)-float(previous)
                arrow=" ↑" if diff>0 else " ↓"
            st.markdown(card(
                f'<b style="color:{ic};">'
                f'[{ev[3]}]</b> '
                f'<span style="color:#333;">'
                f'{ev[0]}</span>'
                f'<br><span style="color:#666;'
                f'font-size:12px;">'
                f'A:{actual} P:{previous}{arrow}'
                f'</span>',
                border_color=ic
            ), unsafe_allow_html=True)

    # ══════════════════════════════════════════════
