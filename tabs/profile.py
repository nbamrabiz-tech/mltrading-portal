# ── My Profile Tab ───────────────
import streamlit as st
from tabs import log_trade
from db import get_engine
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
            substance_opts = {
                "😊 Completely fine": 0,
                "😐 Slightly off — mild effect": 1,
                "😟 Noticeably impaired": 2,
                "🤢 Hungover — should not trade": 3,
            }
            substance_label = st.selectbox(
                "How do you feel right now?",
                list(substance_opts.keys()),
                key="substance_check"
            )
            substance_level = substance_opts[
                substance_label]
            substances = substance_level > 0

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
                if substance_level == 3:
                    allowed = False
                    reasons.append(
                        "hungover — do not trade today")
                elif substance_level == 2:
                    allowed = False
                    reasons.append(
                        "noticeably impaired — sit out")
                elif substance_level == 1:
                    reasons.append(
                        "slightly off — trade small")

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

    # ── Setup reminder (personal system) ─────
    if report:
        up_pct    = int(report.get("up_pct",33))
        down_pct  = int(report.get("down_pct",33))
        range_pct = int(report.get("range_pct",34))
        edge      = str(report.get("confidence",
                    report.get("bias", "")))

        if "No Edge" in str(edge) or \
                range_pct >= up_pct:
            # Range context
            setup_reminder = (
                "**Range setup:** Wait for "
                "consolidation → breakout with "
                "volume + delta → FVG → enter "
                "at FVG fill. Stop: other side "
                "of FVG.")
            setup_icon = "↔️"
        elif up_pct > down_pct:
            # Bullish trend context
            setup_reminder = (
                "**Trend setup (Long):** Wait "
                "for HH+HL → pullback to "
                "EMA-21/34 or VWAP → bullish "
                "confirmation candle → enter. "
                "Stop: below candle low.")
            setup_icon = "📈"
        else:
            # Bearish trend context
            setup_reminder = (
                "**Trend setup (Short):** Wait "
                "for LH+LL → pullback to "
                "EMA-21/34 or VWAP → bearish "
                "confirmation candle → enter. "
                "Stop: above candle high.")
            setup_icon = "📉"

        st.markdown(
            f"<div style='background:#F8F8F8;"
            f"border:0.5px solid #DDD;"
            f"border-radius:8px;"
            f"padding:12px 16px;"
            f"margin-bottom:8px;'>"
            f"<p style='color:#666;"
            f"font-size:11px;margin:0 0 4px;'>"
            f"{setup_icon} YOUR SETUP TODAY</p>"
            f"<p style='color:#1A1A2E;"
            f"font-size:14px;"
            f"line-height:1.6;margin:0;'>"
            f"{setup_reminder}</p>"
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


    # Trade logging
    log_trade.render(
        engine, today, now_est,
        check_exists=check_exists,
        check_data=check_data,
        trading_allowed=trading_allowed)

