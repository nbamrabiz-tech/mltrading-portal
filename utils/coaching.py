# ── Coaching utilities ───────────
import streamlit as st
from datetime import date, timedelta
from sqlalchemy import text

def generate_coaching_brief(events_b, scores_b,
                             today_t, report):
    """
    Plain English coaching brief.
    One insight maximum.
    Dollar amounts always included.
    Short and actionable.
    """
    insights = []

    # ── Behavioral patterns ───────────────────────
    PLAIN = {
        "Revenge Trading": (
            "traded too soon after a loss",
            "30 min break after every loss"),
        "Overtrading": (
            "took too many trades",
            "max 3 trades per day"),
        "Rule Violation": (
            "skipped pre-trade checks",
            "check system before every trade"),
        "Emotional Exit": (
            "exited on emotion not your plan",
            "set your exit before you enter"),
        "FOMO": (
            "chased price without a setup",
            "wait for price to come to you"),
        "Traded Against Edge": (
            "traded when system said sit out",
            "trust the No Edge signal"),
        "Wrong Setup for Day": (
            "used wrong strategy for the day type",
            "match your setup to today's edge"),
        "Respected No Edge": (
            "sat out correctly",
            "keep it up"),
    }

    if events_b:
        # Find most costly pattern first
        costly = sorted(events_b,
            key=lambda x: abs(float(x[2] or 0)),
            reverse=True)

        for e in costly[:3]:
            btype = e[0]
            count = int(e[1])
            cost  = float(e[2] or 0)
            plain = PLAIN.get(btype)
            if not plain:
                continue

            action_desc, fix = plain
            positive = btype == "Respected No Edge"

            if positive:
                insights.append(
                    f"You {action_desc} "
                    f"{count}x this month. "
                    f"Discipline is building.")
            elif cost < -20:
                insights.append(
                    f"You {action_desc} "
                    f"{count}x this month — "
                    f"costing you "
                    f"${abs(cost):.0f}. "
                    f"Fix: {fix}.")
            else:
                insights.append(
                    f"You {action_desc} "
                    f"{count}x this month. "
                    f"No cost yet — "
                    f"but catch this early. "
                    f"Fix: {fix}.")

    # ── Score trend ───────────────────────────────
    if not insights and scores_b and \
            len(scores_b) >= 3:
        recent = [int(s[0]) for s in scores_b[:3]]
        older  = [int(s[0]) for s in scores_b[3:]]
        if older:
            avg_r = sum(recent)/len(recent)
            avg_o = sum(older)/len(older)
            if avg_r > avg_o + 5:
                insights.append(
                    "Your discipline score is "
                    "improving this week. "
                    "Keep the momentum.")
            elif avg_r < avg_o - 5:
                insights.append(
                    "Your discipline score "
                    "dropped this week. "
                    "What changed?")

    # ── Fallback ──────────────────────────────────
    if not insights:
        insights.append(
            "Log every trade to build "
            "your personal coaching insight.")

    # Return first insight only — keep it simple
    return insights[0] if insights else ""


def generate_signal_summary(report):
    """
    Plain English signal summary.
    Analytical but readable.
    """
    if not report:
        return ""

    edge      = report.get("confidence",
                report.get("edge","No Edge"))
    up_pct    = report.get("up_pct", 33)
    down_pct  = report.get("down_pct", 33)
    range_pct = report.get("range_pct", 33)
    matrix    = report.get("matrix","?")
    total     = report.get("total_days",
                report.get("score", 0))

    narr_map = {
        "B": "bullish news flow",
        "R": "bearish news flow",
        "C": "mixed signals",
        "W": "market waiting on catalyst",
        "U": "geopolitical uncertainty",
        "N": "quiet — no major catalyst"
    }
    narrative = report.get("narrative","C")
    narr_desc = narr_map.get(
        str(narrative).upper(), "mixed signals")

    if "Long Bias" in str(edge):
        direction = "rally"
        dominant_pct = up_pct
        action = "Look for long setups " \
                 "with the trend."
    elif "Short Bias" in str(edge):
        direction = "sell off"
        dominant_pct = down_pct
        action = "Look for short setups " \
                 "with the trend."
    elif "Range" in str(edge):
        direction = "stay range bound"
        dominant_pct = range_pct
        action = "Range trade between " \
                 "key levels or sit out."
    else:
        # No Edge
        dominant = max(
            [("range bound", range_pct),
             ("sell off", down_pct),
             ("rally", up_pct)],
            key=lambda x: x[1])
        return (
            f"On days like today with "
            f"{narr_desc}, markets "
            f"{dominant[0]} {dominant[1]}% "
            f"of the time. "
            f"No clear edge — "
            f"sitting out protects capital.")

    return (
        f"On days like today with "
        f"{narr_desc}, markets "
        f"{direction} {dominant_pct}% "
        f"of the time. {action}")

# ══════════════════════════════════════════════════════════════
# STYLE HELPERS
# ══════════════════════════════════════════════════════════════
