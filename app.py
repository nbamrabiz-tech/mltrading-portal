# ══════════════════════════════════════════════════════════════
# MLTrading System — Portal v6
# Full behavioral layer + R:R + quantity + hold time
# ══════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from datetime import datetime, date, timedelta
import pytz

st.set_page_config(
    page_title="MLTrading Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

EST = pytz.timezone("America/New_York")

@st.cache_resource
def get_engine():
    pw = quote_plus(st.secrets["SUPABASE_PASSWORD"])
    return create_engine(
        f"postgresql://postgres.hjcmfkllwarrqougwdiy:{pw}"
        f"@aws-0-ca-central-1.pooler.supabase.com"
        f":6543/postgres",
        pool_pre_ping=True
    )

engine = get_engine()

def get_last_trading_day():
    today   = datetime.now(EST).date()
    weekday = today.weekday()
    if weekday == 5:   return today - timedelta(days=1)
    elif weekday == 6: return today - timedelta(days=2)
    return today

# ══════════════════════════════════════════════════════════════
# DATA FUNCTIONS
# ══════════════════════════════════════════════════════════════
def get_latest_report():
    today = get_last_trading_day()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT * FROM intelligence_reports
                WHERE market='US' AND report_date=:td
                ORDER BY created_at DESC LIMIT 1
            """), {"td": str(today)})
            row = result.fetchone()
            if row:
                return dict(zip(result.keys(), row))
            result = conn.execute(text("""
                SELECT * FROM intelligence_reports
                WHERE market='US'
                ORDER BY report_date DESC,
                         created_at DESC LIMIT 1
            """))
            row = result.fetchone()
            if row:
                return dict(zip(result.keys(), row))
    except:
        pass
    return None

def get_todays_events():
    today = get_last_trading_day()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT ON (event_type)
                    event_type, actual_value,
                    previous_value, impact_score
                FROM economic_events
                WHERE market='US' AND event_date=:td
                AND impact_score IN ('High','Medium')
                ORDER BY event_type, id DESC
            """), {"td": str(today)})
            return result.fetchall()
    except:
        return []

def get_spy_levels():
    today = get_last_trading_day()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT ticker,
                       CAST(high AS FLOAT),
                       CAST(low AS FLOAT),
                       CAST(close AS FLOAT)
                FROM price_data
                WHERE market='US'
                AND ticker IN ('SPY','QQQ')
                AND timeframe='1d'
                AND DATE(timestamp) < :td
                ORDER BY ticker, timestamp DESC
            """), {"td": str(today)})
            rows = result.fetchall()
            levels = {}
            seen = set()
            for r in rows:
                if r[0] not in seen:
                    levels[r[0]] = {
                        "pdh": round(float(r[1]),2),
                        "pdl": round(float(r[2]),2),
                        "pdc": round(float(r[3]),2)
                    }
                    seen.add(r[0])
            return levels
    except:
        return {}

def get_learning_log():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT ON (log_date)
                    log_date, predicted_bias,
                    actual_bias, actual_return,
                    was_correct, matrix_score
                FROM learning_log
                WHERE market='US'
                AND predicted_bias != 'Historical'
                ORDER BY log_date DESC,
                         logged_at DESC
                LIMIT 60
            """))
            rows = result.fetchall()
            if rows:
                return pd.DataFrame(rows,
                    columns=["date","predicted",
                             "actual","return",
                             "correct","score"])
    except:
        pass
    return pd.DataFrame()

