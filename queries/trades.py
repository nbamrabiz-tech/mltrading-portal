# ── Trade queries ────────────────
import streamlit as st
from datetime import date, timedelta
from sqlalchemy import text

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

