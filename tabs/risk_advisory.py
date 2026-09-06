# ── Risk Advisory Tab ────────────
import streamlit as st
from datetime import date, timedelta, datetime
from sqlalchemy import text
import pytz
EST = pytz.timezone("America/New_York")


def render(engine, *args, **kwargs):
    # TAB 3 — RISK ADVISORY
    # ══════════════════════════════════════════════
    st.subheader("⚖️ Risk Advisory")
    col_b,col_c = st.columns(2)

    with col_b:
        st.markdown("### Risk Budget")
        account = st.number_input(
            "Account size ($)",
            min_value=1000,max_value=1000000,
            value=10000,step=1000)
        risk_tier = st.radio("Risk tier",[
            "0.25% — Minimal",
            "0.50% — Reduced",
            "0.75% — Normal",
            "1.00% — Full"],index=1)
        risk_map = {
            "0.25% — Minimal":0.25,
            "0.50% — Reduced":0.50,
            "0.75% — Normal": 0.75,
            "1.00% — Full":   1.00}
        risk_pct  = risk_map[risk_tier]
        max_risk  = round(account*risk_pct/100,2)
        daily_lim = round(max_risk*3,2)

        report = get_latest_report()
        tp = (report.get("trade_prob",30)
              if report else 30) or 30
        max_trades = (1 if tp<45 else 2 if tp<60
                      else 3)

        rc1,rc2 = st.columns(2)
        rc1.metric("Max Risk/Trade",
            f"${max_risk:,.2f}",
            f"{risk_pct}% of account")
        rc2.metric("Daily Limit",
            f"${daily_lim:,.2f}",
            f"Max {max_trades} trades")

        if report and report.get("is_event_day"):
            st.warning("⚠️ Event day — use lower tier")

        dd = get_drawdown()
        if dd and dd["current"] != 0:
            st.divider()
            st.markdown("### Drawdown Tracker")
            dd1,dd2,dd3 = st.columns(3)
            dd1.metric("Peak P&L",
                f"${dd['peak']:+.2f}")
            dd2.metric("Current P&L",
                f"${dd['current']:+.2f}")
            dd3.metric("Drawdown",
                f"${dd['drawdown']:+.2f}",
                f"{dd['drawdown_pct']:.1f}%")
            if dd["peak"] > 0:
                pct_used = min(100,
                    abs(dd["drawdown"])
                    /dd["peak"]*100)
                color = ("#CC0000" if pct_used>20
                         else "#FF8C00"
                         if pct_used>10
                         else "#0066CC")
                st.markdown(
                    f"<div style='margin-top:8px;'>"
                    f"<p style='color:#666;"
                    f"font-size:12px;margin:0;'>"
                    f"Drawdown: {pct_used:.1f}%</p>"
                    f"<div style='background:#E8E8E8;"
                    f"border-radius:4px;height:10px;"
                    f"margin-top:4px;'>"
                    f"<div style='background:{color};"
                    f"width:{pct_used:.0f}%;height:10px;"
                    f"border-radius:4px;'></div>"
                    f"</div></div>",
                    unsafe_allow_html=True
                )

    with col_c:
        st.markdown("### Trade Calculator")
        ticker_c = st.selectbox("Ticker",
            ["NQ","ES","MNQ","MES","SPY","QQQ"],
            key="calc_ticker")
        pv_map = {"NQ":20,"ES":50,"MNQ":2,
                  "MES":5,"SPY":1,"QQQ":1}
        pv = pv_map.get(ticker_c,1)

        entry = st.number_input("Entry",
            value=21500.0,step=0.25,format="%.2f")
        stop  = st.number_input("Stop",
            value=21480.0,step=0.25,format="%.2f")

        if entry != stop:
            rps       = abs(entry-stop)
            direction = ("Long" if stop<entry
                         else "Short")
            dollar_risk = rps*pv
            contracts = max(1,int(
                max_risk/dollar_risk
            )) if dollar_risk>0 else 1

            t1=round(entry+rps if direction=="Long"
                     else entry-rps,2)
            t2=round(entry+rps*2 if direction=="Long"
                     else entry-rps*2,2)
            t3=round(entry+rps*3 if direction=="Long"
                     else entry-rps*3,2)

            st.markdown(card(
                f'<b>{direction} — '
                f'{contracts} contract(s)</b><br>'
                f'<span style="color:#666;'
                f'font-size:12px;">Risk: '
                f'${dollar_risk:.2f} | Total: '
                f'${dollar_risk*contracts:.2f}'
                f'</span><br><br>'
                f'<span style="color:#CC0000;">'
                f'1:1 → {t1:.2f} '
                f'(+${dollar_risk*contracts:.0f})'
                f'</span><br>'
                f'<span style="color:#FF8C00;">'
                f'1:2 → {t2:.2f} '
                f'(+${dollar_risk*contracts*2:.0f})'
                f'</span><br>'
                f'<span style="color:#0066CC;">'
                f'1:3 → {t3:.2f} '
                f'(+${dollar_risk*contracts*3:.0f})'
                f'</span>'
            ), unsafe_allow_html=True)

    # ══════════════════════════════════════════════