def get_trade_journal(days_back=30):
    start = date.today() - timedelta(days=days_back)
    uid = st.session_state.get("user_id", 1)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, trade_date, trade_time,
                       ticker, direction,
                       entry_price, exit_price,
                       stop_price, planned_target,
                       pnl, pnl_r,
                       emotional_state,
                       followed_plan,
                       setup_type, mistake,
                       account_type,
                       checked_system,
                       pre_trade_gate,
                       size_contracts,
                       entry_time_actual,
                       exit_time,
                       exit_type,
                       exit_reason,
                       exit_reason_type,
                       post_exit_result
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                AND trade_date >= :start
                ORDER BY trade_date DESC,
                         created_at DESC
                LIMIT 100
            """), {
                "start": str(start),
                "uid": uid
            })
            return result.fetchall()
    except:
        return []

def get_behavioral_data(uid=None):
    start = date.today() - timedelta(days=30)
    if uid is None:
        uid = st.session_state.get("user_id", 1)
    try:
        with engine.connect() as conn:
            events = conn.execute(text("""
                SELECT behavior_type,
                       COUNT(*) as cnt,
                       SUM(financial_cost) as cost
                FROM behavioral_events
                WHERE market='US'
                AND user_id=:uid
                AND event_date >= :start
                GROUP BY behavior_type
                ORDER BY cnt DESC LIMIT 10
            """), {
                "start": str(start),
                "uid": uid
            }).fetchall()

            scores = conn.execute(text("""
                SELECT overall_score,
                       behavioral_state,
                       score_date
                FROM behavioral_scores
                WHERE market='US'
                ORDER BY score_date DESC LIMIT 7
            """)).fetchall()

            today_b = conn.execute(text("""
                SELECT behavior_type, severity,
                       description,
                       COUNT(*) as cnt
                FROM behavioral_events
                WHERE market='US'
                AND user_id=:uid
                AND event_date=:td
                GROUP BY behavior_type,
                         severity, description
                LIMIT 10
            """), {
                "td": str(date.today()),
                "uid": uid
            }).fetchall()

            today_t = conn.execute(text("""
                SELECT COUNT(*),
                       SUM(CASE WHEN pnl>0
                           THEN 1 ELSE 0 END),
                       SUM(pnl),
                       AVG(emotional_state),
                       SUM(CASE WHEN pnl<0
                           THEN 1 ELSE 0 END)
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                AND trade_date=:td
            """), {
                "td": str(date.today()),
                "uid": uid
            }).fetchone()

        return events, scores, today_b, today_t
    except:
        return [], [], [], None

def get_expectancy(days_back=30):
    start = date.today() - timedelta(days=days_back)
    try:
        with engine.connect() as conn:
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
        with engine.connect() as conn:
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
        with engine.connect() as conn:
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
        with engine.connect() as conn:
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
        with engine.connect() as conn:
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
def calculate_daily_score(target_date=None):
    """
    0-100 composite behavioral score.
    5 components weighted by importance.
    Saves to behavioral_scores table.
    Returns score dict or None if no trades.

    Component breakdown:
    1. System adherence  25 pts — checked system?
    2. Rule adherence    25 pts — followed plan?
    3. Emotion control   20 pts — avg emotion level
    4. Trade discipline  20 pts — trade count + losses
    5. Behavior penalty  10 pts — high severity events
    """
    if target_date is None:
        target_date = date.today()

    try:
        with engine.connect() as conn:
            trades = conn.execute(text("""
                SELECT pnl, emotional_state,
                       followed_plan, checked_system,
                       pre_trade_gate, created_at
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                AND trade_date=:td
                ORDER BY created_at ASC
            """), {
                "td":  str(target_date),
                "uid": st.session_state.get("user_id",1)
            }).fetchall()

            behaviors = conn.execute(text("""
                SELECT behavior_type, severity
                FROM behavioral_events
                WHERE market='US'
                AND user_id=:uid
                AND event_date=:td
            """), {"td": str(target_date), "uid": st.session_state.get("user_id",1)}).fetchall()

        if not trades:
            return None

        total        = len(trades)
        pnls         = [float(t[0]) for t in trades]
        emotions     = [int(t[1]) for t in trades]
        plans        = [bool(t[2]) for t in trades]
        systems      = [bool(t[3]) for t in trades]
        losses       = sum(1 for p in pnls if p < 0)
        hi_behaviors = sum(1 for b in behaviors
                           if b[1] == "High")

        # Component 1 — System adherence (25 pts)
        sys_rate = sum(systems) / total
        if sys_rate == 1.0:    sys_score = 25
        elif sys_rate >= 0.75: sys_score = 18
        elif sys_rate >= 0.5:  sys_score = 10
        else:                  sys_score = 0

        # Component 2 — Rule adherence (25 pts)
        plan_rate = sum(plans) / total
        if plan_rate == 1.0:    plan_score = 25
        elif plan_rate >= 0.75: plan_score = 18
        elif plan_rate >= 0.5:  plan_score = 10
        else:                   plan_score = 0

        # Component 3 — Emotion control (20 pts)
        avg_emotion = sum(emotions) / total
        if avg_emotion <= 4:   emo_score = 20
        elif avg_emotion <= 5: emo_score = 17
        elif avg_emotion <= 6: emo_score = 12
        elif avg_emotion <= 7: emo_score = 6
        else:                  emo_score = 0

        # Component 4 — Trade discipline (20 pts)
        if losses >= 2:  disc_score = 0
        elif total <= 3: disc_score = 20
        elif total == 4: disc_score = 12
        elif total == 5: disc_score = 6
        else:            disc_score = 0

        # Component 5 — Behavior penalty (10 pts)
        if hi_behaviors == 0:   beh_score = 10
        elif hi_behaviors == 1: beh_score = 5
        else:                   beh_score = 0

        total_score = (sys_score + plan_score +
                       emo_score + disc_score +
                       beh_score)

        if total_score >= 80:   state = "Excellent"
        elif total_score >= 65: state = "Good"
        elif total_score >= 50: state = "Fair"
        elif total_score >= 35: state = "Poor"
        else:                   state = "Critical"

        # Save to behavioral_scores
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO behavioral_scores(
                    market, score_date,
                    overall_score,
                    behavioral_state,
                    total_trades,
                    system_adherence_score,
                    rule_adherence_score,
                    emotion_control_score,
                    discipline_score)
                VALUES('US',:sd,:os,:bs,
                       :tt,:ss,:rs,:es,:ds)
                ON CONFLICT (market, score_date)
                DO UPDATE SET
                    overall_score=:os,
                    behavioral_state=:bs,
                    total_trades=:tt,
                    system_adherence_score=:ss,
                    rule_adherence_score=:rs,
                    emotion_control_score=:es,
                    discipline_score=:ds
            """), {
                "sd": str(target_date),
                "os": total_score,
                "bs": state,
                "tt": total,
                "ss": sys_score,
                "rs": plan_score,
                "es": emo_score,
                "ds": disc_score
            })
            conn.commit()

        return {
            "score":        total_score,
            "state":        state,
            "total":        total,
            "sys_score":    sys_score,
            "plan_score":   plan_score,
            "emo_score":    emo_score,
            "disc_score":   disc_score,
            "beh_score":    beh_score,
            "avg_emotion":  round(avg_emotion, 1),
            "losses":       losses,
            "hi_behaviors": hi_behaviors
        }

    except Exception as e:
        return None


