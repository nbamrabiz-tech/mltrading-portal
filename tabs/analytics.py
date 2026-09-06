# ── Analytics Tab ────────────────
import streamlit as st
from db import get_engine
from datetime import date, timedelta, datetime
from sqlalchemy import text
import pytz
EST = pytz.timezone("America/New_York")

from queries.trades import get_trade_journal
from queries.analytics import (
    get_expectancy, get_time_analysis,
    get_setup_analysis, get_account_breakdown,
    get_weekly_report)
from queries.behavioral import get_behavioral_data


def render(engine, **kwargs):
    # TAB 6 — ANALYTICS
    st.subheader("📊 Analytics")

    # ── Trade Journal ─────────────────────────
    st.markdown("#### 📓 Trade Journal")
    jf1,jf2 = st.columns(2)
    days_filter = jf1.selectbox(
        "Period",
        ["Today","Last 7 days","Last 30 days"],
        key="analytics_period")
    acct_filter = jf2.selectbox(
        "Account",
        ["All","Live","Topstep",
         "Combine","Paper"],
        key="analytics_acct")

    days_map = {"Today":0,
                "Last 7 days":7,
                "Last 30 days":30}
    dback = days_map[days_filter]
    trades_j = get_trade_journal(
        dback if dback > 0 else 30)
    if days_filter == "Today":
        trades_j = [t for t in trades_j
                    if str(t[1]) == str(
                        datetime.now(EST).date())]
    if acct_filter != "All":
        trades_j = [t for t in trades_j
                    if t[15]==acct_filter]

    if trades_j:
        total    = len(trades_j)
        wins     = sum(1 for t in trades_j
                       if float(t[9])>0)
        total_pnl= sum(float(t[9])
                       for t in trades_j)
        wr       = round(wins/total*100,1)
        aj1,aj2,aj3,aj4 = st.columns(4)
        aj1.metric("Trades", total)
        aj2.metric("Win Rate", f"{wr}%")
        aj3.metric("Total P&L",
                   f"${total_pnl:+,.2f}")
        aj4.metric("Wins", wins)

        for t in trades_j[:20]:
            pnl   = float(t[9] or 0)
            em    = int(t[12] or 5)
            color = ("#1B5E20" if pnl>0
                     else "#CC0000"
                     if pnl<0 else "#888")
            icon  = ("✅" if pnl>0
                     else "❌" if pnl<0
                     else "➖")
            st.markdown(
                f"{icon} **{t[3]}** "
                f"{t[4]}×{t[7]}ct"
                f"{t[1]} {str(t[10] or '')[:5]}"
                f" • {t[8] or 'Unknown'}"
                f" • {t[15]}"
                f"<span style='color:{color};"
                f"font-weight:600;"
                f"float:right;'>"
                f"${pnl:+.2f}</span>",
                unsafe_allow_html=True)

    st.divider()
    trades_all = get_trade_journal(90)
    total_trades = len(trades_all)

    # Setup performance — unlocks at 5+ trades
    if total_trades >= 5:
        st.markdown("#### 🎯 Setup Performance")
        setup_data = get_setup_analysis()
        if setup_data:
            import pandas as pd
            df = pd.DataFrame(setup_data,
                columns=["Setup","Trades",
                         "Wins","P&L","Avg"])
            df["Win Rate"] = (
                df["Wins"]/df["Trades"]*100
            ).round(1).astype(str) + "%"
            df["P&L"] = df["P&L"].apply(
                lambda x: f"${x:+,.0f}")
            st.dataframe(
                df[["Setup","Trades",
                    "Win Rate","P&L"]],
                use_container_width=True)
        # Conviction exit outcomes
        st.divider()
        st.markdown("#### 🎯 Conviction Exit Outcomes")
        try:
            with engine.connect() as conn:
                ce = conn.execute(text("""
                    SELECT
                        exit_reason_type,
                        COUNT(*) as total,
                        SUM(CASE WHEN
                            post_exit_result='TP_hit'
                            THEN 1 ELSE 0 END) as tp,
                        SUM(CASE WHEN
                            post_exit_result='SL_hit'
                            THEN 1 ELSE 0 END) as sl,
                        SUM(CASE WHEN
                            post_exit_result='chop'
                            THEN 1 ELSE 0 END) as chop
                    FROM trade_journal
                    WHERE market='US'
            AND user_id=:uid
                    AND exit_type='Conviction Exit'
                    AND post_exit_result IS NOT NULL
                    GROUP BY exit_reason_type
                """), {"uid": st.session_state.get("user_id",1)}).fetchall()
            if ce:
                for r in ce:
                    rtype = r[0] or "Unknown"
                    total = int(r[1])
                    tp    = int(r[2] or 0)
                    sl    = int(r[3] or 0)
                    chop  = int(r[4] or 0)
                    st.markdown(
                        f"**{rtype}** exits: "
                        f"{total} total · "
                        f"TP hit after: {tp} · "
                        f"SL hit after: {sl} · "
                        f"Chop: {chop}")
            else:
                st.info("No conviction exit data yet.")
        except Exception as e:
            st.info("No conviction exit data yet.")

    st.divider()

    # ── Expectancy ────────────────────────────
    st.markdown("#### 📐 Expectancy")
    exp = get_expectancy()
    if exp:
        ew1,ew2,ew3,ew4 = st.columns(4)
        ew1.metric("Win Rate",
                   f"{exp['win_rate']:.1f}%")
        ew2.metric("Avg Win",
                   f"${exp['avg_win']:+.2f}")
        ew3.metric("Avg Loss",
                   f"${exp['avg_loss']:+.2f}")
        ew4.metric("Per Trade",
                   f"${exp['expectancy']:+.2f}")
        color = ("#1B5E20"
                 if exp['expectancy'] > 0
                 else "#CC0000")
        label = ("✅ Positive — system profitable"
                 if exp['expectancy'] > 0
                 else "❌ Negative — review system")
        st.markdown(
            f"<p style='color:{color};"
            f"font-weight:600;'>{label}</p>",
            unsafe_allow_html=True)
        st.caption(
            f"{exp['total']} trades | "
            f"{exp['wins']}W / {exp['losses']}L")

    st.divider()

    # ── Time of Day ───────────────────────────
    st.markdown("#### ⏰ Best Time to Trade")
    st.caption(
        "Based on your historical trades — "
        "win rate by time of day. "
        "Trade more during your best window, "
        "less during your worst.")
    tod = get_time_analysis()
    if tod and len(tod) >= 2:
        tod_wr = [
            (t[0], t[1],
             round(t[2]/t[1]*100,1)
             if t[1] > 0 else 0,
             float(t[3] or 0))
            for t in tod]
        best  = max(tod_wr, key=lambda x: x[2])
        worst = min(tod_wr, key=lambda x: x[2])
        tc1,tc2 = st.columns(2)
        with tc1:
            st.success(
                f"🟢 **Best window**\n\n"
                f"**{best[0]} EST**\n\n"
                f"You win {best[2]:.0f}% of "
                f"trades in this window "
                f"({best[1]} trades so far)")
        with tc2:
            st.error(
                f"🔴 **Avoid this window**\n\n"
                f"**{worst[0]} EST**\n\n"
                f"You win only {worst[2]:.0f}% "
                f"of trades here "
                f"({worst[1]} trades so far)")

        # Show all buckets as a simple table
        st.markdown("**All time windows:**")
        for bucket, trades, wr, avg in tod_wr:
            color = ("#1B5E20" if wr >= 70
                     else "#E65100" if wr >= 50
                     else "#CC0000")
            bar = "█" * int(wr/10) + \
                  "░" * (10-int(wr/10))
            st.markdown(
                f"<div style='display:flex;"
                f"align-items:center;"
                f"gap:12px;padding:4px 0;"
                f"border-bottom:1px solid #eee;'>"
                f"<span style='width:110px;"
                f"font-size:12px;color:#666;'>"
                f"{bucket}</span>"
                f"<span style='font-family:monospace;"
                f"color:{color};font-size:12px;'>"
                f"{bar}</span>"
                f"<span style='color:{color};"
                f"font-weight:600;"
                f"font-size:12px;width:40px;'>"
                f"{wr:.0f}%</span>"
                f"<span style='color:#888;"
                f"font-size:11px;'>"
                f"{trades} trades · "
                f"avg ${avg:+.0f}</span>"
                f"</div>",
                unsafe_allow_html=True)
    else:
        st.info(
            "Not enough data yet. "
            "Log trades at different times "
            "to see your best trading window.")

    st.divider()

    # ── Account Breakdown ─────────────────────
    st.markdown("#### 🏦 Account Breakdown")
    acct_data = get_account_breakdown()
    if acct_data:
        try:
            import pandas as pd
            acct_df = pd.DataFrame(acct_data,
                columns=["Account","Behavior",
                         "Count","Cost"])
            accounts = acct_df["Account"].unique()
            acct_cols = st.columns(
                min(len(accounts),3))
            for i,acct in enumerate(accounts):
                with acct_cols[i%3]:
                    st.markdown(f"**{acct}**")
                    rows = acct_df[
                        acct_df["Account"]==acct]
                    for _,row in rows.iterrows():
                        cost = float(
                            row["Cost"] or 0)
                        color = (
                            "#CC0000" if cost<-50
                            else "#FF8C00"
                            if cost<0 else "#888")
                        st.markdown(
                            f"<div style='"
                            f"font-size:12px;"
                            f"padding:4px 0;'>"
                            f"<span style='"
                            f"color:{color};'>"
                            f"{row['Behavior']}"
                            f"</span>"
                            f"<span style='"
                            f"color:#888;"
                            f"margin-left:8px;'>"
                            f"{int(row['Count'])}x"
                            f" ${cost:+.0f}"
                            f"</span></div>",
                            unsafe_allow_html=True)
        except Exception:
            st.info("No account breakdown yet.")
    else:
        st.info("No account data yet.")

    st.divider()

    # ── Money Leaks ───────────────────────────
    st.markdown("#### 💸 Money Leaks")
    if events_b:
        any_cost = False
        for e in events_b:
            cost  = float(e[2] or 0)
            count = int(e[1])
            if cost < 0:
                any_cost = True
                st.markdown(
                    f"**{e[0]}** — "
                    f"{count}x · "
                    f"${abs(cost):,.0f} lost")
        if not any_cost:
            st.success(
                "No costly patterns detected.")
    else:
        st.info("No behavioral data yet.")

    st.divider()

    # ── Weekly Report ─────────────────────────
    st.markdown("#### 📅 Weekly Report")
    try:
        week_trades = get_trade_journal(7)
        if week_trades:
            wt = len(week_trades)
            ww = sum(1 for t in week_trades
                     if float(t[9])>0)
            wp = sum(float(t[9])
                     for t in week_trades)
            wwr = round(ww/wt*100,1) \
                if wt > 0 else 0
            wm1,wm2,wm3 = st.columns(3)
            wm1.metric("Trades", wt)
            wm2.metric("Win Rate", f"{wwr}%")
            wm3.metric("P&L",
                       f"${wp:+,.2f}")
        else:
            st.info("No trades this week.")
    except Exception as e:
        st.info("No weekly data yet.")

