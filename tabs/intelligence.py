# ── Daily Intelligence Tab ───────
import streamlit as st
from datetime import date, timedelta, datetime
from sqlalchemy import text
import pytz
EST = pytz.timezone("America/New_York")

from queries.trades import (
    get_latest_report, get_todays_events,
    get_spy_levels, get_learning_log)
from utils.formatting import (
    card, prob_bar, edge_color, candle_color)


def render(engine, *args, **kwargs):
    # TAB 1 — DAILY INTELLIGENCE
    # ══════════════════════════════════════════════
    report = get_latest_report()
    events = get_todays_events()
    levels = get_spy_levels()

    if report:
        rpt_date = report.get("report_date",today)
        if str(rpt_date) != str(today):
            st.warning(
                f"⚠️ Showing {rpt_date}. "
                f"Run morning script to update.")

    if not report:
        st.warning("No report. Run morning script.")
    else:
        up_pct    = report.get("up_pct",33) or \
                    report.get("matrix_score",33) or 33
        down_pct  = report.get("down_pct",8) or 8
        range_pct = report.get("range_pct",50) or 50
        tp     = report.get("trade_prob",30) or 30
        bias   = report.get("bias","No Clear Edge") \
                 or "No Clear Edge"
        conf   = report.get("confidence","No Edge") \
                 or "No Edge"
        ie     = report.get("is_event_day",False)

        reaction = report.get("reaction_type","") or ""
        narr_hl  = report.get(
            "narrative_headline","") or ""

        if up_pct >= 50:
            dominant="UPTREND";   dc="#0066CC"; de="📈"
        elif down_pct >= 50:
            dominant="DOWNTREND"; dc="#CC0000"; de="📉"
        elif range_pct >= 50:
            dominant="RANGE BOUND";dc="#FF8C00";de="➡️"
        else:
            dominant="NO CLEAR EDGE";dc="#888";de="⚪"

        st.markdown(
            f"<div style='background:{dc}15;"
            f"padding:16px;border-radius:8px;"
            f"border-left:4px solid {dc};"
            f"margin-bottom:16px;text-align:center;'>"
            f"<p style='color:{dc};font-size:28px;"
            f"font-weight:bold;margin:0;'>"
            f"{de} {dominant}</p>"
            f"<p style='color:#666;font-size:13px;"
            f"margin:4px 0 0;'>{conf}</p></div>",
            unsafe_allow_html=True
        )

        c1,c2,c3,c4 = st.columns(4)
        for col, val, label, threshold in [
            (c1, up_pct,    "📈 UPTREND",   50),
            (c2, down_pct,  "📉 DOWNTREND", 50),
            (c3, range_pct, "➡️ RANGE",     50),
            (c4, tp,        "TRADE PROB",   65)
        ]:
            vc = ("#0066CC" if val>=threshold
                  else "#888888")
            if label == "📉 DOWNTREND":
                vc = ("#CC0000" if val>=threshold
                      else "#888888")
            elif label == "➡️ RANGE":
                vc = ("#FF8C00" if val>=threshold
                      else "#888888")
            elif label == "TRADE PROB":
                vc = ("#0066CC" if val>=65
                      else "#CC0000" if val<=35
                      else "#FF8C00")
            col.markdown(card(
                f'<p style="color:#666;margin:0;'
                f'font-size:11px;">{label}</p>'
                f'<p style="color:{vc};margin:4px 0 2px;'
                f'font-size:28px;font-weight:bold;">'
                f'{val}%</p>'
                + prob_bar(val,vc),
                border_color=vc
            ), unsafe_allow_html=True)

        ec = edge_color(conf)
        st.markdown(card(
            f'<p style="color:#666;font-size:11px;'
            f'margin:0;">EDGE | ACTION</p>'
            f'<p style="color:{ec};font-size:16px;'
            f'font-weight:bold;margin:4px 0 2px;">'
            f'{conf}</p>'
            f'<p style="color:#333;font-size:13px;'
            f'margin:0;">{reaction}</p>',
            border_color=ec
        ), unsafe_allow_html=True)

        st.divider()
        col_l, col_r = st.columns([3,2])

        with col_l:
            st.subheader("📰 Today's Narrative")
            st.markdown(card(
                f'<p style="color:#333;font-size:14px;'
                f'line-height:1.6;margin:0;">'
                f'{narr_hl}</p>'
            ), unsafe_allow_html=True)
            m1,m2 = st.columns(2)
            m1.metric("Event Day",
                "Yes ★★★" if ie else "No")
            m2.metric("Trade Probability",f"{tp}%")

        with col_r:
            st.subheader("🕯️ First Candle")
            spy_dir  = report.get(
                "spy_candle_dir","Awaiting") or "Awaiting"
            spy_conv = report.get(
                "spy_candle_conv","") or ""
            qqq_dir  = report.get(
                "qqq_candle_dir","Awaiting") or "Awaiting"
            qqq_conv = report.get(
                "qqq_candle_conv","") or ""
            div_sig  = report.get(
                "divergence_signal","") or ""

            cc1,cc2 = st.columns(2)
            for col,tkr,d,cv in [
                (cc1,"SPY",spy_dir,spy_conv),
                (cc2,"QQQ",qqq_dir,qqq_conv)
            ]:
                col.markdown(card(
                    f'<p style="color:#666;'
                    f'font-size:11px;margin:0;">'
                    f'{tkr}</p>'
                    f'<p style="color:{candle_color(d)};'
                    f'font-size:16px;font-weight:bold;'
                    f'margin:4px 0 0;">{d}</p>'
                    f'<p style="color:#888;'
                    f'font-size:11px;margin:0;">'
                    f'{cv}</p>',
                    border_color=candle_color(d)
                ), unsafe_allow_html=True)

            if div_sig:
                st.warning(f"⚠️ {div_sig}")

        st.divider()
        st.subheader("📍 Key Levels")
        kc1,kc2 = st.columns(2)
        for col,tkr in [(kc1,"SPY"),(kc2,"QQQ")]:
            with col:
                st.markdown(f"**{tkr}**")
                lv = levels.get(tkr,{})
                if lv:
                    l1,l2,l3 = st.columns(3)
                    l1.metric("PDH",f"${lv['pdh']:.2f}")
                    l2.metric("PDC",f"${lv['pdc']:.2f}")
                    l3.metric("PDL",f"${lv['pdl']:.2f}")

        if events:
            st.divider()
            st.subheader("📅 Today's Events")
            for ev in events:
                ic = ("#CC0000" if ev[3]=="High"
                      else "#FF8C00")
                actual=ev[1]; previous=ev[2]
                diff_txt=""
                if actual and previous:
                    diff=float(actual)-float(previous)
                    diff_txt=(f" ↑ {diff:+.2f}"
                              if diff>0
                              else f" ↓ {diff:+.2f}")
                st.markdown(card(
                    f'<span style="color:{ic};'
                    f'font-size:11px;font-weight:bold;">'
                    f'[{ev[3]}]</span>'
                    f'<span style="color:#333;'
                    f'margin-left:8px;">{ev[0]}</span>'
                    f'<span style="color:#888;'
                    f'font-size:12px;margin-left:12px;">'
                    f'A:{actual} P:{previous}'
                    f'{diff_txt}</span>',
                    border_color=ic
                ), unsafe_allow_html=True)
        else:
            st.info(f"No events for {today}.")

    # ══════════════════════════════════════════════