def get_streaks():
    """
    Detects win/loss streaks from trade journal.
    Also detects prediction streaks from learning log.
    Returns streak info and warnings.
    """
    result = {
        "trade_streak":      0,
        "trade_streak_type": None,
        "pred_streak":       0,
        "pred_streak_type":  None,
        "warnings":          []
    }

    try:
        # Trade streaks
        with engine.connect() as conn:
            trades = conn.execute(text("""
                SELECT pnl, trade_date
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                ORDER BY trade_date DESC,
                         created_at DESC
                LIMIT 20
            """), {"uid": st.session_state.get("user_id",1)}).fetchall()

        if trades:
            first_pnl    = float(trades[0][0])
            current_type = "Win" if first_pnl > 0 \
                           else "Loss"
            streak = 0

            for t in trades:
                pnl       = float(t[0])
                this_type = "Win" if pnl > 0 else "Loss"
                if this_type == current_type:
                    streak += 1
                else:
                    break

            result["trade_streak"]      = streak
            result["trade_streak_type"] = current_type

            if current_type == "Loss" and streak >= 3:
                result["warnings"].append(
                    f"⛔ {streak} loss streak. "
                    f"STOP TRADING TODAY. "
                    f"Come back tomorrow fresh."
                )
            elif current_type == "Loss" and streak >= 2:
                result["warnings"].append(
                    f"🔴 {streak} consecutive losses. "
                    f"Revenge risk is HIGH. "
                    f"30 min break before next trade."
                )
            elif current_type == "Win" and streak >= 3:
                result["warnings"].append(
                    f"⚠️ {streak} win streak. "
                    f"Overconfidence risk. "
                    f"Do not increase size."
                )

        # Prediction streaks — exclude No Edge days
        with engine.connect() as conn:
            preds = conn.execute(text("""
                SELECT was_correct, trade_date
                FROM forward_test_log
                WHERE market='US'
                AND was_correct IS NOT NULL
                AND edge != 'No Edge'
                AND actual_bias IS NOT NULL
                ORDER BY trade_date DESC
                LIMIT 30
            """)).fetchall()

        if preds:
            first_correct = bool(preds[0][0])
            pred_type     = "Correct" \
                            if first_correct \
                            else "Incorrect"
            pred_streak   = 0

            for p in preds:
                if p[0] is None:
                    continue  # Skip No Edge
                this = bool(p[0])
                if (this and pred_type == "Correct") or \
                   (not this and pred_type == "Incorrect"):
                    pred_streak += 1
                else:
                    break

            result["pred_streak"]      = pred_streak
            result["pred_streak_type"] = pred_type

    except:
        pass

    return result


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
        with engine.connect() as conn:
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



