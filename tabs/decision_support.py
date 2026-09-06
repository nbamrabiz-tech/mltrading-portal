# ── Decision Support Tab ─────────
import streamlit as st
from datetime import date, timedelta, datetime
from sqlalchemy import text
import pytz
EST = pytz.timezone("America/New_York")


def render(engine, *args, **kwargs):
    # TAB 2 — DECISION SUPPORT
    # ══════════════════════════════════════════════
    st.subheader("🎯 Decision Support")
    report = get_latest_report()
    levels = get_spy_levels()

    if not report:
        st.warning("Run morning script first.")
    else:
        up_pct    = report.get("up_pct",33) or \
                    report.get("matrix_score",33) or 33
        down_pct  = report.get("down_pct",8) or 8
        range_pct = report.get("range_pct",50) or 50
        bias      = report.get("bias","Neutral") or "Neutral"
        conf      = report.get("confidence","") or ""

        sc1,sc2,sc3 = st.columns(3)
        sc1.metric("📈 Uptrend",   f"{up_pct}%")
        sc2.metric("📉 Downtrend", f"{down_pct}%")
        sc3.metric("➡️ Range",     f"{range_pct}%")

        ec = edge_color(conf)
        st.markdown(card(
            f'<p style="color:#666;font-size:11px;'
            f'margin:0;">EDGE</p>'
            f'<p style="color:{ec};font-size:18px;'
            f'font-weight:bold;margin:4px 0 0;">'
            f'{conf}</p>',
            border_color=ec
        ), unsafe_allow_html=True)

        st.divider()
        st.markdown("### Key Levels")
        lc1,lc2 = st.columns(2)
        for col,tkr in [(lc1,"SPY"),(lc2,"QQQ")]:
            with col:
                st.markdown(f"**{tkr}**")
                lv = levels.get(tkr,{})
                if lv:
                    k1,k2,k3 = st.columns(3)
                    k1.metric("PDH",
                        f"${lv['pdh']:.2f}","Resistance")
                    k2.metric("PDC",
                        f"${lv['pdc']:.2f}","Pivot")
                    k3.metric("PDL",
                        f"${lv['pdl']:.2f}","Support")

        div_sig = report.get(
            "divergence_signal","") or ""
        if div_sig:
            st.divider()
            st.warning(f"⚠️ **{div_sig}**")

    # ══════════════════════════════════════════════
