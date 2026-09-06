# ── Log Trade Tab ─────────────────
import streamlit as st
from datetime import date, timedelta, datetime
from sqlalchemy import text
import pytz
EST = pytz.timezone("America/New_York")
from db import get_engine
from queries.trades import get_latest_report
from config import EMOTION_OPTIONS, EXIT_EMOTION_OPTIONS


def render(engine, today, now_est, **kwargs):
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
                    key=f"ep_{tid}")
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
                    key=f"ee_{tid}")
                exit_emotion = exit_emotion_opts[
                    exit_emotion_lbl]

                # Plan + System on exit
                ep1,ep2 = st.columns(2)
                exit_plan = ep1.radio(
                    "Followed plan?",
                    ["Yes","No"],
                    horizontal=True,
                    key=f"ep_{tid}")
                exit_checked = ep2.radio(
                    "Checked system?",
                    ["Yes","No"],
                    horizontal=True,
                    key=f"ec_{tid}")
                exit_mistake = st.text_input(
                    "Mistake? (blank if none)",
                    key=f"em_{tid}")

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
            st.caption(
                "Only override if you have "
                "strong confluence. "
                "Max 50% normal size. "
                "Tracked separately.")
            conf_checks = {
                "Key level holding "
                "(support/resistance)": False,
                "Breakout confirmed "
                "with volume": False,
                "EMA stack aligned": False,
                "FVG present": False,
                "PDH/PDL confluence": False,
            }
            checked = []
            for label in conf_checks:
                if st.checkbox(
                        label,
                        key=f"conf_{label}"):
                    checked.append(label)

            conf_score = len(checked)
            if conf_score >= 3:
                st.success(
                    f"✅ {conf_score}/5 "
                    f"confluences — "
                    f"override allowed. "
                    f"Use 50% size.")
                no_edge_override = True
            elif conf_score > 0:
                st.warning(
                    f"⚠️ {conf_score}/5 "
                    f"confluences — "
                    f"need 3+ to override.")
            else:
                st.info(
                    "Check at least 3 "
                    "confluences to override.")

    st.caption("45 seconds — log every trade")

    with st.form("trade_log_form",
                 clear_on_submit=True):
        # Row 1 — Date + Ticker + Account
        r1c1,r1c2,r1c3 = st.columns(3)
        t_date   = r1c1.date_input(
            "Trade Date",value=date.today())
        t_ticker = r1c2.selectbox("Ticker",
            ["NQ","ES","SPY","QQQ",
             "MNQ","MES"])
        # Lock IBKR if override active
        if override_active:
            acct_options = [
                "Topstep","Combine","Paper"]
            r1c3.warning("🔴 IBKR locked today")
        else:
            acct_options = [
                "Live","Topstep",
                "Combine","Paper"]
        t_acct = r1c3.selectbox(
            "Account", acct_options)

        # Row 2 — Direction + Setup + Qty
        r2c1,r2c2,r2c3 = st.columns(3)
        t_dir   = r2c1.radio("Direction",
            ["Long","Short"],horizontal=True)
        t_setup = r2c2.selectbox("Setup",
            ["Range FVG — Long",
             "Range FVG — Short",
             "Trend Pullback — Long",
             "Trend Pullback — Short",
             "Momentum","Reversal",
             "Breakout","Range","Event",
             "Mean Reversion","FOMO",
             "Revenge","Other"])
        t_qty   = r2c3.number_input(
            "Qty (shares/contracts)",
            min_value=1,max_value=10000,
            value=1,step=1)

        # Row 3 — Prices
        r3c1,r3c2,r3c3 = st.columns(3)
        t_entry  = r3c1.number_input(
            "Entry",value=0.0,
            step=0.25,format="%.2f")
        t_exit   = r3c2.number_input(
            "Exit",value=0.0,
            step=0.25,format="%.2f")
        t_stop   = r3c3.number_input(
            "Stop",value=0.0,
            step=0.25,format="%.2f")

        # Target
        t_target = st.number_input(
            "Target (for R:R calculation)",
            value=0.0,step=0.25,format="%.2f")

        # Row 4 — Entry + Exit times
        r4c1,r4c2 = st.columns(2)
        t_entry_time = r4c1.text_input(
            "Entry time (HH:MM)",
            placeholder="09:45")
        t_exit_time  = r4c2.text_input(
            "Exit time (HH:MM)",
            placeholder="10:15")

        # Emotion picker
        emotion_options = {
            "😌 Calm/Focused":    1,
            "😊 Confident":       2,
            "😤 Eager/Excited":   4,
            "😬 Itchy/Restless":  5,
            "😰 Anxious/Nervous": 7,
            "😠 Angry/Frustrated":8,
            "🤑 Greedy":          7,
            "😱 FOMO":            6,
            "😑 Bored":           4,
        }
        emotion_label = st.selectbox(
            "How are you feeling?",
            list(emotion_options.keys()),
            key="emotion_picker")
        t_emotion = emotion_options[
            emotion_label]
        st.caption(
            f"Intensity score: "
            f"{t_emotion}/10")

        # Plan + System defaults for entry
        # Will be confirmed on exit
        t_plan    = "Yes"
        t_checked = "Yes"
        t_mistake = ""

        # Check if mandatory break active
        on_break = (
            reentry is not None and
            reentry.get("mandatory",
                        False))

        submitted = st.form_submit_button(
            "💾 Log Entry",
            use_container_width=True,
            disabled=on_break)

        if submitted and t_entry>0:
            pv_map = {
                "NQ":20,"ES":50,"MNQ":2,
                "MES":5,"SPY":1,"QQQ":1}
            pv = pv_map.get(t_ticker,1)

            # P&L with quantity
            if t_exit > 0:
                if t_dir=="Long":
                    pnl=(t_exit-t_entry)\
                        *pv*t_qty
                else:
                    pnl=(t_entry-t_exit)\
                        *pv*t_qty
                outcome=("Win" if pnl>0
                         else "Loss"
                         if pnl<0
                         else "Scratch")
            else:
                pnl     = 0
                outcome = "Open"

            risk_pts    = abs(t_entry-t_stop)
            risk_dollar = risk_pts*pv*t_qty
            pnl_r = round(
                pnl/risk_dollar,2
            ) if risk_dollar>0 \
              and t_exit>0 else 0

            # Planned R:R
            planned_rr=0; rr_gap=0
            if t_target>0 and risk_pts>0:
                reward = (t_target-t_entry
                          if t_dir=="Long"
                          else t_entry-t_target)
                planned_rr = round(
                    reward/risk_pts,2
                ) if risk_pts>0 else 0
                rr_gap = round(
                    planned_rr-abs(pnl_r),2)

            # ── Breakeven reminder ────────
            if t_exit == 0 and \
                    risk_pts > 0 and \
                    planned_rr >= 0.8:
                be_price = (
                    t_entry + risk_pts
                    if t_dir=="Long"
                    else t_entry - risk_pts)
                st.info(
                    f"⚡ At 0.8:1 RR → "
                    f"move SL to breakeven "
                    f"({be_price:.2f}). "
                    f"Cannot lose after that.")

            # ── Strategy flag ─────────────
            report = get_latest_report()
            if report:
                edge = report.get(
                    "edge","")
                wrong = False
                msg   = ""
                if "Range" in edge and \
                   "Trend Pullback" in \
                        t_setup:
                    wrong = True
                    msg   = (
                        "⚠️ Range day — "
                        "Range FVG works "
                        "better than "
                        "Trend Pullback")
                elif "Long" in edge and \
                     "Short" in t_setup:
                    wrong = True
                    msg   = (
                        "⚠️ Long Bias day "
                        "— Short setup "
                        "against the edge")
                elif "Short" in edge and \
                     "Long" in t_setup and \
                     "FVG" in t_setup:
                    wrong = True
                    msg   = (
                        "⚠️ Short Bias day "
                        "— Long setup "
                        "against the edge")
                if wrong:
                    st.warning(msg)

            # Hold time
            hold_mins=None
            if t_entry_time and t_exit_time:
                try:
                    fmt="%H:%M"
                    e=datetime.strptime(
                        t_entry_time,fmt)
                    x=datetime.strptime(
                        t_exit_time,fmt)
                    hold_mins=int(
                        (x-e).total_seconds()/60)
                except:
                    pass

            gate_passed=(
                t_plan=="Yes" and
                t_checked=="Yes" and
                not gate_blocked)

            try:
                with engine.connect() as conn:
                    rpt=conn.execute(text("""
                        SELECT matrix_score,bias
                        FROM intelligence_reports
                        WHERE market='US'
                        AND report_date=:td
                        ORDER BY created_at
                        DESC LIMIT 1
                    """),{
                        "td":str(t_date)
                    }).fetchone()

                    ms     = int(rpt[0]) if rpt else 33
                    bias_t = rpt[1] if rpt else "Unknown"

                    res=conn.execute(text("""
                        INSERT INTO trade_journal(
                            market,trade_date,
                            trade_time,
                            entry_time_actual,
                            exit_time,
                            ticker,account_type,
                            direction,setup_type,
                            entry_price,exit_price,
                            stop_price,
                            planned_target,
                            size_contracts,
                            pnl,pnl_r,
                            matrix_score,bias_today,
                            emotional_state,
                            followed_plan,mistake,
                            checked_system,
                            pre_trade_gate,
                            trade_status,
                            user_id)
                        VALUES(
                            'US',:td,:tt,
                            :entry_t,:exit_t,
                            :ticker,:acct,
                            :dir,:setup,
                            :entry,:exit,:stop,
                            :target,:qty,
                            :pnl,:pnl_r,
                            :ms,:bias,
                            :emotion,:plan,
                            :mistake,:checked,
                            :gate,:status,
                            :uid)
                        RETURNING id,created_at
                    """),{
                        "td":     str(t_date),
                        "tt":     datetime.now(
                            EST).strftime("%H:%M"),
                        "entry_t":t_entry_time or None,
                        "exit_t": t_exit_time  or None,
                        "ticker": t_ticker,
                        "acct":   t_acct,
                        "dir":    t_dir,
                        "setup":  (
                            f"[No Edge Override] "
                            f"{t_setup}"
                            if no_edge_override
                            else t_setup),
                        "entry":  t_entry,
                        "exit":   t_exit,
                        "stop":   t_stop,
                        "target": t_target
                                  if t_target>0
                                  else None,
                        "qty":    t_qty,
                        "pnl":    round(pnl,2),
                        "pnl_r":  pnl_r,
                        "ms":     ms,
                        "bias":   bias_t,
                        "emotion":t_emotion,
                        "plan":   t_plan=="Yes",
                        "mistake":t_mistake,
                        "checked":t_checked=="Yes",
                        "gate":   gate_passed,
                        "status": "open"
                                  if t_exit == 0
                                  else "closed",
                        "uid": st.session_state.get(
                            "user_id", 1)
                    })
                    row=res.fetchone()
                    trade_id  =row[0]
                    created_at=row[1]
                    conn.commit()

                # Auto behavioral detection
                # and daily score update
                calculate_daily_score(t_date)
                behaviors=detect_all_behaviors(
                    trade_id=trade_id,
                    trade_date=t_date,
                    pnl=pnl,
                    emotion=t_emotion,
                    followed_plan=t_plan=="Yes",
                    checked_system=t_checked=="Yes",
                    gate_passed=gate_passed,
                    entry_price=t_entry,
                    stop_price=t_stop,
                    exit_price=t_exit,
                    direction=t_dir,
                    created_at=created_at
                )

                # Result display
                color=("#0066CC" if pnl>0
                       else "#CC0000")
                qty_label=("shares"
                           if t_ticker in
                           ["SPY","QQQ"]
                           else "contracts")
                hold_txt=(
                    f"<br>⏱️ Hold: {hold_mins}min"
                    if hold_mins is not None
                    else "")
                rr_txt=""
                if planned_rr>0:
                    rr_txt=(
                        f"<br>📐 Planned R:R: "
                        f"1:{planned_rr:.2f} | "
                        f"Actual: "
                        f"1:{abs(pnl_r):.2f}")
                    if rr_gap>0.3:
                        rr_txt+=(
                            f" | ⚠️ "
                            f"{rr_gap:.2f}R "
                            f"left on table")

                st.markdown(
                    f"<div style='background:"
                    f"{color}15;padding:12px;"
                    f"border-radius:8px;"
                    f"border-left:4px solid "
                    f"{color};'>"
                    f"<b style='color:{color};"
                    f"font-size:16px;'>"
                    f"{outcome} — ${pnl:+.2f} "
                    f"({pnl_r:+.2f}R) × "
                    f"{t_qty} {qty_label}"
                    f"</b>"
                    f"{rr_txt}{hold_txt}"
                    f"</div>",
                    unsafe_allow_html=True
                )

                # Behavioral alerts
                for b in behaviors:
                    bc=("#CC0000"
                        if b["severity"]=="High"
                        else "#FF8C00")
                    em=("🔴"
                        if b["severity"]=="High"
                        else "🟡")
                    st.markdown(
                        f"<div style='background:"
                        f"{bc}15;padding:8px 12px;"
                        f"border-radius:6px;"
                        f"border-left:3px solid "
                        f"{bc};margin-top:6px;'>"
                        f"{em} <b>{b['type']}</b>"
                        f" ({b['severity']})<br>"
                        f"<span style='color:#555;"
                        f"font-size:12px;'>"
                        f"{b['desc']}"
                        f"</span></div>",
                        unsafe_allow_html=True
                    )

                st.rerun()

            except Exception as e:
                st.error(f"Save failed: {e}")

    # Today's alerts
    if today_b:
        st.divider()
        st.subheader("⚠️ Today's Alerts")
    for b in today_b:
        color=("#CC0000" if b[1]=="High"
               else "#FF8C00")
        st.markdown(
            f"<div style='background:{color}15;"
            f"padding:10px 14px;"
            f"border-radius:6px;"
            f"border-left:3px solid {color};"
            f"margin-bottom:6px;'>"
            f"<b style='color:{color};'>"
            f"{b[0]}</b>"
            f"<span style='color:#666;"
            f"font-size:12px;margin-left:8px;'>"
            f"{b[1]} — {int(b[3])}x today"
            f"</span><br>"
            f"<span style='color:#888;"
            f"font-size:11px;'>"
            f"{b[2][:80] if b[2] else ''}"
            f"</span></div>",
            unsafe_allow_html=True
        )


    st.divider()
    st.caption(
    "📊 Full journal → Analytics  |  "
    "🎯 Forward test → Forward Test tab")