def detect_all_behaviors(trade_id, trade_date,
                          pnl, emotion,
                          followed_plan,
                          checked_system,
                          gate_passed,
                          entry_price, stop_price,
                          exit_price, direction,
                          created_at):
    behaviors = []
    try:
        with engine.connect() as conn:
            todays = conn.execute(text("""
                SELECT id, pnl, created_at,
                       emotional_state,
                       checked_system
                FROM trade_journal
                WHERE trade_date=:td
                AND market='US'
                ORDER BY created_at ASC
            """), {"td": str(trade_date)}).fetchall()

        today_pnls    = [float(t[1]) for t in todays]
        losses_before = sum(
            1 for p in today_pnls[:-1] if p < 0)
        total_trades  = len(todays)

        if not checked_system:
            behaviors.append({
                "type":     "FOMO",
                "severity": "High",
                "desc":     "Entered without checking "
                            "system report today.",
                "cost":     min(pnl,0)
            })

        if losses_before >= 1 and pnl < 0:
            behaviors.append({
                "type":     "Revenge Trading",
                "severity": "High"
                            if losses_before >= 2
                            else "Medium",
                "desc":     f"Trade after "
                            f"{losses_before} loss(es)."
                            f" Revenge pattern.",
                "cost":     min(pnl,0)
            })

        if not gate_passed:
            behaviors.append({
                "type":     "Rule Violation",
                "severity": "High",
                "desc":     "Pre-trade gate not met.",
                "cost":     min(pnl,0)
            })

        if not followed_plan:
            behaviors.append({
                "type":     "Rule Violation",
                "severity": "Medium",
                "desc":     "Did not follow plan.",
                "cost":     min(pnl,0)*0.5
            })

        if emotion >= 8:
            behaviors.append({
                "type":     "Tilt",
                "severity": "High",
                "desc":     f"Emotion {emotion}/10. "
                            f"Too high to trade.",
                "cost":     min(pnl,0)
            })
        elif emotion >= 6:
            behaviors.append({
                "type":     "Elevated Emotion",
                "severity": "Medium",
                "desc":     f"Emotion {emotion}/10.",
                "cost":     0
            })

        if total_trades > 3:
            behaviors.append({
                "type":     "Overtrading",
                "severity": "Medium",
                "desc":     f"Trade #{total_trades}."
                            f" Win rate drops after 3.",
                "cost":     min(pnl,0)*0.5
            })

        if len(todays) >= 2:
            current  = todays[-1]
            previous = todays[-2]
            try:
                mins = abs((
                    current[2]-previous[2]
                ).total_seconds())/60
                prev_pnl = float(previous[1])

                if prev_pnl < 0 and mins < 30:
                    behaviors.append({
                        "type":     "Revenge Trading",
                        "severity": "High",
                        "desc":     f"{mins:.0f}min "
                                    f"since last loss. "
                                    f"30min required.",
                        "cost":     min(pnl,0)
                    })
                elif prev_pnl >= 0 and mins < 15:
                    behaviors.append({
                        "type":     "Greed",
                        "severity": "Medium",
                        "desc":     f"{mins:.0f}min "
                                    f"since last win. "
                                    f"15min minimum.",
                        "cost":     0
                    })
            except:
                pass

        if behaviors:
            with engine.connect() as conn:
                for b in behaviors:
                    conn.execute(text("""
                        INSERT INTO behavioral_events(
                            market, event_date,
                            trade_id, behavior_type,
                            severity, description,
                            financial_cost)
                        VALUES('US',:td,:tid,
                               :btype,:sev,
                               :desc,:cost)
                    """), {
                        "td":    str(trade_date),
                        "tid":   trade_id,
                        "btype": b["type"],
                        "sev":   b["severity"],
                        "desc":  b["desc"],
                        "cost":  b.get("cost",0)
                    })
                conn.commit()

    except Exception as e:
        st.error(f"Detection error: {e}")

    return behaviors

def check_reentry_timing(trade_date):
    try:
        with engine.connect() as conn:
            last = conn.execute(text("""
                SELECT created_at, pnl
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                AND trade_date=:td
                ORDER BY created_at DESC LIMIT 1
            """), {"td": str(trade_date), "uid": st.session_state.get("user_id",1)}).fetchone()

        if not last:
            return None

        utc  = pytz.utc
        mins = abs((
            datetime.now(utc)-last[0]
        ).total_seconds())/60
        prev_pnl = float(last[1])

        if prev_pnl < 0 and mins < 30:
            rem = round(30-mins)
            return {
                "blocked": True,
                "message": f"⛔ {mins:.0f}min since "
                           f"last LOSS. Wait {rem}min. "
                           f"30min reset required."
            }
        elif mins < 15:
            rem = round(15-mins)
            return {
                "blocked": True,
                "message": f"⚠️ {mins:.0f}min since "
                           f"last trade. Wait {rem}min."
            }
    except:
        pass
    return None

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
def card(content, border_color="#0066CC",
         bg="#F8F9FA"):
    return (
        f'<div style="background:{bg};'
        f'padding:14px;border-radius:8px;'
        f'border-left:4px solid {border_color};'
        f'margin-bottom:8px;">'
        f'{content}</div>'
    )

