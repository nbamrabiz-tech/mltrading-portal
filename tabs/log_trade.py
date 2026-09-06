# ── Log Trade Tab ─────────────────
import streamlit as st
from datetime import date, timedelta, datetime
from sqlalchemy import text
import pytz
EST = pytz.timezone("America/New_York")
from db import get_engine
from queries.trades import get_latest_report
from queries.behavioral import (
    check_reentry_timing, detect_all_behaviors,
    get_behavioral_data, calculate_daily_score)
from config import (
    EMOTION_OPTIONS, EXIT_EMOTION_OPTIONS,
    TICKER_MULTIPLIERS)


def render(engine, today, now_est,
           check_exists=False,
           check_data=None,
           trading_allowed=True,
           **kwargs):
    # Get today's behavioral data
    _, _, today_b, today_t = \
        get_behavioral_data()
    today_losses  = int(today_t[4] or 0) \
        if today_t else 0
    total_today   = int(today_t[0] or 0) \
        if today_t else 0
    hi_behaviors  = sum(
        1 for b in today_b
        if b[1] == "High") \
        if today_b else 0

    # Get latest report
    report = get_latest_report()

    # Gate passed flag
    gate_passed = (
        check_exists and trading_allowed)
    # Trade log form
    st.subheader("📝 Log a Trade")

    # ── Open trades section ───────────────────
    try:
        with engine.connect() as conn:
            open_trades = conn.execute(
                text("""
                SELECT id, trade_date,
                       ticker, direction,
                       entry_price,
                       stop_price,
                       planned_target,
                       size_contracts,
                       entry_time_actual,
                       account_type,
                       setup_type,
                       emotional_state
                FROM trade_journal
                WHERE market='US'
        AND user_id=:uid
                AND trade_status='open'
                AND trade_date=:td
                ORDER BY created_at ASC
            """), {
                 "td": str(date.today()),
            "uid": st.session_state.get("user_id",1)
    }).fetchall()
    except:
        open_trades = []

    if open_trades:
        st.markdown(
            f"<div style='background:#FFF8E1;"
            f"border:0.5px solid #BA7517;"
            f"border-radius:8px;"
            f"padding:12px 16px;"
            f"margin-bottom:12px;'>"
            f"<p style='color:#854F0B;"
            f"font-size:13px;font-weight:500;"
            f"margin:0 0 8px;'>"
            f"⚡ {len(open_trades)} open "
            f"trade(s) — log exit below"
            f"</p></div>",
            unsafe_allow_html=True
        )

        for ot in open_trades:
            tid    = ot[0]
            tkr    = ot[2]
            dirn   = ot[3]
            entry  = float(ot[4])
            stop   = float(ot[5]) \
                     if ot[5] else 0
            target = float(ot[6]) \
                     if ot[6] else 0
            qty    = int(ot[7] or 1)
            etime  = ot[8] or ""
            acct   = ot[9] or ""
            setup  = ot[10] or ""

            st.markdown(
                f"<div style='background:#F8F9FA;"
                f"border:0.5px solid #BA7517;"
                f"border-radius:8px;"
                f"padding:10px 14px;"
                f"margin-bottom:8px;'>"
                f"<b>{tkr} {dirn} ×{qty} "
                f"— {acct}</b> "
                f"<span style='color:#666;"
                f"font-size:12px;'>"
                f"Entry:{entry:.2f} "
                f"Stop:{stop:.2f} "
                f"Target:{target:.2f} "
                f"at {etime}"
                f"</span></div>",
                unsafe_allow_html=True
            )

            with st.form(
                f"exit_form_{tid}",
                clear_on_submit=True
            ):
                st.markdown(
                    f"**Exit: {tkr} {dirn}**")
                ec1,ec2 = st.columns(2)
                exit_px = ec1.number_input(
                    "Exit price",
                    value=entry,
                    step=0.25,
                    format="%.2f",
                    key=f"lt_exp_{tid}")
                exit_tm = ec2.text_input(
                    "Exit time (HH:MM)",
                    placeholder="11:59",
                    key=f"et_{tid}")

                exit_type = st.selectbox(
                    "Exit type",
                    ["Stop Loss",
                     "Target Hit",
                     "Conviction Exit",
                     "Breakeven Stop",
                     "End of Day"],
                    key=f"xt_{tid}")

                # Always show reason fields
                # Validated on submit
                reason_type = st.radio(
                    "Reason type "
                    "(if Conviction Exit)",
                    ["Technical",
                     "Fundamental",
                     "Emotional"],
                    horizontal=True,
                    key=f"rt_{tid}")

                exit_reason = st.text_input(
                    "Reason / notes",
                    placeholder=
                    "Conviction: No follow-"
                    "through 20min / "
                    "Breakeven: Moved SL "
                    "at 1:1 RR",
                    key=f"rd_{tid}")

                exit_reason_type = ""

                if exit_type == \
                        "Conviction Exit":
                    exit_reason_type = \
                        reason_type
                    # Auto-detect emotional
                    emotional_words = [
                        "scared","nervous",
                        "panic","uncertain",
                        "feeling","couldn't",
                        "bad feeling","fear",
                        "anxiety","stress",
                        "worried","overwhelmed"
                    ]
                    if exit_reason and any(
                        w in exit_reason.lower()
                        for w in emotional_words
                    ):
                        st.warning(
                            "⚠️ Emotional "
                            "language detected "
                            "— flagged as "
                            "Emotional exit")
                        exit_reason_type = \
                            "Emotional"
                elif exit_type == \
                        "Breakeven Stop":
                    exit_reason_type = \
                        "Breakeven"
                    st.info(
                        "✅ Moving SL to "
                        "breakeven = "
                        "discipline ✓")

                exit_emotion_opts = {
                    "😌 Calm":         1,
                    "😊 Satisfied":    2,
                    "😤 Eager":        4,
                    "😬 Restless":     5,
                    "😰 Anxious":      7,
                    "😠 Frustrated":   8,
                    "🤑 Greedy":       7,
                    "😱 FOMO":         6,
                    "😑 Relieved":     3,
                }
                exit_emotion_lbl = st.selectbox(
                    "How did you feel at exit?",
                    list(exit_emotion_opts.keys()),
                    key=f"lt_ee_{tid}")
                exit_emotion = exit_emotion_opts[
                    exit_emotion_lbl]

                # Plan + System on exit
                ep1,ep2 = st.columns(2)
                exit_plan = ep1.radio(
                    "Followed plan?",
                    ["Yes","No"],
                    horizontal=True,
                    key=f"lt_eplan_{tid}")
                exit_checked = ep2.radio(
                    "Checked system?",
                    ["Yes","No"],
                    horizontal=True,
                    key=f"lt_ec_{tid}")
                exit_mistake = st.text_input(
                    "Mistake? (blank if none)",
                    key=f"lt_em_{tid}")

                exit_submitted = \
                    st.form_submit_button(
                    "💾 Log Exit",
                    use_container_width=True)

                if exit_submitted and \
                        exit_px > 0:
                    # Validate conviction
                    # exit has reason
                    if exit_type == \
                            "Conviction Exit" \
                            and not exit_reason:
                        st.error(
                            "⚠️ Please enter "
                            "a reason for "
                            "conviction exit "
                            "before submitting.")
                        st.stop()
                    if exit_type == \
                            "Breakeven Stop" \
                            and not exit_reason:
                        st.error(
                            "⚠️ Please explain "
                            "why you moved SL "
                            "before submitting.")
                        st.stop()
                    try:
                        pv_map = {
                            "NQ":20,"ES":50,
                            "MNQ":2,"MES":5,
                            "SPY":1,"QQQ":1}
                        pv = pv_map.get(
                            tkr, 1)

                        if dirn == "Long":
                            pnl = (
                                exit_px-entry
                            )*pv*qty
                        else:
                            pnl = (
                                entry-exit_px
                            )*pv*qty

                        risk_pts = abs(
                            entry-stop)
                        risk_dollar = \
                            risk_pts*pv*qty
                        pnl_r = round(
                            pnl/risk_dollar,
                            2) if \
                            risk_dollar > 0 \
                            else 0

                        hold_mins = None
                        if etime and exit_tm:
                            try:
                                fmt = "%H:%M"
                                e = datetime\
                                    .strptime(
                                    etime,fmt)
                                x = datetime\
                                    .strptime(
                                    exit_tm,fmt)
                                hold_mins = int(
                                    (x-e)
                                    .total_seconds()
                                    /60)
                            except:
                                pass

                        with engine.connect() \
                                as conn:
                            conn.execute(
                                text("""
                                UPDATE
                                trade_journal
                                SET
                                  exit_price=:ep,
                                  exit_time=:et,
                                  pnl=:pnl,
                                  pnl_r=:pnl_r,
                                  trade_status=
                                    'closed',
                                  exit_type=:xt,
                                  exit_reason=:xr,
                                  exit_reason_type
                                    =:xrt,
                                  emotional_state
                                    =:em,
                                  followed_plan=:fp,
                                  checked_system=:cs,
                                  mistake=:mk
                                WHERE id=:tid
                            """), {
                                "ep":  exit_px,
                                "et":  exit_tm,
                                "pnl": round(
                                    pnl,2),
                                "pnl_r":pnl_r,
                                "xt":  exit_type,
                                "xr":  exit_reason,
                                "xrt": exit_reason_type,
                                "em":  exit_emotion,
                                "fp":  exit_plan=="Yes",
                                "cs":  exit_checked=="Yes",
                                "mk":  exit_mistake or None,
                                "tid": tid
                            })
                            conn.commit()

                        # Flag emotional exit
                        if exit_reason_type \
                                == "Emotional":
                            with engine.connect()\
                                    as conn:
                                conn.execute(
                                    text("""
                                    INSERT INTO
                                    behavioral_events(
                                      market,
                                      event_date,
                                      trade_id,
                                      behavior_type,
                                      severity,
                                      description,
                                      financial_cost)
                                    VALUES(
                                      'US',:td,
                                      :tid,
                                      'Emotional Exit',
                                      'Medium',
                                      :desc,0)
                                """), {
                                    "td": str(
                                        date.today()),
                                    "tid": tid,
                                    "desc":
                                        f"Emotional "
                                        f"conviction "
                                        f"exit: "
                                        f"{exit_reason}"
                                })
                                conn.commit()

                        outcome = (
                            "Win" if pnl > 0
                            else "Loss"
                            if pnl < 0
                            else "Scratch")

                        color = (
                            "#0066CC"
                            if pnl > 0
                            else "#CC0000"
                            if pnl < 0
                            else "#888")

                        hold_txt = (
                            f" · {hold_mins}min"
                            if hold_mins
                            else "")

                        exit_lbl = ""
                        if exit_type == \
                                "Conviction Exit":
                            exit_lbl = (
                                f" · {exit_reason_type}"
                                f" exit")

                        st.markdown(
                            f"<div style='"
                            f"background:{color}15;"
                            f"padding:10px;"
                            f"border-radius:8px;"
                            f"border-left:4px "
                            f"solid {color};'>"
                            f"<b style='color:"
                            f"{color};'>"
                            f"{outcome} — "
                            f"${pnl:+.2f} "
                            f"({pnl_r:+.2f}R)"
                            f"{hold_txt}"
                            f"{exit_lbl}"
                            f"</b></div>",
                            unsafe_allow_html
                            =True
                        )

                        # Recalc score
                        calculate_daily_score(
                            date.today())
                        st.rerun()

                    except Exception as e:
                        st.error(
                            f"Exit failed: {e}")

    st.divider()
    st.markdown("**Log new entry:**")

    # Pre-trade gate
    reentry      = check_reentry_timing(
        date.today())
    # Show override warning if active
    override_active = check_exists and \
        not trading_allowed and \
        bool(check_data[4] if check_data
             else False)

    if override_active:
        override_reason = check_data[5] \
            if check_data and \
            len(check_data) > 5 \
            else ""
        st.markdown(
            f"<div style='background:#FFF3CD;"
            f"border:0.5px solid #BA7517;"
            f"border-radius:8px;"
            f"padding:12px 16px;"
            f"margin-bottom:8px;'>"
            f"<p style='color:#854F0B;"
            f"font-size:14px;font-weight:600;"
            f"margin:0 0 4px;'>"
            f"⚠️ Override active — "
            f"restricted trading today</p>"
            f"<p style='color:#854F0B;"
            f"font-size:12px;margin:0;'>"
            f"Reason: {override_reason}<br>"
            f"✅ Allowed: Topstep / Paper<br>"
            f"🔴 Locked: IBKR Live</p>"
            f"</div>",
            unsafe_allow_html=True
        )

    gate_blocked = False

    # Pre-session check gate
    if check_exists and not trading_allowed:
        override_done = bool(check_data[4]) \
            if check_data else False
        if not override_done:
            st.error(
                "🔴 Pre-session check: "
                "not recommended to trade today. "
                "See the alert above.")
            gate_blocked = True
    gate_warnings= []

    if today_losses >= 2:
        st.error(
            "⛔ 2 losses today — done. "
            "Close platform now.")
        gate_blocked = True

    if reentry and reentry["blocked"]:
        if reentry.get("mandatory"):
            # MANDATORY — no override
            remaining = reentry["remaining"]
            unlock    = reentry["unlock_time"]
            pnl       = reentry["loss_pnl"]
            ticker    = reentry["ticker"]
            st.markdown(
                f"<div style='"
                f"background:#1A0000;"
                f"border:2px solid #CC0000;"
                f"border-radius:10px;"
                f"padding:16px 20px;"
                f"margin-bottom:12px;'>"
                f"<div style='color:#FF4444;"
                f"font-size:18px;"
                f"font-weight:800;"
                f"margin-bottom:8px;'>"
                f"⏸️ MANDATORY 30-MIN BREAK"
                f"</div>"
                f"<div style='color:#FFE0E0;"
                f"font-size:14px;"
                f"line-height:1.8;'>"
                f"You just took a loss of "
                f"<b>${abs(pnl):.2f}</b> "
                f"on {ticker}.<br>"
                f"Next trade allowed at: "
                f"<b>{unlock} EST</b><br>"
                f"Time remaining: "
                f"<b>{remaining:.0f} minutes</b>"
                f"<br><br>"
                f"<span style='color:#FF8888;'>"
                f"Step away from the platform.<br>"
                f"No override. No exceptions.</span>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True)
            gate_blocked = True
        else:
            st.warning(reentry["message"])
            gate_blocked = True

    up_pct_g = 33
    conf_g   = "No Edge"
    if report:
        up_pct_g = report.get(
            "matrix_score",33) or 33
        conf_g   = report.get(
            "confidence","No Edge") or "No Edge"

    if "No Edge" in conf_g and up_pct_g < 35:
        st.warning(
            "⚠️ No Edge today — "
            "consider sitting out")

    if total_today >= 3:
        st.warning(
            f"⚠️ Trade #{total_today+1} "
            f"today — max 3 recommended")

    if not gate_blocked:
        st.success("✅ Gate clear — proceed")

    # ── No Edge override ──────────────────
    report_now = get_latest_report()
    is_no_edge = False
    if report_now:
        edge_now = report_now.get(
            "confidence",
            report_now.get("edge",""))
        is_no_edge = "No Edge" in str(
            edge_now)

    no_edge_override = False
    if is_no_edge:
        st.warning(
            "⚪ No Edge today — "
            "system recommends sitting out.")
        with st.expander(
            "I see a setup — override "
            "No Edge signal",
            expanded=False):

            st.markdown(
                "No Edge day — price action decides.  \n"
                "Look at the chart first, then pick "
                "the setup that matches what you see.")

            setup_type = st.radio(
                "What does price action show?",
                ["↔️ Range / Consolidation",
                 "📈 Trending Up",
                 "📉 Trending Down"],
                index=0,
                key="no_edge_setup_type",
                horizontal=True)

            if "Range" in setup_type:
                st.caption(
                    "Range setup — need 4/5. "
                    "Max 50% size.")
                conf_items = [
                    "Consolidation identified "
                    "(price in tight range)",
                    "Breakout with volume increase",
                    "Volume delta confirms direction",
                    "FVG created on breakout",
                    "Price pulled back to FVG",
                ]
                threshold = 4
                label_count = "5"
            elif "Up" in setup_type:
                st.caption(
                    "Trend Long setup — need 3/4. "
                    "Max 50% size.")
                conf_items = [
                    "Higher High + Higher Low "
                    "established",
                    "Pullback to EMA-21, "
                    "EMA-34 or VWAP",
                    "Bullish confirmation candle "
                    "at the level",
                    "Direction: Long only",
                ]
                threshold = 3
                label_count = "4"
            else:
                st.caption(
                    "Trend Short setup — need 3/4. "
                    "Max 50% size.")
                conf_items = [
                    "Lower High + Lower Low "
                    "established",
                    "Pullback to EMA-21, "
                    "EMA-34 or VWAP",
                    "Bearish confirmation candle "
                    "at the level",
                    "Direction: Short only",
                ]
                threshold = 3
                label_count = "4"

            checked = []
            for i, label in enumerate(conf_items):
                if st.checkbox(
                        label,
                        key=f"conf_{i}"):
                    checked.append(label)

            conf_score = len(checked)
            if conf_score >= threshold:
                st.success(
                    f"✅ {conf_score}/"
                    f"{label_count} confluences — "
                    f"override allowed. "
                    f"Use 50% size.")
                no_edge_override = True
            elif conf_score > 0:
                st.warning(
                    f"⚠️ {conf_score}/"
                    f"{label_count} confluences — "
                    f"need {threshold}+ to override.")
            else:
                st.info(
                    f"Check at least {threshold} "
                    f"confluences to override.")

