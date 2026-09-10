# ── Behavioral Intelligence Tab ───────────────
import streamlit as st
from datetime import date, timedelta, datetime
from sqlalchemy import text
import pytz
EST = pytz.timezone("America/New_York")
from db import get_engine
from queries.behavioral import get_behavioral_data


def render(engine, **kwargs):
    """
    Behavioral Intelligence — deep dive into
    trading psychology patterns over time.
    """
    st.subheader("🧠 Behavioral Intelligence")

    uid = st.session_state.get("user_id", 1)

    # ── Period selector ───────────────────────
    period = st.radio(
        "View period:",
        ["This Week", "This Month",
         "Last 90 Days", "All Time"],
        horizontal=True,
        key="behav_period")

    period_days = {
        "This Week":    7,
        "This Month":   30,
        "Last 90 Days": 90,
        "All Time":     3650
    }
    days_back = period_days[period]
    start_date = date.today() - \
        timedelta(days=days_back)

    try:
        with engine.connect() as conn:

            # ── All patterns summary ──────────
            all_patterns = conn.execute(text("""
                SELECT behavior_type,
                       severity,
                       COUNT(*) as cnt,
                       SUM(financial_cost) as cost,
                       MIN(event_date) as first,
                       MAX(event_date) as last
                FROM behavioral_events
                WHERE market='US'
                AND user_id=:uid
                AND event_date >= :start
                GROUP BY behavior_type, severity
                ORDER BY
                    CASE severity
                        WHEN 'Critical' THEN 1
                        WHEN 'High' THEN 2
                        WHEN 'Medium' THEN 3
                        WHEN 'Positive' THEN 5
                        ELSE 4
                    END,
                    cnt DESC
            """), {
                "uid":   uid,
                "start": str(start_date)
            }).fetchall()

            # ── Emotion vs performance ────────
            em_perf = conn.execute(text("""
                SELECT
                    CASE
                        WHEN emotional_state <= 2
                            THEN 'Calm (1-2)'
                        WHEN emotional_state <= 4
                            THEN 'Focused (3-4)'
                        WHEN emotional_state <= 6
                            THEN 'Elevated (5-6)'
                        WHEN emotional_state <= 8
                            THEN 'High (7-8)'
                        ELSE 'Extreme (9-10)'
                    END as emotion_band,
                    COUNT(*) as trades,
                    SUM(CASE WHEN pnl>0
                        THEN 1 ELSE 0 END) as wins,
                    AVG(pnl) as avg_pnl,
                    ROUND(AVG(emotional_state),1)
                        as avg_em
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                AND trade_date >= :start
                AND emotional_state IS NOT NULL
                AND trade_status='closed'
                GROUP BY emotion_band,
                    CASE
                        WHEN emotional_state <= 2
                            THEN 1
                        WHEN emotional_state <= 4
                            THEN 2
                        WHEN emotional_state <= 6
                            THEN 3
                        WHEN emotional_state <= 8
                            THEN 4
                        ELSE 5
                    END
                ORDER BY
                    CASE
                        WHEN emotional_state <= 2
                            THEN 1
                        WHEN emotional_state <= 4
                            THEN 2
                        WHEN emotional_state <= 6
                            THEN 3
                        WHEN emotional_state <= 8
                            THEN 4
                        ELSE 5
                    END
            """), {
                "uid":   uid,
                "start": str(start_date)
            }).fetchall()

            # ── Weekly archive ────────────────
            weekly = conn.execute(text("""
                SELECT
                    DATE_TRUNC('week',
                        event_date) as week_start,
                    behavior_type,
                    COUNT(*) as cnt,
                    SUM(financial_cost) as cost
                FROM behavioral_events
                WHERE market='US'
                AND user_id=:uid
                AND event_date >= :start
                AND severity != 'Positive'
                GROUP BY
                    DATE_TRUNC('week', event_date),
                    behavior_type
                ORDER BY week_start DESC,
                         cnt DESC
                LIMIT 50
            """), {
                "uid":   uid,
                "start": str(start_date)
            }).fetchall()

    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    # ── SECTION 1: Pattern Summary ────────────
    st.markdown("### 📊 Pattern Summary")

    PLAIN = {
        "Revenge Trading":
            ("traded too soon after a loss", "🔴"),
        "Overtrading":
            ("took too many trades", "🟡"),
        "Rule Violation":
            ("skipped pre-trade checks", "🟡"),
        "FOMO":
            ("chased price without setup", "🔴"),
        "Boredom Trading":
            ("traded without clear setup", "🟡"),
        "Greed":
            ("held losers too long", "🔴"),
        "Hesitant Trading":
            ("exited winners early", "🟡"),
        "Traded Against Edge":
            ("traded when system said sit out", "🔴"),
        "Instrument Escalation":
            ("switched to full contract after loss",
             "🚨"),
        "Respected No Edge":
            ("sat out correctly on No Edge days",
             "✅"),
    }

    if all_patterns:
        neg = [(r, PLAIN.get(r[0],
                (r[0], "⚪")))
               for r in all_patterns
               if r[1] != "Positive"]
        pos = [(r, PLAIN.get(r[0],
                (r[0], "✅")))
               for r in all_patterns
               if r[1] == "Positive"]

        if neg:
            st.markdown("**Patterns to address:**")
            for r, (desc, emoji) in neg:
                btype = r[0]
                cnt   = int(r[2])
                cost  = float(r[3] or 0)
                sev   = r[1]
                cost_txt = (
                    f" — cost **${abs(cost):.0f}**"
                    if cost < -5
                    else f" — made **${cost:.0f}**"
                    if cost > 5
                    else "")

                sev_color = {
                    "Critical": "#CC0000",
                    "High":     "#CC3333",
                    "Medium":   "#E65100"
                }.get(sev, "#888")

                st.markdown(
                    f"<div style='padding:10px 14px;"
                    f"border-left:3px solid {sev_color};"
                    f"margin-bottom:8px;"
                    f"background:#FAFAFA;"
                    f"border-radius:0 8px 8px 0;'>"
                    f"<span style='font-size:16px;'>"
                    f"{emoji}</span> "
                    f"<span style='font-size:15px;"
                    f"font-weight:600;color:#1A1A2E;'>"
                    f"You {desc} "
                    f"<span style='color:{sev_color};'>"
                    f"{cnt} times</span>"
                    f"{cost_txt}</span>"
                    f"</div>",
                    unsafe_allow_html=True)

        if pos:
            st.markdown("**Positive patterns:**")
            for r, (desc, emoji) in pos:
                cnt = int(r[2])
                st.markdown(
                    f"<div style='padding:10px 14px;"
                    f"border-left:3px solid #2E7D32;"
                    f"margin-bottom:8px;"
                    f"background:#F1F8F1;"
                    f"border-radius:0 8px 8px 0;'>"
                    f"<span style='font-size:16px;'>"
                    f"{emoji}</span> "
                    f"<span style='font-size:15px;"
                    f"font-weight:600;color:#1A1A2E;'>"
                    f"You {desc} "
                    f"<span style='color:#2E7D32;'>"
                    f"{cnt} times</span>. "
                    f"Good discipline.</span>"
                    f"</div>",
                    unsafe_allow_html=True)
    else:
        st.info(
            "No behavioral data yet for "
            "this period. Log trades to "
            "build your profile.")

    st.divider()

    # ── SECTION 2: Emotion vs Performance ─────
    st.markdown("### 😊 Emotion vs Performance")
    st.caption(
        "Your win rate and average P&L "
        "by emotional state at entry. "
        "Lower emotion = better trading.")

    if em_perf:
        for r in em_perf:
            band   = r[0]
            trades = int(r[1])
            wins   = int(r[2] or 0)
            avg_p  = float(r[3] or 0)
            wr     = round(wins/trades*100) \
                if trades > 0 else 0

            color = ("#2E7D32" if wr >= 60
                     else "#E65100" if wr >= 45
                     else "#CC0000")

            bar_w = int(wr * 1.5)

            st.markdown(
                f"<div style='display:flex;"
                f"align-items:center;gap:12px;"
                f"padding:6px 0;"
                f"border-bottom:1px solid #eee;'>"
                f"<span style='width:110px;"
                f"font-size:13px;color:#555;'>"
                f"{band}</span>"
                f"<div style='flex:1;background:#eee;"
                f"border-radius:4px;height:8px;'>"
                f"<div style='width:{bar_w}px;"
                f"max-width:150px;"
                f"background:{color};"
                f"height:8px;border-radius:4px;'>"
                f"</div></div>"
                f"<span style='width:45px;"
                f"font-size:14px;font-weight:700;"
                f"color:{color};'>{wr}%</span>"
                f"<span style='color:#888;"
                f"font-size:12px;width:100px;'>"
                f"{trades} trades · "
                f"${avg_p:+.0f} avg</span>"
                f"</div>",
                unsafe_allow_html=True)

        # Key insight
        if len(em_perf) >= 2:
            calm = next((r for r in em_perf
                        if "Calm" in r[0] or
                        "Focused" in r[0]), None)
            high = next((r for r in reversed(
                        em_perf)
                        if "High" in r[0] or
                        "Extreme" in r[0]), None)
            if calm and high:
                calm_wr = round(int(calm[2] or 0)
                    /int(calm[1])*100)
                high_wr = round(int(high[2] or 0)
                    /int(high[1])*100)
                diff = calm_wr - high_wr
                if diff > 10:
                    st.markdown(
                        f"<div style='background:"
                        f"#E8F5E9;border-radius:8px;"
                        f"padding:10px 14px;"
                        f"margin-top:10px;"
                        f"font-size:14px;"
                        f"font-weight:600;'>"
                        f"💡 You win {diff}% more "
                        f"when calm vs emotional. "
                        f"Calm = your edge.</div>",
                        unsafe_allow_html=True)
    else:
        st.info(
            "Log trades with emotion scores "
            "to see this analysis.")

    st.divider()

    # ── SECTION 3: Weekly Archive ─────────────
    st.markdown("### 📅 Weekly Archive")
    st.caption(
        "Behavioral patterns by week. "
        "Are you improving over time?")

    if weekly:
        # Group by week
        weeks = {}
        for r in weekly:
            wk = str(r[0])[:10]
            if wk not in weeks:
                weeks[wk] = []
            weeks[wk].append(r)

        for wk, events in list(weeks.items())[:8]:
            # Week date range
            wk_date = date.fromisoformat(wk)
            wk_end  = wk_date + timedelta(days=6)
            total_violations = sum(
                int(e[2]) for e in events)
            total_cost = sum(
                float(e[3] or 0) for e in events)

            with st.expander(
                f"Week of {wk_date.strftime('%b %d')} "
                f"— {wk_end.strftime('%b %d, %Y')} "
                f"| {total_violations} issues "
                f"| ${abs(total_cost):.0f} cost"):
                for e in events:
                    btype = e[1]
                    cnt   = int(e[2])
                    cost  = float(e[3] or 0)
                    plain = PLAIN.get(
                        btype, (btype, "⚪"))
                    cost_txt = (
                        f" — ${abs(cost):.0f} cost"
                        if cost < -5 else "")
                    st.markdown(
                        f"{plain[1]} You "
                        f"**{plain[0]}** "
                        f"{cnt} times"
                        f"{cost_txt}")
    else:
        st.info("No pattern history yet.")

    st.divider()

    # ── SECTION 4: Most Dangerous Patterns ────
    st.markdown("### 🚨 Most Dangerous Patterns")
    st.caption(
        "Ranked by financial impact. "
        "These are the habits worth "
        "fixing first.")

    try:
        with engine.connect() as conn:
            dangerous = conn.execute(text("""
                SELECT behavior_type,
                       COUNT(*) as cnt,
                       SUM(financial_cost) as cost,
                       AVG(financial_cost) as avg_cost
                FROM behavioral_events
                WHERE market='US'
                AND user_id=:uid
                AND severity != 'Positive'
                AND financial_cost < 0
                GROUP BY behavior_type
                ORDER BY SUM(financial_cost) ASC
                LIMIT 5
            """), {"uid": uid}).fetchall()

        if dangerous:
            for i, r in enumerate(dangerous, 1):
                btype    = r[0]
                cnt      = int(r[1])
                cost     = float(r[2] or 0)
                avg_cost = float(r[3] or 0)
                plain    = PLAIN.get(
                    btype, (btype, "⚪"))
                st.markdown(
                    f"<div style='padding:12px 16px;"
                    f"background:#FFF5F5;"
                    f"border-radius:8px;"
                    f"margin-bottom:8px;"
                    f"border-left:4px solid #CC0000;'>"
                    f"<div style='font-size:16px;"
                    f"font-weight:800;color:#CC0000;'>"
                    f"#{i} {plain[1]} "
                    f"{btype}</div>"
                    f"<div style='font-size:14px;"
                    f"color:#333;margin-top:4px;'>"
                    f"You {plain[0]} "
                    f"**{cnt} times** — "
                    f"total cost: "
                    f"**${abs(cost):.0f}** "
                    f"(avg ${abs(avg_cost):.0f} "
                    f"per occurrence)</div>"
                    f"</div>",
                    unsafe_allow_html=True)
        else:
            st.success(
                "✅ No costly patterns detected. "
                "Keep it up.")

    except Exception as e:
        st.info("No cost data yet.")
    st.divider()

    # ── SECTION 5: Emotional Trader Profile ──
    st.markdown("### 🥧 Emotional Trader Profile")
    st.caption(
        "Breakdown of all behavioral patterns. "
        "What percentage of your trading "
        "is driven by each emotion?")

    try:
        with engine.connect() as conn:
            pie_data = conn.execute(text("""
                SELECT behavior_type,
                       COUNT(*) as cnt
                FROM behavioral_events
                WHERE market='US'
                AND user_id=:uid
                AND severity != 'Positive'
                AND event_date >= :start
                GROUP BY behavior_type
                ORDER BY cnt DESC
            """), {
                "uid":   uid,
                "start": str(start_date)
            }).fetchall()

        if pie_data:
            total_events = sum(
                int(r[1]) for r in pie_data)

            # Color map per pattern
            COLORS = {
                "Revenge Trading":    "#CC0000",
                "FOMO":               "#FF6B35",
                "Overtrading":        "#FFA500",
                "Greed":              "#FFD700",
                "Boredom Trading":    "#4ECDC4",
                "Hesitant Trading":   "#9B59B6",
                "Rule Violation":     "#E74C3C",
                "Traded Against Edge":"#95A5A6",
                "Instrument Escalation":"#2C3E50",
                "Tilt":               "#C0392B",
            }

            # Draw pie chart using HTML/CSS
            st.markdown(
                "<div style='display:flex;"
                "flex-wrap:wrap;gap:8px;"
                "margin-bottom:16px;'>",
                unsafe_allow_html=True)

            # Build segments display
            segments = []
            for r in pie_data:
                btype = r[0]
                cnt   = int(r[1])
                pct   = round(cnt/total_events*100)
                color = COLORS.get(btype, "#888")
                plain = PLAIN.get(
                    btype, (btype, "⚪"))
                segments.append((
                    btype, cnt, pct,
                    color, plain))

            # Visual bar representation
            st.markdown(
                "<div style='width:100%;"
                "height:32px;border-radius:8px;"
                "overflow:hidden;display:flex;"
                "margin-bottom:12px;'>",
                unsafe_allow_html=True)

            for btype, cnt, pct, color, plain                     in segments:
                if pct > 0:
                    st.markdown(
                        f"<div style='width:{pct}%;"
                        f"background:{color};"
                        f"height:32px;"
                        f"display:flex;"
                        f"align-items:center;"
                        f"justify-content:center;"
                        f"font-size:11px;"
                        f"color:white;"
                        f"font-weight:700;'>"
                        f"{pct}%"
                        f"</div>",
                        unsafe_allow_html=True)

            st.markdown(
                "</div>", unsafe_allow_html=True)

            # Legend
            for btype, cnt, pct, color, plain                     in segments:
                st.markdown(
                    f"<div style='display:flex;"
                    f"align-items:center;"
                    f"gap:10px;padding:6px 0;"
                    f"border-bottom:"
                    f"1px solid #F0F0F0;'>"
                    f"<div style='width:14px;"
                    f"height:14px;border-radius:3px;"
                    f"background:{color};"
                    f"flex-shrink:0;'></div>"
                    f"<span style='flex:1;"
                    f"font-size:14px;color:#333;'>"
                    f"{plain[1]} {btype}</span>"
                    f"<span style='font-weight:700;"
                    f"color:{color};"
                    f"font-size:15px;'>{pct}%"
                    f"</span>"
                    f"<span style='color:#888;"
                    f"font-size:12px;"
                    f"width:60px;text-align:right;'>"
                    f"{cnt}x</span>"
                    f"</div>",
                    unsafe_allow_html=True)

            # Dominant emotion callout
            if segments:
                top = segments[0]
                st.markdown(
                    f"<div style='background:"
                    f"{top[3]}15;"
                    f"border-left:4px solid "
                    f"{top[3]};"
                    f"border-radius:0 8px 8px 0;"
                    f"padding:12px 16px;"
                    f"margin-top:12px;'>"
                    f"<div style='font-size:15px;"
                    f"font-weight:700;"
                    f"color:{top[3]};'>"
                    f"Dominant pattern: "
                    f"{top[4][1]} {top[0]}"
                    f"</div>"
                    f"<div style='font-size:13px;"
                    f"color:#555;margin-top:4px;'>"
                    f"{top[2]}% of all behavioral "
                    f"events — {top[1]} occurrences. "
                    f"This is your primary pattern "
                    f"to address.</div>"
                    f"</div>",
                    unsafe_allow_html=True)
        else:
            st.info(
                "No behavioral data yet. "
                "Log trades to build your "
                "emotional profile.")

    except Exception as e:
        st.error(f"Chart error: {e}")