def prob_bar(pct, color, width=150):
    return (
        f'<div style="background:#E8E8E8;'
        f'border-radius:4px;width:{width}px;'
        f'height:8px;margin-top:4px;">'
        f'<div style="background:{color};'
        f'width:{min(pct,100)}%;height:8px;'
        f'border-radius:4px;"></div></div>'
    )

def edge_color(edge):
    if not edge: return "#888888"
    if "Long Bias"  in edge: return "#0066CC"
    if "Short Bias" in edge: return "#CC0000"
    if "Range Bias" in edge: return "#FF8C00"
    return "#888888"

def candle_color(d):
    if "Bullish" in str(d): return "#0066CC"
    if "Bearish" in str(d): return "#CC0000"
    return "#888888"

def score_color(score):
    if score >= 80: return "#0066CC"
    if score >= 65: return "#4CAF50"
    if score >= 50: return "#FF8C00"
    if score >= 35: return "#FF5722"
    return "#CC0000"

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main():
    now_est = datetime.now(EST)
    today   = get_last_trading_day()

    # ── User selector ─────────────────────────
    if "user_id" not in st.session_state:
        st.session_state.user_id = 1
        st.session_state.username = "sunny"
        st.session_state.display_name = "Sunny"

    try:
        with engine.connect() as conn:
            all_users = conn.execute(text("""
                SELECT id, username,
                       display_name,
                       persona_type,
                       is_test_user
                FROM users
                WHERE is_active=TRUE
                ORDER BY is_test_user ASC, id ASC
            """)).fetchall()

        user_options = {
            f"{'🧪 ' if u[4] else '👤 '}"
            f"{u[2]} ({u[3]})": u
            for u in all_users}

        with st.sidebar:
            st.markdown("**👤 Active User**")
            selected = st.selectbox(
                "View as:",
                list(user_options.keys()),
                index=0,
                key="user_selector")
            selected_user = user_options[selected]

            # Detect user change
            prev_uid = st.session_state.get(
                "prev_user_id", 1)
            new_uid = selected_user[0]
            if prev_uid != new_uid:
                st.session_state.prev_user_id = \
                    new_uid
                st.rerun()

            st.session_state.user_id = \
                selected_user[0]
            st.session_state.username = \
                selected_user[1]
            st.session_state.display_name = \
                selected_user[2]

            STRATEGIES = {
                "marcus_rev":
                    "📈 5-min ORB",
                "james_over":
                    "📊 EMA 9/21 Crossover",
                "sarah_fomo":
                    "🚀 Momentum Chasing",
                "alex_bore":
                    "↔️ Support/Resistance Fade",
                "david_greed":
                    "💰 Intraday Swing",
                "emma_hesit":
                    "📍 FVG Entries",
                "sam_disc":
                    "✅ Rules-Based System",
                "sunny":
                    "🧠 Matrix + No Edge System",
            }

            username = selected_user[1]
            strategy = STRATEGIES.get(
                username, "")

            if selected_user[4]:
                st.caption(
                    f"🧪 {selected_user[3]}")
                if strategy:
                    st.markdown(
                        f"<div style='"
                        f"background:#F0F4FF;"
                        f"border-radius:6px;"
                        f"padding:6px 10px;"
                        f"font-size:12px;"
                        f"font-weight:600;"
                        f"color:#0066CC;'>"
                        f"{strategy}</div>",
                        unsafe_allow_html=True)
            else:
                st.caption("👤 Real user")
                if strategy:
                    st.markdown(
                        f"<div style='"
                        f"background:#F0F4FF;"
                        f"border-radius:6px;"
                        f"padding:6px 10px;"
                        f"font-size:12px;"
                        f"font-weight:600;"
                        f"color:#0066CC;'>"
                        f"{strategy}</div>",
                        unsafe_allow_html=True)

    except Exception as e:
        st.session_state.user_id = 1
        st.sidebar.error(f"User selector: {e}")

    CURRENT_USER_ID = st.session_state.user_id
    CURRENT_USER    = st.session_state.username
    DISPLAY_NAME    = st.session_state.display_name

    st.markdown(
        f"<div style='text-align:center;padding:8px 0;'>"
        f"<h1 style='color:#0066CC;margin:0;"
        f"font-size:26px;'>📊 MLTrading Intelligence</h1>"
        f"<p style='color:#888;margin:0;font-size:12px;'>"
        f"{now_est.strftime('%A %B %d %Y — %H:%M EST')}"
        f" &nbsp;|&nbsp; Trading day: {today}"
        f" &nbsp;|&nbsp; 👤 {DISPLAY_NAME}</p>"
        f"</div>",
        unsafe_allow_html=True
    )
    st.divider()

    tabs = st.tabs([
        "📈 Daily Intelligence",
        "🎯 Decision Support",
        "⚖️ Risk Advisory",
        "😊 Sentiment",
        "👤 My Profile",
        "📊 Analytics",
        "🎯 Forward Test",
        "⚙️ Settings"
    ])

    # ══════════════════════════════════════════════
    # TAB 1 — DAILY INTELLIGENCE
    # ══════════════════════════════════════════════
    with tabs[0]:
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

            if up_pct >= 50:
                dominant="UPTREND";   dc="#0066CC"; de="📈"
            elif down_pct >= 50:
                dominant="DOWNTREND"; dc="#CC0000"; de="📉"
            elif range_pct >= 50:
                dominant="RANGE BOUND";dc="#FF8C00";de="➡️"
            else:
                dominant="NO CLEAR EDGE";dc="#888";de="⚪"

            st.markdown(
                f"<div style='background:{dc}15;"
                f"padding:16px;border-radius:8px;"
                f"border-left:4px solid {dc};"
                f"margin-bottom:16px;text-align:center;'>"
                f"<p style='color:{dc};font-size:28px;"
                f"font-weight:bold;margin:0;'>"
                f"{de} {dominant}</p>"
                f"<p style='color:#666;font-size:13px;"
                f"margin:4px 0 0;'>{conf}</p></div>",
                unsafe_allow_html=True
            )

            c1,c2,c3,c4 = st.columns(4)
            for col, val, label, threshold in [
                (c1, up_pct,    "📈 UPTREND",   50),
                (c2, down_pct,  "📉 DOWNTREND", 50),
                (c3, range_pct, "➡️ RANGE",     50),
                (c4, tp,        "TRADE PROB",   65)
            ]:
                vc = ("#0066CC" if val>=threshold
                      else "#888888")
                if label == "📉 DOWNTREND":
                    vc = ("#CC0000" if val>=threshold
                          else "#888888")
                elif label == "➡️ RANGE":
                    vc = ("#FF8C00" if val>=threshold
                          else "#888888")
                elif label == "TRADE PROB":
                    vc = ("#0066CC" if val>=65
                          else "#CC0000" if val<=35
                          else "#FF8C00")
                col.markdown(card(
                    f'<p style="color:#666;margin:0;'
                    f'font-size:11px;">{label}</p>'
                    f'<p style="color:{vc};margin:4px 0 2px;'
                    f'font-size:28px;font-weight:bold;">'
                    f'{val}%</p>'
                    + prob_bar(val,vc),
                    border_color=vc
                ), unsafe_allow_html=True)

            ec = edge_color(conf)
            st.markdown(card(
                f'<p style="color:#666;font-size:11px;'
                f'margin:0;">EDGE | ACTION</p>'
                f'<p style="color:{ec};font-size:16px;'
                f'font-weight:bold;margin:4px 0 2px;">'
                f'{conf}</p>'
                f'<p style="color:#333;font-size:13px;'
                f'margin:0;">{reaction}</p>',
                border_color=ec
            ), unsafe_allow_html=True)

            st.divider()
            col_l, col_r = st.columns([3,2])

            with col_l:
                st.subheader("📰 Today's Narrative")
                st.markdown(card(
                    f'<p style="color:#333;font-size:14px;'
                    f'line-height:1.6;margin:0;">'
                    f'{narr_hl}</p>'
                ), unsafe_allow_html=True)
                m1,m2 = st.columns(2)
                m1.metric("Event Day",
                    "Yes ★★★" if ie else "No")
                m2.metric("Trade Probability",f"{tp}%")

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
    # TAB 2 — DECISION SUPPORT
    # ══════════════════════════════════════════════
    with tabs[1]:
        st.subheader("🎯 Decision Support")
        report = get_latest_report()
        levels = get_spy_levels()

        if not report:
            st.warning("Run morning script first.")
        else:
            up_pct    = report.get("up_pct",33) or \
                        report.get("matrix_score",33) or 33
            down_pct  = report.get("down_pct",8) or 8
            range_pct = report.get("range_pct",50) or 50
            bias      = report.get("bias","Neutral") or "Neutral"
            conf      = report.get("confidence","") or ""

            sc1,sc2,sc3 = st.columns(3)
            sc1.metric("📈 Uptrend",   f"{up_pct}%")
            sc2.metric("📉 Downtrend", f"{down_pct}%")
            sc3.metric("➡️ Range",     f"{range_pct}%")

            ec = edge_color(conf)
            st.markdown(card(
                f'<p style="color:#666;font-size:11px;'
                f'margin:0;">EDGE</p>'
                f'<p style="color:{ec};font-size:18px;'
                f'font-weight:bold;margin:4px 0 0;">'
                f'{conf}</p>',
                border_color=ec
            ), unsafe_allow_html=True)

            st.divider()
            st.markdown("### Key Levels")
            lc1,lc2 = st.columns(2)
            for col,tkr in [(lc1,"SPY"),(lc2,"QQQ")]:
                with col:
                    st.markdown(f"**{tkr}**")
                    lv = levels.get(tkr,{})
                    if lv:
                        k1,k2,k3 = st.columns(3)
                        k1.metric("PDH",
                            f"${lv['pdh']:.2f}","Resistance")
                        k2.metric("PDC",
                            f"${lv['pdc']:.2f}","Pivot")
                        k3.metric("PDL",
                            f"${lv['pdl']:.2f}","Support")

            div_sig = report.get(
                "divergence_signal","") or ""
            if div_sig:
                st.divider()
                st.warning(f"⚠️ **{div_sig}**")

    # ══════════════════════════════════════════════
    # TAB 3 — RISK ADVISORY
    # ══════════════════════════════════════════════
    with tabs[2]:
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
    # TAB 4 — SENTIMENT
    # ══════════════════════════════════════════════
    with tabs[3]:
        st.subheader("😊 Market Sentiment")
        report = get_latest_report()
        events = get_todays_events()

        if report:
            up_pct    = report.get("up_pct",33) or \
                        report.get("matrix_score",33) or 33
            down_pct  = report.get("down_pct",8) or 8
            range_pct = report.get("range_pct",50) or 50
            ie        = report.get("is_event_day",False)
            conf      = report.get("confidence","") or ""

            sc1,sc2,sc3,sc4 = st.columns(4)
            sc1.metric("📈 Uptrend",   f"{up_pct}%")
            sc2.metric("📉 Downtrend", f"{down_pct}%")
            sc3.metric("➡️ Range",     f"{range_pct}%")
            sc4.metric("Event Day","Yes ★★★" if ie else "No")

            st.divider()
            st.markdown(card(
                f'<p style="color:#333;font-size:13px;'
                f'line-height:1.8;margin:0;">'
                f'<b>Step 1:</b> You classify narrative '
                f'(B/R/C/W/U/N)<br>'
                f'<b>Step 2:</b> System reads first '
                f'5-min candle at 9:35 AM<br>'
                f'<b>Step 3:</b> Matrix type → '
                f'historical probabilities<br>'
                f'<b>Step 4:</b> Up% / Down% / Range%<br>'
                f'<br><b>No ML. No VIX. '
                f'No arbitrary weights.</b></p>'
            ), unsafe_allow_html=True)

        if events:
            st.divider()
            st.markdown("### Today's Events")
            for ev in events:
                ic=("#CC0000" if ev[3]=="High"
                    else "#FF8C00")
                actual=ev[1]; previous=ev[2]
                arrow=""
                if actual and previous:
                    diff=float(actual)-float(previous)
                    arrow=" ↑" if diff>0 else " ↓"
                st.markdown(card(
                    f'<b style="color:{ic};">'
                    f'[{ev[3]}]</b> '
                    f'<span style="color:#333;">'
                    f'{ev[0]}</span>'
                    f'<br><span style="color:#666;'
                    f'font-size:12px;">'
                    f'A:{actual} P:{previous}{arrow}'
                    f'</span>',
                    border_color=ic
                ), unsafe_allow_html=True)

    # ══════════════════════════════════════════════
    # TAB 5 — MY PROFILE
    # ══════════════════════════════════════════════
    with tabs[4]:
        report   = get_latest_report()
        _uid_debug = st.session_state.get(
            "user_id", 1)
        events_b,scores_b,today_b,today_t = \
            get_behavioral_data(
                uid=_uid_debug)
        st.caption(f"DEBUG: uid={_uid_debug} "
                   f"events={len(events_b)}")

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
        }

        yest_evts  = get_period_events(
            yesterday2, yesterday2)
        week_evts  = get_period_events(
            week_ago2, today_est2)
        month_evts = events_b
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
                if reentry["message"].startswith("⛔"):
                    st.error(reentry["message"])
                    gate_blocked = True
                else:
                    st.warning(reentry["message"])

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

                submitted = st.form_submit_button(
                    "💾 Log Entry",
                    use_container_width=True)

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

    
    # ══════════════════════════════════════════════
    # TAB 6 — ANALYTICS
    with tabs[5]:
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

    # TAB 7 — FORWARD TEST
    with tabs[6]:
        st.subheader("🎯 Forward Test Record")
        try:
            with engine.connect() as conn:
                sig = conn.execute(text("""
                    SELECT COUNT(*),
                           SUM(CASE WHEN
                               was_correct
                               THEN 1 ELSE 0
                               END)
                    FROM forward_test_log
                    WHERE market='US'
                    AND edge != 'No Edge'
                    AND was_correct IS NOT NULL
                """)).fetchone()

                ne = conn.execute(text("""
                    SELECT COUNT(*)
                    FROM forward_test_log
                    WHERE market='US'
                    AND edge = 'No Edge'
                    AND actual_bias IS NOT NULL
                """)).fetchone()

                all_days = conn.execute(text("""
                    SELECT trade_date,
                           matrix_type,
                           edge,
                           predicted_bias,
                           actual_bias,
                           was_correct
                    FROM forward_test_log
                    WHERE market='US'
                    AND actual_bias IS NOT NULL
                    ORDER BY trade_date DESC
                    LIMIT 60
                """)).fetchall()

            sig_total   = int(sig[0] or 0)
            sig_correct = int(sig[1] or 0)
            ne_days     = int(ne[0] or 0)
            sig_pct     = round(
                sig_correct/sig_total*100,1
            ) if sig_total > 0 else 0

            f1,f2,f3,f4 = st.columns(4)
            f1.metric("Signal Days", sig_total)
            f2.metric("Correct", sig_correct)
            f3.metric("Accuracy", f"{sig_pct}%")
            f4.metric("No Edge Days", ne_days)

            st.caption(
                "Accuracy excludes No Edge days "
                "— no prediction made on those days")

            if all_days:
                import pandas as pd
                df = pd.DataFrame(all_days,
                    columns=["Date","Matrix",
                             "Edge","Predicted",
                             "Actual","Correct"])
                df["Correct"] = df["Correct"].map(
                    {True:"✓",False:"✗",None:"—"})
                st.dataframe(
                    df[["Date","Matrix",
                        "Predicted","Actual",
                        "Correct"]],
                    use_container_width=True)
        except Exception as e:
            st.error(f"Forward test error: {e}")

    # TAB 8 — SETTINGS
    # ══════════════════════════════════════════════
    with tabs[7]:
        st.subheader("⚙️ Settings & Status")

        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            st.success("✅ Supabase connected")
        except:
            st.error("❌ Connection failed")

        st.divider()
        st.markdown("### Data Summary")
        try:
            with engine.connect() as conn:
                tables={
                    "price_data":    "Price rows",
                    "economic_events":"Events",
                    "news_headlines": "Headlines",
                    "intelligence_reports":"Reports",
                    "learning_log":  "Learning log",
                    "trade_journal": "Trade journal",
                    "behavioral_events":"Behavioral",
                    "behavioral_scores":"B. Scores"
                }
                cols=st.columns(4)
                i=0
                for table,label in tables.items():
                    try:
                        r=conn.execute(text(
                            f"SELECT COUNT(*) "
                            f"FROM {table}"))
                        count=r.fetchone()[0]
                        cols[i%4].metric(
                            label,f"{count:,}")
                    except:
                        cols[i%4].metric(label,"N/A")
                    i+=1
        except Exception as e:
            st.error(f"Stats error: {e}")

        st.divider()
        st.markdown("### Layer Status")
        layers={
            "Layer 1 — Data Pipeline":
                "✅ Railway 24/7",
            "Layer 2 — Probability Engine":
                "✅ Matrix lookup (204 days)",
            "Layer 3 — Decision Support":
                "✅ Complete",
            "Layer 4 — Risk + Drawdown":
                "✅ Complete",
            "Layer 5 — Trade Execution":
                "✅ Complete",
            "Layer 6 — Portal":
                "✅ Live v6",
            "Layer 7 — Behavioral Intel":
                "✅ Full auto-detection"
        }
        for layer,status in layers.items():
            st.markdown(f"**{layer}:** {status}")

if __name__=="__main__":
    main()
