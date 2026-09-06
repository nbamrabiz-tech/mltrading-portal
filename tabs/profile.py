# ── My Profile Tab ───────────────
import streamlit as st
from datetime import date, timedelta, datetime
from sqlalchemy import text
import pytz
EST = pytz.timezone("America/New_York")

from queries.trades import (
    get_latest_report, get_trade_journal)
from queries.behavioral import (
    get_behavioral_data, get_streaks,
    calculate_daily_score, check_reentry_timing,
    detect_all_behaviors)
from queries.analytics import (
    get_expectancy, get_time_analysis,
    get_setup_analysis, get_weekly_report)
from utils.coaching import (
    generate_coaching_brief,
    generate_signal_summary)
from utils.formatting import card, score_color
from config import BEHAVIOR_PLAIN


def render(engine, today, now_est):
    report   = get_latest_report()
    _uid_debug = st.session_state.get(
        "user_id", 1)
    events_b,scores_b,today_b,today_t = \
        get_behavioral_data(
            uid=_uid_debug)

    # ── Pre-session check-in ──────────────────
    today_date      = datetime.now(EST).date()
    check_exists    = False
    trading_allowed = True
    check_data      = None
    sleep_val       = 3
    stress_val      = 3
    sleep_label     = "Good"

    try:
        with engine.connect() as conn:
            check_data = conn.execute(text("""
                SELECT sleep_quality,
                       stress_level,
                       substances,
                       trading_allowed,
                       override,
                       override_reason
                FROM pre_session_checks
                WHERE market='US'
                AND check_date=:td
            """), {
                "td": str(today_date)
            }).fetchone()
        if check_data:
            check_exists    = True
            trading_allowed = bool(check_data[3])
            sleep_val       = int(check_data[0])
            stress_val      = int(check_data[1])
            sleep_label     = {
                1:"Poor",2:"OK",3:"Good"
            }.get(sleep_val,"Good")
    except Exception as e:
        pass

    if not check_exists:
        st.markdown(
            "<div style='background:var(--surface-2);"
            "border:0.5px solid var(--border);"
            "border-radius:12px;padding:20px;"
            "margin-bottom:16px;'>"
            "<p style='font-size:13px;font-weight:500;"
            "margin:0 0 4px;'>Good morning — "
            "quick check before you start</p>"
            "<p style='font-size:12px;"
            "color:var(--text-secondary);margin:0 0 16px;'>"
            "Takes 10 seconds. Helps protect your capital."
            "</p></div>",
            unsafe_allow_html=True
        )

        with st.form("pre_session_form"):
            sleep_q = st.select_slider(
                "How did you sleep last night?",
                options=["Poor","OK","Good"],
                value="Good"
            )
            stress = st.slider(
                "Stress/anxiety level right now",
                min_value=1, max_value=10,
                value=3,
                help="1 = completely calm, 10 = very stressed"
            )
            substances = st.checkbox(
                "Alcohol or substances last night"
            )

            submitted = st.form_submit_button(
                "Start my session →",
                use_container_width=True
            )

            if submitted:
                sleep_map = {"Poor":1,"OK":2,"Good":3}
                sleep_val = sleep_map[sleep_q]

                # Determine if trading is recommended
                allowed = True
                reasons = []

                if sleep_val == 1:
                    allowed = False
                    reasons.append("poor sleep")
                if stress >= 7:
                    allowed = False
                    reasons.append(
                        f"stress level {stress}/10")
                if substances:
                    allowed = False
                    reasons.append(
                        "substances last night")

                try:
                    with engine.connect() as conn:
                        conn.execute(text("""
                            INSERT INTO
                            pre_session_checks(
                                market, check_date,
                                sleep_quality,
                                stress_level,
                                substances,
                                trading_allowed)
                            VALUES('US',:td,
                                   :sl,:st,:sub,:ta)
                            ON CONFLICT
                            (market, check_date)
                            DO UPDATE SET
                                sleep_quality=:sl,
                                stress_level=:st,
                                substances=:sub,
                                trading_allowed=:ta
                        """), {
                            "td":  str(today_date),
                            "sl":  sleep_val,
                            "st":  stress,
                            "sub": substances,
                            "ta":  allowed
                        })
                        conn.commit()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    else:
        # Show today's check result
        sleep_val  = int(check_data[0])
        stress_val = int(check_data[1])
        subs       = bool(check_data[2])
        allowed    = bool(check_data[3])

        sleep_label = {1:"Poor",2:"OK",3:"Good"
                       }.get(sleep_val,"OK")
        sleep_emoji = {1:"😴",2:"😐",3:"😊"
                       }.get(sleep_val,"😐")

        if not allowed:
            # Red — do not trade
            reasons = []
            if sleep_val == 1:
                reasons.append("poor sleep")
            if stress_val >= 7:
                reasons.append(
                    f"stress {stress_val}/10")
            if subs:
                reasons.append(
                    "substances last night")
            reason_str = " · ".join(reasons)

            st.markdown(
                f"<div style='background:#FFE8E8;"
                f"border:0.5px solid #E24B4A;"
                f"border-radius:12px;"
                f"padding:16px 20px;"
                f"margin-bottom:16px;'>"
                f"<p style='color:#A32D2D;"
                f"font-size:15px;font-weight:500;"
                f"margin:0 0 6px;'>"
                f"🔴 Do not trade today</p>"
                f"<p style='color:#A32D2D;"
                f"font-size:12px;margin:0 0 10px;'>"
                f"{reason_str.capitalize()}. "
                f"Your edge disappears under "
                f"these conditions.</p>"
                f"<p style='color:#A32D2D;"
                f"font-size:12px;margin:0;'>"
                f"Sleep: {sleep_emoji} {sleep_label} · "
                f"Stress: {stress_val}/10"
                f"{'  · Substances: Yes' if subs else ''}"
                f"</p></div>",
                unsafe_allow_html=True
            )

            # Allow override with reason
            with st.expander(
                "Override — I understand the risk"):
                reason = st.text_input(
                    "Why are you trading anyway?",
                    placeholder="Be honest with yourself"
                )
                if st.button("Override and continue"):
                    if reason:
                        try:
                            with engine.connect() \
                                    as conn:
                                conn.execute(text("""
                                    UPDATE
                                    pre_session_checks
                                    SET override=TRUE,
                                    override_reason=:r
                                    WHERE market='US'
                                    AND check_date=:td
                                """), {
                                    "r":  reason,
                                    "td": str(today_date)
                                })
                                conn.commit()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.warning(
                            "Enter a reason first.")

        elif stress_val >= 5 or sleep_val == 2:
            # Yellow — trade with caution
            st.markdown(
                f"<div style='background:#FFF8E1;"
                f"border:0.5px solid #BA7517;"
                f"border-radius:12px;"
                f"padding:14px 20px;"
                f"margin-bottom:16px;'>"
                f"<p style='color:#854F0B;"
                f"font-size:14px;font-weight:500;"
                f"margin:0 0 4px;'>"
                f"⚠️ Trade with caution today</p>"
                f"<p style='color:#854F0B;"
                f"font-size:12px;margin:0;'>"
                f"Sleep: {sleep_emoji} {sleep_label} · "
                f"Stress: {stress_val}/10 · "
                f"Reduce size 50% · Max 2 trades"
                f"</p></div>",
                unsafe_allow_html=True
            )
        else:
            # Green — all clear
            st.markdown(
                f"<div style='background:#EAF3DE;"
                f"border:0.5px solid #3B6D11;"
                f"border-radius:12px;"
                f"padding:14px 20px;"
                f"margin-bottom:16px;'>"
                f"<p style='color:#27500A;"
                f"font-size:14px;font-weight:500;"
                f"margin:0 0 4px;'>"
                f"✅ Good to go today</p>"
                f"<p style='color:#27500A;"
                f"font-size:12px;margin:0;'>"
                f"Sleep: {sleep_emoji} {sleep_label} · "
                f"Stress: {stress_val}/10 · "
                f"System ready."
                f"</p></div>",
                unsafe_allow_html=True
            )


    today_losses=0; hi_behaviors=0; total_today=0
    if today_t and today_t[0]:
        total_today  = int(today_t[0] or 0)
        today_losses = int(today_t[4] or 0)
    hi_behaviors = sum(1 for b in today_b
                       if b[1]=="High")

    if today_losses>=2 or hi_behaviors>=3:
        sc="CC0000"; st_txt="🔴 STOP TRADING"
        st_desc=(f"{today_losses} losses. "
                 f"Close platform now.")
    elif today_losses>=1 or hi_behaviors>=2:
        sc="FF6600"; st_txt="🟠 TILT RISK"
        st_desc="Elevated risk. Minimum size."
    elif hi_behaviors>=1:
        sc="FF8C00"; st_txt="🟡 ELEVATED"
        st_desc="Minor issues. Trade carefully."
    else:
        sc="0066CC"; st_txt="🟢 NORMAL"
        st_desc="No behavioral concerns today."

    st.markdown(
        f"<div style='background:#{sc}15;"
        f"padding:14px;border-radius:8px;"
        f"border-left:4px solid #{sc};"
        f"margin-bottom:12px;'>"
        f"<p style='color:#{sc};font-size:18px;"
        f"font-weight:bold;margin:0;'>{st_txt}</p>"
        f"<p style='color:#333;font-size:13px;"
        f"margin:4px 0 0;'>{st_desc}</p></div>",
        unsafe_allow_html=True
    )


    # ── Behavioral patterns ──────────
    from datetime import timedelta
    today_est2 = datetime.now(EST).date()
    week_ago2  = today_est2 - timedelta(days=7)
    yesterday2 = today_est2 - timedelta(days=1)
    prev_week2 = today_est2 - timedelta(days=14)

    def get_period_events(start, end):
        uid = st.session_state.get(
            "user_id", 1)
        try:
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT behavior_type,
                           COUNT(*) as cnt,
                           SUM(financial_cost)
                               as cost
                    FROM behavioral_events
                    WHERE market='US'
                    AND user_id=:uid
                    AND event_date >= :s
                    AND event_date <= :e
                    GROUP BY behavior_type
                    ORDER BY cnt DESC
                """), {
                    "s":   str(start),
                    "e":   str(end),
                    "uid": uid
                }).fetchall()
            return rows
        except Exception as e:
            return []

    BEHAVIOR_PLAIN = {
        "Revenge Trading":
            ("traded too soon after a loss",
             False, "stop → 30 min break after every loss"),
        "Overtrading":
            ("took too many trades",
             False, "stop → max 3 trades per day"),
        "Rule Violation":
            ("skipped pre-trade checks",
             False, "fix → check system before every trade"),
        "Emotional Exit":
            ("exited on emotion not plan",
             False, "fix → set exit level before entering"),
        "FOMO":
            ("chased price without a setup",
             False, "stop → wait for price to come to you"),
        "Traded Against Edge":
            ("traded when system said sit out",
             False, "fix → trust the No Edge signal"),
        "Wrong Setup for Day":
            ("used wrong strategy for day type",
             False, "fix → match setup to today's edge"),
        "Respected No Edge":
            ("sat out correctly on No Edge days",
             True, ""),
        "Greed":
            ("held losers too long hoping for reversal",
             False, "fix → honour your stop every time"),
        "Hesitant Trading":
            ("exited winners early before target",
             False, "fix → trust your target, use breakeven stop"),
        "Boredom Trading":
            ("took trades without a clear setup",
             False, "stop → no setup, no trade"),
    }

    month_ago2 = today_est2 - timedelta(days=30)
    yest_evts  = get_period_events(
        yesterday2, yesterday2)
    week_evts  = get_period_events(
        week_ago2, today_est2)
    month_evts = get_period_events(
        month_ago2, today_est2)
    prev_evts  = get_period_events(
        prev_week2, week_ago2)

    # Build consolidated view
    def summarize_period(evts):
        neg = []
        pos = []
        for e in evts:
            btype = e[0]
            count = int(e[1])
            cost  = float(e[2] or 0)
            p = BEHAVIOR_PLAIN.get(btype)
            if not p:
                continue
            desc, is_pos, fix = p
            if is_pos:
                pos.append((desc,count,cost,fix))
            else:
                neg.append((desc,count,cost,fix))
        return neg, pos

    yest_neg,  yest_pos  = summarize_period(yest_evts)
    week_neg,  week_pos  = summarize_period(week_evts)
    month_neg, month_pos = summarize_period(month_evts)
    prev_neg,  _         = summarize_period(prev_evts)

    # Trend
    trend = None
    if len(week_neg) < len(prev_neg):
        trend = "improving"
    elif len(week_neg) > len(prev_neg):
        trend = "worse"

    # Net conclusion
    conclusion = ""
    if month_neg and month_pos:
        conclusion = (
            "Keep sitting out on No Edge days. "
            "Work on not trading when the "
            "system says sit out.")
    elif month_neg:
        top = month_neg[0]
        conclusion = (
            f"One thing to fix: "
            f"stop {top[0]}. {top[3].split('→')[-1].strip().capitalize()}.")
    elif month_pos:
        conclusion = (
            "No issues this month. "
            "Discipline is strong.")

    # Render — clean and compact
    st.markdown(
        "<div style='font-size:24px;"
        "font-weight:800;color:#1A1A2E;"
        "margin-bottom:12px;'>"
        "🧠 Your Trading Behavior</div>",
        unsafe_allow_html=True)

    # Three columns: Yesterday | This Week | This Month
    bc1, bc2, bc3 = st.columns(3)

    def render_col(col, label,
                   neg, pos, show_ok=True):
        with col:
            st.markdown(
                f"<div style='font-size:15px;"
                f"font-weight:700;color:#888;"
                f"text-transform:uppercase;"
                f"letter-spacing:1px;"
                f"margin-bottom:8px;'>"
                f"{label}</div>",
                unsafe_allow_html=True)
            if not neg and not pos:
                st.markdown(
                    "<div style='color:#888;"
                    "font-size:14px;'>"
                    "Nothing flagged</div>",
                    unsafe_allow_html=True)
                return
            for desc,count,cost,fix in neg:
                cost_txt = (
                    f" — cost ${abs(cost):.0f}"
                    if cost < -5
                    else f" — made ${cost:.0f}"
                    if cost > 5
                    else "")
                fix_parts = fix.split("→")
                fix_label = fix_parts[0].strip()                         if len(fix_parts) > 1 else ""
                fix_action = fix_parts[-1].strip()
                st.markdown(
                    f"<div style='margin-bottom:"
                    f"10px;padding-left:10px;"
                    f"border-left:3px solid #CC3333;'>"
                    f"<div style='font-size:20px;"
                    f"font-weight:600;"
                    f"color:#CC3333;'>"
                    f"↑ {count}×</div>"
                    f"<div style='font-size:16px;"
                    f"color:#333;line-height:1.4;'>"
                    f"{desc.capitalize()}"
                    f"{cost_txt}</div>"
                    f"<div style='font-size:14px;"
                    f"color:#888;margin-top:2px;'>"
                    f"{fix_action.capitalize()}"
                    f"</div></div>",
                    unsafe_allow_html=True)
            if show_ok:
                for desc,count,cost,fix in pos:
                    st.markdown(
                        f"<div style='margin-bottom:"
                        f"10px;padding-left:10px;"
                        f"border-left:3px solid"
                        f" #2E7D32;'>"
                        f"<div style='font-size:20px;"
                        f"font-weight:600;"
                        f"color:#2E7D32;'>"
                        f"✓ {count}×</div>"
                        f"<div style='font-size:16px;"
                        f"color:#111;font-weight:500;'>"
                        f"{desc.capitalize()}"
                        f"</div></div>",
                        unsafe_allow_html=True)

    render_col(bc1, "Yesterday",
               yest_neg, yest_pos)
    render_col(bc2, "This Week",
               week_neg, week_pos)
    render_col(bc3, "This Month",
               month_neg, month_pos)

    # Trend + conclusion
    if trend == "improving":
        st.caption(
            "📈 Fewer issues this week "
            "vs last week — improving.")
    elif trend == "worse":
        st.caption(
            "📉 More issues this week "
            "vs last week — refocus.")

    if conclusion:
        st.markdown(
            f"<div style='border-top:"
            f"1px solid #E0E0E0;"
            f"padding-top:12px;"
            f"margin-top:10px;'>"
            f"<div style='font-size:13px;"
            f"font-weight:700;color:#0066CC;"
            f"text-transform:uppercase;"
            f"letter-spacing:1px;"
            f"margin-bottom:6px;'>"
            f"💡 This Week's Priority"
            f"</div>"
            f"<div style='font-size:17px;"
            f"font-weight:600;"
            f"color:#1A1A2E;'>"
            f"{conclusion}</div>"
            f"</div>",
            unsafe_allow_html=True)

    # ── Best/worst time to trade ──────────
    try:
        tod = get_time_analysis()
        if tod and len(tod) >= 2:
            tod_wr = [
                (t[0], t[1],
                 round(t[2]/t[1]*100,1)
                 if t[1] > 0 else 0)
                for t in tod]
            best  = max(tod_wr,
                        key=lambda x: x[2])
            worst = min(tod_wr,
                        key=lambda x: x[2])
            if best[2] != worst[2]:
                st.markdown(
                    "<div style='font-size:13px;"
                    "font-weight:700;color:#888;"
                    "text-transform:uppercase;"
                    "letter-spacing:1px;"
                    "margin:12px 0 8px;'>"
                    "⏰ Your Trading Windows"
                    "</div>",
                    unsafe_allow_html=True)
                tw1, tw2 = st.columns(2)
                tw1.markdown(
                    f"<div style='"
                    f"padding:8px 12px;"
                    f"border-left:3px solid"
                    f" #2E7D32;"
                    f"margin-top:8px;'>"
                    f"<div style='font-size:13px;"
                    f"color:#888;"
                    f"text-transform:uppercase;'>"
                    f"Best time to trade</div>"
                    f"<div style='font-size:17px;"
                    f"font-weight:700;"
                    f"color:#2E7D32;'>"
                    f"{best[0]} EST</div>"
                    f"<div style='font-size:14px;"
                    f"color:#555;'>"
                    f"{best[2]:.0f}% win rate "
                    f"· {best[1]} trades</div>"
                    f"</div>",
                    unsafe_allow_html=True)
                tw2.markdown(
                    f"<div style='"
                    f"padding:8px 12px;"
                    f"border-left:3px solid"
                    f" #CC3333;"
                    f"margin-top:8px;'>"
                    f"<div style='font-size:13px;"
                    f"color:#888;"
                    f"text-transform:uppercase;'>"
                    f"Avoid this window</div>"
                    f"<div style='font-size:17px;"
                    f"font-weight:700;"
                    f"color:#CC3333;'>"
                    f"{worst[0]} EST</div>"
                    f"<div style='font-size:14px;"
                    f"color:#555;'>"
                    f"{worst[2]:.0f}% win rate "
                    f"· {worst[1]} trades</div>"
                    f"</div>",
                    unsafe_allow_html=True)
    except:
        pass

    st.divider()

    # ── Three questions ───────────────────────

    # Q1 — Am I good to trade?
    if check_exists:
        if not trading_allowed:
            q1_color = "#CC0000"
            q1_icon  = "🔴"
            q1_text  = "Do not trade today"
            q1_sub   = "Pre-session check failed"
        elif stress_val >= 5 or sleep_val == 2:
            q1_color = "#FF8C00"
            q1_icon  = "⚠️"
            q1_text  = "Trade with caution"
            q1_sub   = (f"Sleep: {sleep_label} · "
                        f"Stress: {stress_val}/10")
        else:
            q1_color = "#1B5E20"
            q1_icon  = "✅"
            q1_text  = "Good to trade"
            q1_sub   = (f"Sleep: {sleep_label} · "
                        f"Stress: {stress_val}/10")
    else:
        q1_color = "#888"
        q1_icon  = "❓"
        q1_text  = "Complete pre-session check"
        q1_sub   = "Scroll down to answer"

    # Q2 — What is today's signal?
    if report and str(report.get(
            "report_date","")) == str(
            datetime.now(EST).date()):
        edge   = report.get(
            "confidence","No Edge")
        up_pct = int(report.get("up_pct") or 33)
        dn_pct = int(report.get("down_pct") or 33)
        rb_pct = int(report.get("range_pct") or 33)
        action = report.get(
            "reaction_type","")
        bias   = report.get("bias","")

        if "Long" in edge:
            q2_color = "#1B5E20"
            q2_icon  = "📈"
        elif "Short" in edge:
            q2_color = "#CC0000"
            q2_icon  = "📉"
        elif "Range" in edge:
            q2_color = "#E65100"
            q2_icon  = "➡️"
        else:
            q2_color = "#888"
            q2_icon  = "⚪"

        q2_text = f"{edge}"
        q2_sub  = (f"Up {up_pct}% · "
                   f"Down {dn_pct}% · "
                   f"Range {rb_pct}% · "
                   f"{action}")
    else:
        q2_color = "#888"
        q2_icon  = "⏳"
        q2_text  = "Run Cell 3 for signal"
        q2_sub   = "Signal not yet available"

    # Q3 — What am I doing wrong?
    q3_color = "#1B5E20"
    q3_icon  = "✅"
    q3_text  = "Nothing flagged"
    q3_sub   = "Keep doing what you are doing"

    if today_b:
        top = today_b[0]
        btype = top[0] if top else ""
        cost  = float(top[3]) \
            if top and len(top) > 3 \
            and top[3] else 0
        if btype == "Revenge Trading":
            q3_color = "#CC0000"
            q3_icon  = "🔴"
            q3_text  = "Stop — revenge risk"
            q3_sub   = ("You took a trade too "
                        "soon after a loss. "
                        "Take a 30 min break.")
        elif btype == "Overtrading":
            q3_color = "#FF8C00"
            q3_icon  = "⚠️"
            q3_text  = "Too many trades today"
            q3_sub   = ("Win rate drops after "
                        "3 trades. Sit out.")
        elif btype == "Rule Violation":
            q3_color = "#FF8C00"
            q3_icon  = "⚠️"
            q3_text  = "Rule violation today"
            q3_sub   = ("You skipped a step "
                        "before taking a trade.")
        elif btype == "Emotional Exit":
            q3_color = "#FF8C00"
            q3_icon  = "⚠️"
            q3_text  = "Emotional exit detected"
            q3_sub   = ("You exited on fear. "
                        "That may cost you profits.")
    elif events_b:
        # Check last 30 days patterns
        # events_b = (behavior_type, cnt, cost)
        pattern_costs = {}
        for e in events_b[:20]:
            bt   = e[0]
            cnt  = int(e[1] or 0)
            cost = float(e[2] or 0) \
                if len(e) > 2 else 0
            pattern_costs[bt] = {
                "count": cnt,
                "cost":  cost
            }

        if pattern_costs:
            top_pattern = max(
                pattern_costs.items(),
                key=lambda x: x[1]["count"])
            bt    = top_pattern[0]
            count = top_pattern[1]["count"]
            cost  = top_pattern[1]["cost"]

            plain = {
                "Rule Violation":
                    f"You skipped pre-trade "
                    f"checks {count}x recently",
                "Revenge Trading":
                    f"You revenge traded "
                    f"{count}x recently",
                "Overtrading":
                    f"You overtraded {count}x "
                    f"recently",
                "Emotional Exit":
                    f"You exited on emotion "
                    f"{count}x recently",
                "Respected No Edge":
                    f"You sat out correctly "
                    f"{count}x — keep it up",
            }.get(bt,
                  f"{bt} {count}x recently")

            if bt == "Respected No Edge":
                q3_color = "#1B5E20"
                q3_icon  = "✅"
                q3_sub   = "Keep it up"
            else:
                q3_color = "#FF8C00"
                q3_icon  = "⚠️"
                q3_sub   = (
                    f"${abs(cost):.0f} cost"
                    if cost < -5
                    else "Catch this early")
            q3_text = plain

    # Render three questions
    st.markdown(
        f"<div style='margin-bottom:12px;'>",
        unsafe_allow_html=True)

    for icon, color, title, sub in [
        (q1_icon, q1_color,
         q1_text, q1_sub),
        (q2_icon, q2_color,
         q2_text, q2_sub),
        (q3_icon, q3_color,
         q3_text, q3_sub),
    ]:
        st.markdown(
            f"<div style='display:flex;"
            f"align-items:flex-start;"
            f"gap:12px;padding:12px 16px;"
            f"background:#FAFAFA;"
            f"border:0.5px solid #E0E0E0;"
            f"border-left:4px solid {color};"
            f"border-radius:8px;"
            f"margin-bottom:8px;'>"
            f"<div style='font-size:22px;"
            f"line-height:1;'>{icon}</div>"
            f"<div>"
            f"<div style='font-size:16px;"
            f"font-weight:600;"
            f"color:{color};"
            f"margin-bottom:3px;'>"
            f"{title}</div>"
            f"<div style='font-size:12px;"
            f"color:#666;'>{sub}</div>"
            f"</div></div>",
            unsafe_allow_html=True
        )

    st.markdown("</div>",
                unsafe_allow_html=True)

    # Coaching brief — plain English
    brief = generate_coaching_brief(
        events_b,scores_b,today_t,report)

    # Signal summary
    signal_summary = generate_signal_summary(
        report)

    if signal_summary:
        st.markdown(
            f"<div style='background:#F0F4FF;"
            f"border:0.5px solid #C5D5FF;"
            f"border-radius:8px;"
            f"padding:12px 16px;"
            f"margin-bottom:8px;'>"
            f"<p style='color:#666;"
            f"font-size:11px;margin:0 0 4px;'>"
            f"📊 MARKET CONTEXT</p>"
            f"<p style='color:#1A1A2E;"
            f"font-size:14px;font-weight:500;"
            f"line-height:1.6;margin:0;'>"
            f"{signal_summary}</p>"
            f"</div>",
            unsafe_allow_html=True
        )

    if brief:
        st.markdown(
            f"<div style='background:#EEF4FF;"
            f"border:0.5px solid #0066CC;"
            f"border-radius:8px;"
            f"padding:12px 16px;"
            f"margin-bottom:12px;'>"
            f"<p style='color:#666;"
            f"font-size:11px;margin:0 0 4px;'>"
            f"💬 COACHING INSIGHT</p>"
            f"<p style='color:#1A1A2E;"
            f"font-size:14px;font-weight:500;"
            f"line-height:1.6;margin:0;'>"
            f"{brief}</p>"
            f"</div>",
            unsafe_allow_html=True
        )

    # ── Daily behavioral score ────────────────
    daily_score = calculate_daily_score(
        date.today())
    streaks     = get_streaks()

    if daily_score:
        sc_val   = daily_score["score"]
        sc_col   = score_color(sc_val)
        sc_state = daily_score["state"]
        st.markdown(
            f"<div style='background:{sc_col}15;"
            f"padding:14px;border-radius:8px;"
            f"border-left:4px solid {sc_col};"
            f"margin-bottom:12px;'>"
            f"<p style='color:#666;font-size:11px;"
            f"margin:0;'>TODAY'S BEHAVIORAL SCORE</p>"
            f"<p style='color:{sc_col};font-size:36px;"
            f"font-weight:bold;margin:4px 0 2px;'>"
            f"{sc_val}/100 — {sc_state}</p>"
            f"<div style='background:#E8E8E8;"
            f"border-radius:4px;height:8px;"
            f"margin-top:6px;'>"
            f"<div style='background:{sc_col};"
            f"width:{sc_val}%;height:8px;"
            f"border-radius:4px;'></div>"
            f"</div></div>",
            unsafe_allow_html=True
        )
        sb1,sb2,sb3,sb4,sb5 = st.columns(5)
        for col,label,val,mx in [
            (sb1,"System",
             daily_score["sys_score"],25),
            (sb2,"Rules",
             daily_score["plan_score"],25),
            (sb3,"Emotion",
             daily_score["emo_score"],20),
            (sb4,"Discipline",
             daily_score["disc_score"],20),
            (sb5,"Behavior",
             daily_score["beh_score"],10),
        ]:
            pct   = round(val/mx*100) if mx>0 else 0
            color = ("#0066CC" if pct>=80
                     else "#FF8C00" if pct>=50
                     else "#CC0000")
            col.markdown(
                f"<div style='text-align:center;"
                f"padding:8px;background:#F8F9FA;"
                f"border-radius:6px;'>"
                f"<p style='color:#666;"
                f"font-size:10px;margin:0;'>"
                f"{label}</p>"
                f"<p style='color:{color};"
                f"font-size:18px;font-weight:bold;"
                f"margin:2px 0;'>{val}/{mx}</p>"
                f"</div>",
                unsafe_allow_html=True
            )

    # ── Auto-update account balances ─────────────
    try:
        today_est = datetime.now(EST).date()
        with engine.connect() as conn:
            accounts_to_update = conn.execute(
                text("""
                SELECT s.account_name,
                       s.account_type,
                       s.risk_pct,
                       s.max_loss_multiplier,
                       COALESCE(
                         (SELECT closing_balance
                          FROM account_balances
                          WHERE market='US'
                          AND account_name=
                              s.account_name
                          ORDER BY balance_date
                          DESC LIMIT 1),
                         s.current_balance) as bal
                FROM account_settings s
                WHERE s.market='US'
                AND s.user_id=:uid
                AND s.is_active=TRUE
            """), {
                "uid": st.session_state.get("user_id",1)
            }).fetchall()

            for a in accounts_to_update:
                name  = a[0]
                atype = a[1]
                rpct  = float(a[2])
                mult  = int(a[3])
                bal   = float(a[4] or 0)

                pnl = conn.execute(text("""
                    SELECT COALESCE(SUM(pnl),0)
                    FROM trade_journal
                    WHERE market='US'
                    AND user_id=:uid
                    AND trade_date=:td
                    AND (account_type=:an
                         OR account_type=:at)
                """), {
                    "td":  str(today_est),
                    "an":  name,
                    "at":  atype,
                    "uid": st.session_state
                           .get("user_id",1)
                }).fetchone()[0]
                pnl = float(pnl or 0)

                closing  = bal + pnl
                risk     = round(
                    closing * rpct/100, 2)
                max_loss = round(risk * mult, 2)

                conn.execute(text("""
                    INSERT INTO account_balances(
                        market, account_name,
                        balance_date,
                        opening_balance,
                        closing_balance,
                        daily_pnl,
                        risk_per_trade,
                        max_loss_today)
                    VALUES('US',:an,:td,
                           :o,:c,:pnl,:r,:ml)
                    ON CONFLICT
                    (market,account_name,
                     balance_date)
                    DO UPDATE SET
                        closing_balance=:c,
                        daily_pnl=:pnl,
                        risk_per_trade=:r,
                        max_loss_today=:ml
                """), {
                    "an":  name,
                    "td":  str(today_est),
                    "o":   bal,
                    "c":   closing,
                    "pnl": pnl,
                    "r":   risk,
                    "ml":  max_loss
                })
            conn.commit()
    except Exception as e:
        pass

    # ── Risk summary per account ──────────────
    try:
        today_est = datetime.now(EST).date()
        uid = st.session_state.get(
            "user_id", 1)
        with engine.connect() as conn:
            accounts = conn.execute(text("""
                SELECT
                    s.account_name,
                    s.account_type,
                    s.risk_pct,
                    s.max_loss_multiplier,
                    s.is_active,
                    s.current_balance
                FROM account_settings s
                WHERE s.market='US'
                AND s.user_id=:uid
                AND s.is_active = TRUE
                ORDER BY s.account_type DESC
            """), {"uid": uid}).fetchall()

            # All P&L from inception
            all_pnl = conn.execute(text("""
                SELECT account_type,
                       SUM(pnl) as total_pnl
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                GROUP BY account_type
            """), {"uid": uid}).fetchall()

            # Today's P&L
            today_pnl = conn.execute(text("""
                SELECT account_type,
                       SUM(pnl) as total_pnl
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                AND trade_date=:td
                GROUP BY account_type
            """), {
                "td":  str(today_est),
                "uid": uid
            }).fetchall()

        # Build P&L maps
        all_pnl_map = {
            r[0]: float(r[1] or 0)
            for r in all_pnl}
        today_pnl_map = {
            r[0]: float(r[1] or 0)
            for r in today_pnl}

        if accounts:
            st.divider()
            st.markdown(
                "**💰 Today's Risk Summary**")
            for a in accounts:
                name     = a[0]
                atype    = a[1]
                rpct     = float(a[2])
                mult     = int(a[3])
                start_bal= float(a[5] or 0)

                # Live balance =
                # starting balance + all P&L
                total_earned = all_pnl_map.get(
                    atype, all_pnl_map.get(
                        name, 0))
                balance  = round(
                    start_bal + total_earned, 2)
                risk     = round(
                    balance * rpct/100, 2)
                max_loss = round(
                    risk * mult, 2)

                # Today's losses only
                pnl_today = today_pnl_map.get(
                    atype, today_pnl_map.get(
                        name, 0))
                used = abs(min(0, pnl_today))
                used_pct = round(
                    used/max_loss*100
                    if max_loss > 0 else 0)
                remaining = max(
                    0, max_loss - used)

                # Color based on usage
                if used_pct >= 100:
                    bar_color = "#CC0000"
                    status = "🔴 LOCKED"
                elif used_pct >= 75:
                    bar_color = "#FF8C00"
                    status = "⚠️ WARNING"
                else:
                    bar_color = "#0066CC"
                    status = "✅ OK"

                st.markdown(
                    f"<div style='background:"
                    f"#F8F9FA;border:0.5px solid "
                    f"#E0E0E0;border-radius:8px;"
                    f"padding:12px 16px;"
                    f"margin-bottom:8px;'>"
                    f"<div style='display:flex;"
                    f"justify-content:space-between;"
                    f"align-items:center;"
                    f"margin-bottom:8px;'>"
                    f"<b style='font-size:13px;'>"
                    f"{name}</b>"
                    f"<span style='font-size:11px;"
                    f"color:#666;'>{status}</span>"
                    f"</div>"
                    f"<div style='display:grid;"
                    f"grid-template-columns:"
                    f"1fr 1fr 1fr 1fr;"
                    f"gap:8px;margin-bottom:8px;'>"
                    f"<div><div style='color:#888;"
                    f"font-size:10px;'>Balance</div>"
                    f"<div style='font-size:14px;"
                    f"font-weight:500;'>"
                    f"${balance:,.0f}</div></div>"
                    f"<div><div style='color:#888;"
                    f"font-size:10px;'>Risk/Trade"
                    f"</div><div style='font-size:"
                    f"14px;font-weight:500;'>"
                    f"${risk:,.0f}</div></div>"
                    f"<div><div style='color:#888;"
                    f"font-size:10px;'>Max Loss"
                    f"</div><div style='font-size:"
                    f"14px;font-weight:500;'>"
                    f"${max_loss:,.0f}</div></div>"
                    f"<div><div style='color:#888;"
                    f"font-size:10px;'>Remaining"
                    f"</div><div style='font-size:"
                    f"14px;font-weight:500;"
                    f"color:{bar_color};'>"
                    f"${remaining:,.0f}</div></div>"
                    f"</div>"
                    f"<div style='background:#E0E0E0;"
                    f"border-radius:4px;height:6px;'>"
                    f"<div style='background:"
                    f"{bar_color};width:"
                    f"{min(100,used_pct)}%;"
                    f"height:6px;border-radius:4px;"
                    f"transition:width 0.3s;'>"
                    f"</div></div>"
                    f"<div style='font-size:10px;"
                    f"color:#888;margin-top:4px;'>"
                    f"Used: ${used:,.0f} of "
                    f"${max_loss:,.0f} "
                    f"({used_pct}%)</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

                # Lock gate if limit hit
                if used_pct >= 100:
                    st.error(
                        f"🔴 {name} daily loss "
                        f"limit reached. "
                        f"No more trades on "
                        f"this account today.")

    except Exception as e:
        st.error(f"Risk summary error: {e}")

    # ── Streak display ────────────────────────
    if streaks:
        st.divider()
        sk1,sk2 = st.columns(2)
        with sk1:
            ts = streaks["trade_streak"]
            tt = streaks["trade_streak_type"]
            if ts > 0 and tt:
                sk_col = ("#0066CC" if tt=="Win"
                          else "#CC0000")
                sk_em  = ("🔥" if tt=="Win"
                          else "📉")
                st.markdown(card(
                    f'<p style="color:#666;'
                    f'font-size:11px;margin:0;">'
                    f'TRADE STREAK</p>'
                    f'<p style="color:{sk_col};'
                    f'font-size:22px;'
                    f'font-weight:bold;margin:4px 0;">'
                    f'{sk_em} {ts} {tt}s in a row'
                    f'</p>',
                    border_color=sk_col
                ), unsafe_allow_html=True)
            else:
                st.markdown(card(
                    f'<p style="color:#666;'
                    f'font-size:11px;margin:0;">'
                    f'TRADE STREAK</p>'
                    f'<p style="color:#888;'
                    f'font-size:14px;margin:4px 0;">'
                    f'No trades yet</p>',
                    border_color="#888"
                ), unsafe_allow_html=True)
        with sk2:
            ps = streaks["pred_streak"]
            pt = streaks["pred_streak_type"]
            if ps > 0 and pt:
                pk_col = ("#0066CC"
                          if pt=="Correct"
                          else "#CC0000")
                pk_em  = ("✅" if pt=="Correct"
                          else "❌")
                st.markdown(card(
                    f'<p style="color:#666;'
                    f'font-size:11px;margin:0;">'
                    f'PREDICTION STREAK</p>'
                    f'<p style="color:{pk_col};'
                    f'font-size:22px;'
                    f'font-weight:bold;margin:4px 0;">'
                    f'{pk_em} {ps} {pt} in a row'
                    f'</p>',
                    border_color=pk_col
                ), unsafe_allow_html=True)
        for w in streaks.get("warnings",[]):
            wc = ("#CC0000"
                  if any(x in w for x in
                         ["⛔","🔴"])
                  else "#FF8C00")
            st.markdown(
                f"<div style='background:{wc}15;"
                f"padding:10px 14px;"
                f"border-radius:6px;"
                f"border-left:3px solid {wc};"
                f"margin-bottom:6px;'>{w}</div>",
                unsafe_allow_html=True
            )

    col_brief,col_log = st.columns([1,1])

    # ── Left column — behavioral summary ─────
    with col_brief:





        # ── No Edge streak ────────────────────
        try:
            with engine.connect() as conn:
                # Get recent No Edge days
                # from learning_log
                ne_days = conn.execute(text("""
                    SELECT log_date,
                           was_correct,
                           actual_bias
                    FROM learning_log
                    WHERE market='US'
                    AND predicted_bias IN
                        ('No Edge','Range Bias')
                    ORDER BY log_date DESC
                    LIMIT 20
                """)).fetchall()

                # Count consecutive correct
                # sit-out days
                streak = 0
                for nd in ne_days:
                    if bool(nd[1]):
                        streak += 1
                    else:
                        break

                # Last No Edge day price data
                last_ne = conn.execute(text("""
                    SELECT ll.log_date,
                           pd.open, pd.high,
                           pd.low, pd.close
                    FROM learning_log ll
                    LEFT JOIN price_data pd
                        ON DATE(pd.timestamp)
                           = ll.log_date
                        AND pd.ticker='SPY'
                        AND pd.timeframe='1d'
                        AND pd.market='US'
                    WHERE ll.market='US'
                    AND ll.predicted_bias IN
                        ('No Edge','Range Bias')
                    ORDER BY ll.log_date DESC
                    LIMIT 1
                """)).fetchone()

            if streak >= 1:
                st.markdown(
                    f"<div style='background:"
                    f"#E8F5E9;padding:10px 14px;"
                    f"border-radius:6px;"
                    f"border-left:3px solid "
                    f"#4CAF50;margin-bottom:6px;'>"
                    f"🎯 <b>{streak} consecutive "
                    f"No Edge / Range Bias days "
                    f"called correctly</b><br>"
                    f"<span style='color:#666;"
                    f"font-size:12px;'>"
                    f"System identified uncertainty "
                    f"{streak} days in a row. "
                    f"Discipline is building."
                    f"</span></div>",
                    unsafe_allow_html=True
                )

            if last_ne and last_ne[1]:
                o = float(last_ne[1])
                h = float(last_ne[2])
                l = float(last_ne[3])
                c = float(last_ne[4])
                day_range_pct = (h-l)/o*100
                est_exposure  = round(
                    10000*(day_range_pct/2/100),2)
                direction = (
                    "up" if c > o else "down")
                move_pct  = round(
                    abs(c-o)/o*100, 2)
                last_date = str(last_ne[0])
                st.markdown(
                    f"<div style='background:"
                    f"#E3F2FD;padding:10px 14px;"
                    f"border-radius:6px;"
                    f"border-left:3px solid "
                    f"#0066CC;margin-bottom:6px;'>"
                    f"💰 <b>Last No Edge day "
                    f"({last_date}): market went "
                    f"{direction} {move_pct}%"
                    f"</b><br>"
                    f"<span style='color:#666;"
                    f"font-size:12px;'>"
                    f"Sitting out avoided up to "
                    f"${est_exposure:.0f} "
                    f"exposure on a "
                    f"{day_range_pct:.1f}pt "
                    f"range day."
                    f"</span></div>",
                    unsafe_allow_html=True
                )

        except Exception as e:
            pass

        if scores_b:
            st.markdown("**Score trend:**")
            vals = [int(s[0]) for s in
                    reversed(scores_b)]
            dts  = [str(s[2]) for s in
                    reversed(scores_b)]
            fig  = go.Figure()
            fig.add_trace(go.Scatter(
                x=dts,y=vals,
                mode="lines+markers",
                line=dict(color="#0066CC",width=2),
                marker=dict(size=6)
            ))
            fig.update_layout(
                height=140,
                margin=dict(l=0,r=0,t=0,b=0),
                yaxis=dict(range=[0,100]),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig,
                use_container_width=True)

    # Trade log form
    with col_log:
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


