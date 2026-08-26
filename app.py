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
                ORDER BY log_date DESC,
                         logged_at DESC
                LIMIT 30
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
                       exit_time
                FROM trade_journal
                WHERE market='US'
                AND trade_date >= :start
                ORDER BY trade_date DESC,
                         created_at DESC
                LIMIT 100
            """), {"start": str(start)})
            return result.fetchall()
    except:
        return []

def get_behavioral_data():
    start = date.today() - timedelta(days=30)
    try:
        with engine.connect() as conn:
            events = conn.execute(text("""
                SELECT behavior_type,
                       COUNT(*) as cnt,
                       SUM(financial_cost) as cost
                FROM behavioral_events
                WHERE market='US'
                AND event_date >= :start
                GROUP BY behavior_type
                ORDER BY cnt DESC LIMIT 10
            """), {"start": str(start)}).fetchall()

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
                AND event_date=:td
                GROUP BY behavior_type,
                         severity, description
                LIMIT 10
            """), {"td": str(date.today())}).fetchall()

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
                AND trade_date=:td
            """), {"td": str(date.today())}).fetchone()

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
                AND trade_date >= :start
            """), {"start": str(start)}).fetchone()

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
                AND entry_time_actual IS NOT NULL
                GROUP BY bucket
                ORDER BY bucket
            """)).fetchall()
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
                AND setup_type IS NOT NULL
                GROUP BY setup_type
                ORDER BY total_pnl DESC
            """)).fetchall()
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
                ORDER BY trade_date, created_at
            """)).fetchall()

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
                AND trade_date=:td
                ORDER BY created_at DESC LIMIT 1
            """), {"td": str(trade_date)}).fetchone()

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
    lines = []

    if events_b:
        worst = events_b[0]
        cost  = abs(float(worst[2] or 0))
        count = int(worst[1])
        lines.append(
            f"Your biggest pattern is "
            f"**{worst[0]}** — "
            f"{count}x in 30 days "
            f"costing ${cost:.0f}."
        )

    revenge = next((e for e in events_b
        if e[0]=="Revenge Trading"),None)
    fomo    = next((e for e in events_b
        if e[0]=="FOMO"),None)

    if revenge and fomo:
        lines.append(
            "FOMO gets you in, revenge keeps "
            "you in too long. Fix the first "
            "trade — the second never happens."
        )
    elif revenge and int(revenge[1]) >= 2:
        lines.append(
            "After any loss — 30 min break. "
            "No exceptions. Your revenge "
            "trades lose every time."
        )
    elif fomo and int(fomo[1]) >= 2:
        lines.append(
            "Check the system BEFORE every "
            "trade. Every FOMO trade skips "
            "this step."
        )

    if scores_b and len(scores_b) >= 3:
        recent = [int(s[0]) for s in scores_b[:3]]
        older  = [int(s[0]) for s in scores_b[3:]]
        if older:
            if sum(recent)/3 > sum(older)/len(older)+5:
                lines.append(
                    "Behavioral score improving. "
                    "The discipline is showing.")
            elif sum(recent)/3 < sum(older)/len(older)-5:
                lines.append(
                    "Score declining this week. "
                    "What changed?")

    if report:
        conf = report.get("confidence","") or ""
        if "No Edge" in conf:
            lines.append(
                "No edge today. "
                "Patience is a position.")
        elif "Long Bias" in conf:
            lines.append(
                "Long Bias today. "
                "Stay disciplined — follow the plan.")

    return " ".join(lines) if lines else (
        "Log trades consistently to build "
        "your personalized coaching brief.")

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

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main():
    now_est = datetime.now(EST)
    today   = get_last_trading_day()

    st.markdown(
        f"<div style='text-align:center;padding:8px 0;'>"
        f"<h1 style='color:#0066CC;margin:0;"
        f"font-size:26px;'>📊 MLTrading Intelligence</h1>"
        f"<p style='color:#888;margin:0;font-size:12px;'>"
        f"{now_est.strftime('%A %B %d %Y — %H:%M EST')}"
        f" &nbsp;|&nbsp; Trading day: {today}</p>"
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
            up_pct = report.get("matrix_score",33) or 33
            tp     = report.get("trade_prob",30) or 30
            bias   = report.get("bias","No Clear Edge") \
                     or "No Clear Edge"
            conf   = report.get("confidence","No Edge") \
                     or "No Edge"
            ie     = report.get("is_event_day",False)

            # Find and replace this entire block:
        if "Bullish" in str(bias) or \
           "Uptrend" in str(bias):
            down_pct  = max(5,100-up_pct-20)
            range_pct = max(5,100-up_pct-down_pct)
        elif "Bearish" in str(bias) or \
            "Downtrend" in str(bias):
            down_pct  = up_pct
            up_pct    = max(5,100-down_pct-30)
            range_pct = max(5,100-up_pct-down_pct)
        else:
            down_pct  = 25
            range_pct = max(5,100-up_pct-down_pct)

        # Replace with:
            up_pct    = report.get("up_pct",33) or \
            report.get("matrix_score",33) or 33
            down_pct  = report.get("down_pct",25) or 25
            range_pct = report.get("range_pct",42) or 42

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
            up_pct = report.get("matrix_score",33) or 33
            bias   = report.get("bias","Neutral") or "Neutral"
            conf   = report.get("confidence","") or ""

            if "Bullish" in str(bias) or \
               "Uptrend" in str(bias):
                down_pct  = max(5,100-up_pct-20)
                range_pct = max(5,100-up_pct-down_pct)
            elif "Bearish"   in str(bias) or \
                 "Downtrend" in str(bias):
                down_pct  = up_pct
                up_pct    = max(5,100-down_pct-30)
                range_pct = max(5,100-up_pct-down_pct)
            else:
                down_pct=25; range_pct=100-up_pct-down_pct

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
            up_pct = report.get("matrix_score",33) or 33
            ie     = report.get("is_event_day",False)
            conf   = report.get("confidence","") or ""

            sc1,sc2,sc3 = st.columns(3)
            sc1.metric("Uptrend Probability",f"{up_pct}%")
            sc2.metric("Event Day","Yes ★★★" if ie else "No")
            sc3.metric("Edge",conf or "No Edge")

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
        events_b,scores_b,today_b,today_t = \
            get_behavioral_data()

        # State banner
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

        # Coaching brief
        brief = generate_coaching_brief(
            events_b,scores_b,today_t,report)
        if brief:
            st.markdown(card(
                f'<p style="color:#666;font-size:11px;'
                f'margin:0;">💬 COACHING BRIEF</p>'
                f'<p style="color:#333;font-size:14px;'
                f'line-height:1.7;margin:8px 0 0;">'
                f'{brief}</p>',
                border_color="#0066CC",bg="#EEF4FF"
            ), unsafe_allow_html=True)

        col_brief,col_log = st.columns([1,1])

        # Morning brief
        with col_brief:
            st.subheader("📋 Morning Brief")

            if events_b:
                st.markdown("**Patterns — last 30 days:**")
                for e in events_b[:5]:
                    cost  = float(e[2] or 0)
                    count = int(e[1])
                    color = ("#CC0000" if cost<-50
                             else "#FF8C00" if cost<0
                             else "#0066CC")
                    st.markdown(
                        f"<div style='background:#F8F9FA;"
                        f"padding:8px 12px;"
                        f"border-radius:6px;"
                        f"border-left:3px solid {color};"
                        f"margin-bottom:4px;"
                        f"display:flex;"
                        f"justify-content:space-between;'>"
                        f"<span style='color:{color};"
                        f"font-weight:bold;"
                        f"font-size:12px;'>{e[0]}</span>"
                        f"<span>"
                        f"<span style='color:#666;"
                        f"font-size:12px;'>{count}x</span>"
                        f"<span style='color:{color};"
                        f"font-size:12px;"
                        f"margin-left:12px;'>"
                        f"${cost:+.0f}</span>"
                        f"</span></div>",
                        unsafe_allow_html=True
                    )
            else:
                st.info("Log trades to see patterns.")

            st.markdown("**Today's warnings:**")
            shown = 0

            for btype,msg,color_cls in [
                ("Revenge Trading",
                 "After ANY loss → 30 min break",
                 "FFE8E8"),
                ("FOMO",
                 "Check system BEFORE every trade",
                 "FFE8E8"),
                ("Overtrading",
                 "Max 3 trades. Win→15min Loss→30min",
                 "FFF3CD")
            ]:
                b = next((e for e in events_b
                          if e[0]==btype),None)
                if b and int(b[1])>=1:
                    em = "🔴" if color_cls=="FFE8E8" \
                         else "🟡"
                    st.markdown(
                        f"<div style='background:"
                        f"#{color_cls};"
                        f"padding:8px 12px;"
                        f"border-radius:6px;"
                        f"margin-bottom:4px;'>"
                        f"{em} <b>{btype}</b> "
                        f"({int(b[1])}x)<br>"
                        f"<span style='color:#666;"
                        f"font-size:12px;'>"
                        f"{msg}</span></div>",
                        unsafe_allow_html=True
                    )
                    shown += 1

            if shown == 0:
                st.success("No major patterns yet.")

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

            # Pre-trade gate
            reentry      = check_reentry_timing(
                date.today())
            gate_blocked = False
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
                t_acct   = r1c3.selectbox("Account",
                    ["Live","Topstep",
                     "Combine","Paper"])

                # Row 2 — Direction + Setup + Qty
                r2c1,r2c2,r2c3 = st.columns(3)
                t_dir   = r2c1.radio("Direction",
                    ["Long","Short"],horizontal=True)
                t_setup = r2c2.selectbox("Setup",
                    ["Momentum","Reversal","Breakout",
                     "Range","Event","Mean Reversion",
                     "Trend Pullback","FOMO",
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

                # Emotion
                t_emotion = st.slider(
                    "Emotion (1=calm 10=stressed)",
                    min_value=1,max_value=10,value=5)

                # Plan + System
                r5c1,r5c2 = st.columns(2)
                t_plan    = r5c1.radio(
                    "Followed plan?",
                    ["Yes","No"],horizontal=True)
                t_checked = r5c2.radio(
                    "Checked system?",
                    ["Yes","No"],horizontal=True)

                t_mistake = st.text_input(
                    "Mistake? (blank if none)")

                submitted = st.form_submit_button(
                    "💾 Log Trade",
                    use_container_width=True)

                if submitted and t_entry>0 and t_exit>0:
                    pv_map = {
                        "NQ":20,"ES":50,"MNQ":2,
                        "MES":5,"SPY":1,"QQQ":1}
                    pv = pv_map.get(t_ticker,1)

                    # P&L with quantity
                    if t_dir=="Long":
                        pnl=(t_exit-t_entry)*pv*t_qty
                    else:
                        pnl=(t_entry-t_exit)*pv*t_qty

                    outcome=("Win" if pnl>0
                             else "Loss" if pnl<0
                             else "Scratch")

                    risk_pts    = abs(t_entry-t_stop)
                    risk_dollar = risk_pts*pv*t_qty
                    pnl_r = round(
                        pnl/risk_dollar,2
                    ) if risk_dollar>0 else 0

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
                                    pre_trade_gate)
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
                                    :gate)
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
                                "setup":  t_setup,
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
                                "gate":   gate_passed
                            })
                            row=res.fetchone()
                            trade_id  =row[0]
                            created_at=row[1]
                            conn.commit()

                        # Auto behavioral detection
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

        # Trade Journal
        st.subheader("📊 Trade Journal")
        jf1,jf2 = st.columns(2)
        days_filter = jf1.selectbox("Period",[
            "Today","Last 7 days","Last 30 days"])
        acct_filter = jf2.selectbox("Account",[
            "All","Live","Topstep","Combine","Paper"])

        days_map={"Today":1,"Last 7 days":7,
                  "Last 30 days":30}
        trades=get_trade_journal(days_map[days_filter])

        if acct_filter != "All":
            trades=[t for t in trades
                    if t[15]==acct_filter]

        if trades:
            total    =len(trades)
            wins     =sum(1 for t in trades
                          if float(t[9])>0)
            total_pnl=sum(float(t[9]) for t in trades)
            wr       =round(wins/total*100,1)
            avg_em   =round(sum(
                int(t[11]) for t in trades
            )/total,1)

            sm1,sm2,sm3,sm4=st.columns(4)
            sm1.metric("Trades",   total)
            sm2.metric("Win Rate", f"{wr}%")
            sm3.metric("Total P&L",f"${total_pnl:+.2f}")
            sm4.metric("Avg Emotion",avg_em)

            # R:R summary
            planned_rrs=[]; actual_rrs=[]
            for t in trades:
                if t[8] and float(t[8])>0:
                    risk=abs(float(t[5])-float(t[7]))
                    if risk>0:
                        reward=(float(t[8])-float(t[5])
                                if t[4]=="Long"
                                else float(t[5])-float(t[8]))
                        planned_rrs.append(reward/risk)
                if t[10]:
                    actual_rrs.append(float(t[10]))

            if planned_rrs and actual_rrs:
                avg_p=round(sum(planned_rrs)
                            /len(planned_rrs),2)
                avg_a=round(sum(actual_rrs)
                            /len(actual_rrs),2)
                gap  =round(avg_p-avg_a,2)
                rr1,rr2,rr3=st.columns(3)
                rr1.metric("Avg Planned R:R",
                    f"1:{avg_p:.2f}")
                rr2.metric("Avg Actual R:R",
                    f"1:{avg_a:.2f}")
                rr3.metric("R:R Gap",f"{gap:.2f}R",
                    "on table" if gap>0 else "good")

            st.divider()
            for t in trades[:20]:
                pnl  =float(t[9])
                pnl_r=float(t[10] or 0)
                qty  =int(t[18] or 1)
                color=("#0066CC" if pnl>0
                       else "#CC0000" if pnl<0
                       else "#888")
                em   =("✅" if pnl>0
                       else "❌" if pnl<0 else "➖")
                plan ="✓" if t[12] else "✗"
                chk  ="✓" if t[16] else "✗"
                hold_txt=""
                if t[19] and t[20]:
                    try:
                        fmt="%H:%M"
                        et=datetime.strptime(str(t[19]),fmt)
                        xt=datetime.strptime(str(t[20]),fmt)
                        mins=int((xt-et).total_seconds()/60)
                        hold_txt=f"• Hold:{mins}min "
                    except:
                        pass
                qty_lbl=("sh" if t[3] in ["SPY","QQQ"]
                          else "ct")
                tgt_txt=(f"• Tgt:{float(t[8]):.2f} "
                         if t[8] else "")
                st.markdown(
                    f"<div style='background:#F8F9FA;"
                    f"padding:10px 14px;"
                    f"border-radius:8px;"
                    f"border-left:4px solid {color};"
                    f"margin-bottom:6px;'>"
                    f"<div style='display:flex;"
                    f"justify-content:space-between;'>"
                    f"<span><b style='color:#333;'>"
                    f"{em} {t[3]} {t[4]} ×{qty}{qty_lbl}"
                    f"</b>"
                    f"<span style='color:#888;"
                    f"font-size:12px;margin-left:8px;'>"
                    f"{t[1]} {t[19] or t[2] or ''} • "
                    f"{t[13] or ''} • {t[15] or ''}"
                    f"</span></span>"
                    f"<b style='color:{color};'>"
                    f"${pnl:+.2f} ({pnl_r:+.2f}R)"
                    f"</b></div>"
                    f"<div style='color:#888;"
                    f"font-size:11px;margin-top:4px;'>"
                    f"Entry:{float(t[5]):.2f} → "
                    f"Exit:{float(t[6]):.2f} • "
                    f"Stop:{float(t[7]):.2f} "
                    f"{tgt_txt}• "
                    f"Em:{t[11]}/10 • "
                    f"Plan:{plan} • Sys:{chk} "
                    f"{hold_txt}"
                    f"{f'• ⚠️ {t[14]}' if t[14] else ''}"
                    f"</div></div>",
                    unsafe_allow_html=True
                )
        else:
            st.info("No trades logged yet.")

        st.divider()

        # Expectancy
        st.subheader("📐 Expectancy")
        exp=get_expectancy()
        if exp:
            ex1,ex2,ex3,ex4=st.columns(4)
            ex1.metric("Win Rate",f"{exp['win_rate']}%")
            ex2.metric("Avg Win",f"${exp['avg_win']:+.2f}")
            ex3.metric("Avg Loss",
                f"${exp['avg_loss']:+.2f}")
            ex4.metric("Per Trade",
                f"${exp['expectancy']:+.2f}")
            exp_color=("#0066CC"
                       if exp['expectancy']>0
                       else "#CC0000")
            exp_desc=("✅ Positive — system profitable"
                      if exp['expectancy']>0
                      else "❌ Negative — fix your edge")
            st.markdown(card(
                f'<p style="color:{exp_color};">'
                f'<b>{exp_desc}</b></p>'
                f'<p style="color:#666;font-size:12px;">'
                f'{exp["total"]} trades | '
                f'{exp["wins"]}W / {exp["losses"]}L</p>',
                border_color=exp_color
            ), unsafe_allow_html=True)
        else:
            st.info("Log 5+ trades to see expectancy.")

        st.divider()

        # Time of day
        st.subheader("⏰ Time of Day Analysis")
        time_data=get_time_analysis()
        if time_data and len(time_data)>=2:
            buckets=[t[0] for t in time_data]
            wr_list=[round(int(t[2])/int(t[1])*100,1)
                     if int(t[1])>0 else 0
                     for t in time_data]
            counts =[int(t[1]) for t in time_data]
            colors =["#0066CC" if w>=55
                     else "#CC0000" if w<40
                     else "#FF8C00"
                     for w in wr_list]
            fig=go.Figure()
            fig.add_trace(go.Bar(
                x=buckets,y=wr_list,
                marker_color=colors,
                text=[f"{w}%\n({c})"
                      for w,c in zip(wr_list,counts)],
                textposition="outside"
            ))
            fig.add_hline(y=50,line_dash="dash",
                line_color="#888",
                annotation_text="50%")
            fig.update_layout(
                height=250,
                margin=dict(l=0,r=0,t=20,b=0),
                yaxis=dict(range=[0,100]),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig,
                use_container_width=True)
            if wr_list:
                best_i =wr_list.index(max(wr_list))
                worst_i=wr_list.index(min(wr_list))
                bw1,bw2=st.columns(2)
                bw1.success(
                    f"🟢 Best: {buckets[best_i]} "
                    f"({wr_list[best_i]}% WR)")
                bw2.error(
                    f"🔴 Worst: {buckets[worst_i]} "
                    f"({wr_list[worst_i]}% WR)")
        else:
            st.info(
                "Log 10+ trades with entry times "
                "to see patterns.")

        st.divider()

        # Setup performance
        st.subheader("🎯 Setup Performance")
        setup_data=get_setup_analysis()
        if setup_data and len(setup_data)>=2:
            for s in setup_data:
                total_s=int(s[1]); wins_s=int(s[2])
                pnl_s  =float(s[3])
                wr_s   =round(wins_s/total_s*100,1) \
                        if total_s>0 else 0
                color  =("#0066CC" if pnl_s>0
                         else "#CC0000")
                st.markdown(
                    f"<div style='background:#F8F9FA;"
                    f"padding:8px 14px;"
                    f"border-radius:6px;"
                    f"border-left:3px solid {color};"
                    f"margin-bottom:4px;"
                    f"display:flex;"
                    f"justify-content:space-between;'>"
                    f"<span style='color:#333;"
                    f"font-weight:bold;'>{s[0]}</span>"
                    f"<span>"
                    f"<span style='color:#666;"
                    f"font-size:12px;'>"
                    f"{total_s} trades • {wr_s}% WR"
                    f"</span>"
                    f"<span style='color:{color};"
                    f"font-weight:bold;"
                    f"margin-left:12px;'>"
                    f"${pnl_s:+.0f}</span>"
                    f"</span></div>",
                    unsafe_allow_html=True
                )
        else:
            st.info("Log trades to see setup breakdown.")

        st.divider()

        # Account breakdown
        st.subheader("🏦 Account Breakdown")
        acct_data=get_account_breakdown()
        if acct_data:
            acct_df=pd.DataFrame(acct_data,
                columns=["Account","Behavior",
                         "Count","Cost"])
            accounts=acct_df["Account"].unique()
            acct_cols=st.columns(min(len(accounts),3))
            for i,acct in enumerate(accounts):
                with acct_cols[i%3]:
                    st.markdown(f"**{acct}**")
                    rows=acct_df[
                        acct_df["Account"]==acct]
                    for _,row in rows.iterrows():
                        cost=float(row["Cost"] or 0)
                        color=("#CC0000" if cost<-50
                               else "#FF8C00"
                               if cost<0 else "#888")
                        st.markdown(
                            f"<div style='font-size:12px;"
                            f"padding:4px 0;"
                            f"border-bottom:1px solid #eee;'>"
                            f"<span style='color:{color};'>"
                            f"{row['Behavior']}</span>"
                            f"<span style='color:#888;"
                            f"margin-left:8px;'>"
                            f"{int(row['Count'])}x "
                            f"${cost:+.0f}</span></div>",
                            unsafe_allow_html=True
                        )
        else:
            st.info("Log trades across accounts.")

        st.divider()

        # Money leaks
        st.subheader("💸 Money Leaks")
        start_30=date.today()-timedelta(days=30)
        try:
            with engine.connect() as conn:
                leaks=conn.execute(text("""
                    SELECT behavior_type,
                           COUNT(*) as cnt,
                           SUM(financial_cost) as cost
                    FROM behavioral_events
                    WHERE market='US'
                    AND event_date >= :start
                    GROUP BY behavior_type
                    ORDER BY cost ASC LIMIT 10
                """),{"start":str(start_30)}).fetchall()

            if leaks:
                costs=[abs(float(l[2] or 0))
                       for l in leaks]
                max_cost=max(costs) if costs else 1
                max_cost=max(max_cost,1)
                for l in leaks:
                    cost =float(l[2] or 0)
                    count=int(l[1])
                    pct  =min(100,
                        abs(cost)/max_cost*100)
                    color=("#CC0000" if cost<-50
                           else "#FF8C00" if cost<0
                           else "#0066CC")
                    st.markdown(
                        f"<div style='background:#F8F9FA;"
                        f"padding:8px 14px;"
                        f"border-radius:6px;"
                        f"margin-bottom:4px;'>"
                        f"<div style='display:flex;"
                        f"justify-content:space-between;'>"
                        f"<span style='color:#333;"
                        f"font-weight:bold;'>"
                        f"{l[0]}</span>"
                        f"<span style='color:{color};"
                        f"font-weight:bold;'>"
                        f"${cost:+.0f}"
                        f"<span style='color:#888;"
                        f"font-size:11px;"
                        f"font-weight:normal;'>"
                        f" ({count}x)</span></span>"
                        f"</div>"
                        f"<div style='background:#E8E8E8;"
                        f"border-radius:3px;height:4px;"
                        f"margin-top:4px;'>"
                        f"<div style='background:{color};"
                        f"width:{pct:.0f}%;height:4px;"
                        f"border-radius:3px;'>"
                        f"</div></div></div>",
                        unsafe_allow_html=True
                    )
            else:
                st.info("No behavioral data yet.")
        except Exception as e:
            st.error(f"Error: {e}")

        st.divider()

        # Forward test
        st.subheader("📈 Forward Test Record")
        log_df=get_learning_log()
        if log_df.empty:
            st.info("No forward test data yet.")
        else:
            total_d=len(log_df)
            correct=log_df["correct"].sum()
            wr_days=round(correct/total_d*100,1) \
                    if total_d>0 else 0
            fl1,fl2,fl3=st.columns(3)
            fl1.metric("Days Tested",total_d)
            fl2.metric("Correct",int(correct))
            fl3.metric("Accuracy",f"{wr_days}%")
            st.dataframe(
                log_df[["date","predicted","actual",
                         "return","correct","score"]],
                use_container_width=True
            )

    # ══════════════════════════════════════════════
    # TAB 6 — SETTINGS
    # ══════════════════════════════════════════════
    with tabs[5]:
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
