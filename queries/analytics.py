# ── Analytics queries ────────────
import streamlit as st
from db import get_engine
from datetime import date, timedelta
from sqlalchemy import text

def get_expectancy(days_back=30):
    start = date.today() - timedelta(days=days_back)
    try:
        with get_engine().connect() as conn:
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN pnl>0
                        THEN 1 ELSE 0 END) as wins,
                    AVG(CASE WHEN pnl>0
                        THEN pnl END) as avg_win,
                    AVG(CASE WHEN pnl<0
                        THEN pnl END) as avg_loss,
                    SUM(pnl) as total_pnl
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                AND trade_date >= :start
            """), {"start": str(start), "uid": st.session_state.get("user_id",1)}).fetchone()

        if not result or not result[0]:
            return None

        total     = int(result[0])
        wins      = int(result[1] or 0)
        avg_win   = float(result[2] or 0)
        avg_loss  = float(result[3] or 0)
        total_pnl = float(result[4] or 0)

        if total == 0:
            return None

        wr         = wins / total
        lr         = 1 - wr
        expectancy = (wr*avg_win) + (lr*avg_loss)

        return {
            "total":      total,
            "wins":       wins,
            "losses":     total - wins,
            "win_rate":   round(wr*100,1),
            "avg_win":    round(avg_win,2),
            "avg_loss":   round(avg_loss,2),
            "expectancy": round(expectancy,2),
            "total_pnl":  round(total_pnl,2)
        }
    except:
        return None

def get_time_analysis():
    try:
        with get_engine().connect() as conn:
            result = conn.execute(text("""
                SELECT
                    CASE
                        WHEN entry_time_actual < '09:45'
                            THEN '09:30-09:45'
                        WHEN entry_time_actual < '10:00'
                            THEN '09:45-10:00'
                        WHEN entry_time_actual < '10:30'
                            THEN '10:00-10:30'
                        WHEN entry_time_actual < '11:00'
                            THEN '10:30-11:00'
                        WHEN entry_time_actual < '12:00'
                            THEN '11:00-12:00'
                        WHEN entry_time_actual < '14:00'
                            THEN '12:00-14:00'
                        WHEN entry_time_actual < '15:00'
                            THEN '14:00-15:00'
                        ELSE '15:00-16:00'
                    END as bucket,
                    COUNT(*) as trades,
                    SUM(CASE WHEN pnl>0
                        THEN 1 ELSE 0 END) as wins,
                    ROUND(AVG(pnl)::numeric,2) as avg_pnl
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                AND entry_time_actual IS NOT NULL
                GROUP BY bucket
                ORDER BY bucket
            """), {"uid": st.session_state.get("user_id",1)}).fetchall()
            return result
    except:
        return []

def get_setup_analysis():
    try:
        with get_engine().connect() as conn:
            result = conn.execute(text("""
                SELECT setup_type,
                       COUNT(*) as trades,
                       SUM(CASE WHEN pnl>0
                           THEN 1 ELSE 0 END) as wins,
                       ROUND(SUM(pnl)::numeric,2)
                           as total_pnl,
                       ROUND(AVG(pnl)::numeric,2)
                           as avg_pnl
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                AND setup_type IS NOT NULL
                GROUP BY setup_type
                ORDER BY total_pnl DESC
            """), {"uid": st.session_state.get("user_id",1)}).fetchall()
            return result
    except:
        return []

def get_account_breakdown():
    try:
        with get_engine().connect() as conn:
            result = conn.execute(text("""
                SELECT tj.account_type,
                       be.behavior_type,
                       COUNT(*) as cnt,
                       SUM(be.financial_cost) as cost
                FROM behavioral_events be
                JOIN trade_journal tj
                    ON be.trade_id = tj.id
                WHERE tj.market='US'
                AND be.event_date >= :start
                GROUP BY tj.account_type,
                         be.behavior_type
                ORDER BY tj.account_type, cnt DESC
            """), {
                "start": str(
                    date.today()-timedelta(days=30))
            }).fetchall()
            return result
    except:
        return []

def get_drawdown():
    try:
        with get_engine().connect() as conn:
            result = conn.execute(text("""
                SELECT SUM(pnl) OVER (
                    ORDER BY trade_date,
                             created_at
                ) as cumulative_pnl
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                ORDER BY trade_date, created_at
            """), {"uid": st.session_state.get("user_id",1)}).fetchall()

        if not result:
            return None

        cum_pnls = [float(r[0]) for r in result]
        peak     = max(cum_pnls) if cum_pnls else 0
        current  = cum_pnls[-1] if cum_pnls else 0
        drawdown = current - peak

        return {
            "peak":         round(peak,2),
            "current":      round(current,2),
            "drawdown":     round(drawdown,2),
            "drawdown_pct": round(
                drawdown/peak*100,1
            ) if peak != 0 else 0
        }
    except:
        return None

# ══════════════════════════════════════════════════════════════
# BEHAVIORAL DETECTION ENGINE
# ══════════════════════════════════════════════════════════════
def get_weekly_report():
    """
    Weekly behavioral summary Mon-Fri.
    Shows patterns, scores, P&L, forward test.
    Auto-generates next week focus.
    """
    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    try:
        with get_engine().connect() as conn:
            trades = conn.execute(text("""
                SELECT COUNT(*),
                       SUM(CASE WHEN pnl>0
                           THEN 1 ELSE 0 END),
                       SUM(pnl),
                       AVG(emotional_state),
                       SUM(CASE WHEN pnl<0
                           THEN 1 ELSE 0 END),
                       SUM(CASE WHEN checked_system
                           THEN 1 ELSE 0 END),
                       SUM(CASE WHEN followed_plan
                           THEN 1 ELSE 0 END)
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                AND trade_date BETWEEN :mon AND :fri
            """), {
                "mon": str(monday),
                "fri": str(friday)
            , "uid": st.session_state.get("user_id",1)}).fetchone()

            behaviors = conn.execute(text("""
                SELECT behavior_type,
                       COUNT(*) as cnt,
                       SUM(financial_cost) as cost
                FROM behavioral_events
                WHERE market='US'
                AND user_id=:uid
                AND event_date BETWEEN :mon AND :fri
                GROUP BY behavior_type
                ORDER BY cnt DESC
            """), {
                "mon": str(monday),
                "fri": str(friday)
            , "uid": st.session_state.get("user_id",1)}).fetchall()

            scores = conn.execute(text("""
                SELECT score_date, overall_score,
                       behavioral_state
                FROM behavioral_scores
                WHERE market='US'
                AND score_date BETWEEN :mon AND :fri
                ORDER BY score_date ASC
            """), {
                "mon": str(monday),
                "fri": str(friday)
            }).fetchall()

            fwd = conn.execute(text("""
                SELECT DISTINCT ON (log_date)
                    log_date, was_correct,
                    predicted_bias, actual_bias
                FROM learning_log
                WHERE market='US'
                AND predicted_bias != 'Historical'
                AND log_date BETWEEN :mon AND :fri
                ORDER BY log_date, logged_at DESC
            """), {
                "mon": str(monday),
                "fri": str(friday)
            }).fetchall()

            last_mon = monday - timedelta(days=7)
            last_fri = friday - timedelta(days=7)
            last_sc  = conn.execute(text("""
                SELECT AVG(overall_score)
                FROM behavioral_scores
                WHERE market='US'
                AND score_date BETWEEN :mon AND :fri
            """), {
                "mon": str(last_mon),
                "fri": str(last_fri)
            }).fetchone()

        return {
            "week_start":    monday,
            "week_end":      friday,
            "trades":        trades,
            "behaviors":     behaviors,
            "scores":        scores,
            "fwd_test":      fwd,
            "last_week_avg": float(last_sc[0])
                             if last_sc and last_sc[0]
                             else None
        }

    except:
        return None


def score_color(score):
    if score >= 80: return "#0066CC"
    if score >= 65: return "#4CAF50"
    if score >= 50: return "#FF8C00"
    if score >= 35: return "#FF5722"
    return "#CC0000"


