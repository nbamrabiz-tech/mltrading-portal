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


def render(engine, today, now_est, **kwargs):
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

        # ── Signal determination ──────────────
        if up_pct >= 50:
            dominant = "UPTREND"
            dc = "#0066CC"
            de = "📈"
            action = "Look for long setups with the trend."
        elif down_pct >= 50:
            dominant = "DOWNTREND"
            dc = "#CC0000"
            de = "📉"
            action = "Look for short setups with the trend."
        elif range_pct >= 50:
            dominant = "RANGE BOUND"
            dc = "#FF8C00"
            de = "➡️"
            action = "Range trade between key levels or sit out."
        else:
            dominant = "NO CLEAR EDGE"
            dc = "#888888"
            de = "⚪"
            action = "No statistical backing today. Sitting out protects capital."

        # Get matrix context
        matrix_type = report.get("matrix_type",
                      report.get("matrix","?")) or "?"
        total_days  = report.get("total_days", 0) or 0
        similar_days = max(
            int(up_pct/100*(total_days or 100)),
            int(down_pct/100*(total_days or 100)),
            int(range_pct/100*(total_days or 100)))

        # ── Main signal card ──────────────────
        st.markdown(
            f"<div style='background:{dc}15;"
            f"padding:18px 20px;border-radius:10px;"
            f"border-left:4px solid {dc};"
            f"margin-bottom:16px;'>"
            f"<div style='display:flex;"
            f"align-items:center;gap:12px;'>"
            f"<span style='font-size:36px;'>{de}</span>"
            f"<div>"
            f"<div style='color:{dc};font-size:22px;"
            f"font-weight:800;'>{dominant}</div>"
            f"<div style='color:#555;font-size:13px;"
            f"margin-top:4px;'>{action}</div>"
            f"</div></div>"
            f"</div>",
            unsafe_allow_html=True)

        # ── Historical context ─────────────────
        st.markdown(
            f"<div style='background:#F8F9FA;"
            f"border-radius:8px;padding:12px 16px;"
            f"margin-bottom:12px;'>"
            f"<p style='color:#888;font-size:11px;"
            f"text-transform:uppercase;margin:0 0 8px;'>"
            f"📊 Based on historical analysis</p>"
            f"<div style='display:flex;gap:24px;'>"
            f"<div style='text-align:center;'>"
            f"<div style='font-size:24px;font-weight:800;"
            f"color:#0066CC;'>{up_pct}%</div>"
            f"<div style='font-size:12px;color:#888;'>Uptrend</div>"
            f"</div>"
            f"<div style='text-align:center;'>"
            f"<div style='font-size:24px;font-weight:800;"
            f"color:#CC0000;'>{down_pct}%</div>"
            f"<div style='font-size:12px;color:#888;'>Downtrend</div>"
            f"</div>"
            f"<div style='text-align:center;'>"
            f"<div style='font-size:24px;font-weight:800;"
            f"color:#FF8C00;'>{range_pct}%</div>"
            f"<div style='font-size:12px;color:#888;'>Range</div>"
            f"</div>"
            f"<div style='border-left:1px solid #ddd;"
            f"padding-left:24px;'>"
            f"<div style='font-size:13px;color:#555;'>"
            f"Trade probability: "
            f"<b style='color:{'#0066CC' if tp>=50 else '#CC0000'};'>"
            f"{tp}%</b></div>"
            f"<div style='font-size:12px;color:#888;'>"
            f"{'Above' if tp>=50 else 'Below'} our 50% threshold</div>"
            f"</div>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True)

        st.divider()
        col_l, col_r = st.columns([3,2])

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

