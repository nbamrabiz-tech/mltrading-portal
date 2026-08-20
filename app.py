# ══════════════════════════════════════════════════════════════
# MLTrading System — Portal v3
# ══════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from datetime import datetime, date, timedelta
import pytz

st.set_page_config(
    page_title  = "MLTrading Intelligence",
    page_icon   = "📊",
    layout      = "wide",
    initial_sidebar_state = "collapsed"
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

# ── Data functions ────────────────────────────────────────────
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
            rows   = result.fetchall()
            levels = {}
            seen   = set()
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

def get_learning_log_deduped():
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
                    columns=["date","predicted","actual",
                             "return","correct","score"])
    except:
        pass
    return pd.DataFrame()

def get_vix():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT CAST(close AS FLOAT)
                FROM vix_data WHERE market='US'
                ORDER BY date DESC LIMIT 1
            """))
            row = result.fetchone()
            return float(row[0]) if row else 18.0
    except:
        return 18.0

def get_trade_journal(days_back=30):
    start = date.today() - timedelta(days=days_back)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT trade_date, trade_time,
                       ticker, direction,
                       entry_price, exit_price,
                       pnl, pnl_r,
                       emotional_state,
                       followed_plan,
                       setup_type, mistake,
                       account_type
                FROM trade_journal
                WHERE market='US'
                AND trade_date >= :start
                ORDER BY trade_date DESC,
                         created_at DESC
                LIMIT 50
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
                ORDER BY cnt DESC
                LIMIT 10
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
                       COUNT(*) as cnt
                FROM behavioral_events
                WHERE market='US'
                AND event_date=:td
                GROUP BY behavior_type, severity
                LIMIT 10
            """), {"td": str(date.today())}).fetchall()

            today_t = conn.execute(text("""
                SELECT COUNT(*),
                       SUM(CASE WHEN pnl>0
                           THEN 1 ELSE 0 END),
                       SUM(pnl),
                       AVG(emotional_state)
                FROM trade_journal
                WHERE market='US'
                AND trade_date=:td
            """), {"td": str(date.today())}).fetchone()

        return events, scores, today_b, today_t
    except:
        return [], [], [], None

# ── Style helpers ─────────────────────────────────────────────
def bias_color(bias):
    if not bias: return "#666"
    if "Bullish" in str(bias): return "#0066CC"
    if "Bearish" in str(bias): return "#CC0000"
    return "#888888"

def bias_emoji(bias):
    if not bias: return "⚪"
    if "Bullish" in str(bias): return "🟢"
    if "Bearish" in str(bias): return "🔴"
    return "⚪"

def score_bar(score, width=200):
    color = ("#0066CC" if score >= 58
             else "#CC0000" if score <= 42
             else "#FF8C00")
    return (
        f'<div style="background:#E8E8E8;'
        f'border-radius:4px;width:{width}px;height:8px;">'
        f'<div style="background:{color};'
        f'width:{min(score,100)}%;height:8px;'
        f'border-radius:4px;"></div></div>'
    )

def card(content, border_color="#0066CC"):
    return (
        f'<div style="background:#F8F9FA;'
        f'padding:14px;border-radius:8px;'
        f'border-left:4px solid {border_color};'
        f'margin-bottom:8px;">'
        f'{content}</div>'
    )

# ── Main ──────────────────────────────────────────────────────
def main():
    now_est = datetime.now(EST)
    today   = get_last_trading_day()

    st.markdown(
        f"""
        <div style='text-align:center;padding:8px 0;'>
        <h1 style='color:#0066CC;margin:0;font-size:26px;'>
        📊 MLTrading Intelligence
        </h1>
        <p style='color:#888;margin:0;font-size:12px;'>
        {now_est.strftime('%A, %B %d %Y — %H:%M EST')}
        &nbsp;|&nbsp; Trading day: {today}
        </p>
        </div>
        """,
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

    # ══════════════════════════════════════════════════════════
    # TAB 1 — DAILY INTELLIGENCE
    # ══════════════════════════════════════════════════════════
    with tabs[0]:
        report = get_latest_report()
        vix    = get_vix()
        events = get_todays_events()
        levels = get_spy_levels()

        if report:
            rpt_date = report.get("report_date", today)
            if str(rpt_date) != str(today):
                st.warning(
                    f"⚠️ Showing report from {rpt_date}. "
                    f"Run morning script to update."
                )

        if not report:
            st.warning("No report found. "
                       "Run morning script first.")
        else:
            bias  = report.get("bias","Neutral")
            score = report.get("matrix_score",50)
            conf  = report.get("confidence","Low")
            tp    = report.get("trade_prob",45)

            c1,c2,c3,c4 = st.columns(4)

            with c1:
                color = bias_color(bias)
                st.markdown(card(
                    f'<p style="color:#666;margin:0;'
                    f'font-size:11px;">MARKET BIAS</p>'
                    f'<p style="color:{color};margin:4px 0 0;'
                    f'font-size:22px;font-weight:bold;">'
                    f'{bias_emoji(bias)} {bias}</p>'
                    f'<p style="color:#888;margin:0;'
                    f'font-size:11px;">{conf} confidence</p>',
                    border_color=color
                ), unsafe_allow_html=True)

            with c2:
                st.markdown(card(
                    f'<p style="color:#666;margin:0;'
                    f'font-size:11px;">MATRIX SCORE</p>'
                    f'<p style="color:#333;margin:4px 0 4px;'
                    f'font-size:22px;font-weight:bold;">'
                    f'{score}/100</p>'
                    + score_bar(score)
                ), unsafe_allow_html=True)

            with c3:
                tp_color = ("#0066CC" if tp >= 65
                            else "#CC0000" if tp <= 40
                            else "#FF8C00")
                st.markdown(card(
                    f'<p style="color:#666;margin:0;'
                    f'font-size:11px;">TRADE PROBABILITY</p>'
                    f'<p style="color:{tp_color};'
                    f'margin:4px 0 4px;font-size:22px;'
                    f'font-weight:bold;">{tp}%</p>'
                    + score_bar(tp),
                    border_color=tp_color
                ), unsafe_allow_html=True)

            with c4:
                vix_color = ("#0066CC" if vix < 15
                             else "#CC0000" if vix >= 25
                             else "#FF8C00")
                vix_lbl   = ("Low fear" if vix < 15
                             else "High fear" if vix >= 25
                             else "Moderate")
                st.markdown(card(
                    f'<p style="color:#666;margin:0;'
                    f'font-size:11px;">VIX</p>'
                    f'<p style="color:{vix_color};'
                    f'margin:4px 0 0;font-size:22px;'
                    f'font-weight:bold;">{vix:.2f}</p>'
                    f'<p style="color:#888;margin:0;'
                    f'font-size:11px;">{vix_lbl}</p>',
                    border_color=vix_color
                ), unsafe_allow_html=True)

            st.divider()

            col_l, col_r = st.columns([3,2])

            with col_l:
                st.subheader("📰 Today's Narrative")
                headline = report.get(
                    "narrative_headline",
                    "No narrative available")
                ns = report.get("narrative_score",50)
                ie = report.get("is_event_day",False)
                st.markdown(card(
                    f'<p style="color:#333;font-size:14px;'
                    f'line-height:1.6;margin:0;">'
                    f'{headline}</p>'
                ), unsafe_allow_html=True)
                m1,m2,m3 = st.columns(3)
                m1.metric("Narrative Score", f"{ns}/100")
                m2.metric("Event Day",
                          "Yes ★★★" if ie else "No")
                m3.metric("Volatility",
                    report.get("volatility","Normal")
                    or "Normal")

            with col_r:
                st.subheader("🤖 ML Ensemble")
                ml_score = report.get(
                    "ml_ensemble_score",50)
                ml_lean  = report.get(
                    "ml_ensemble_lean","Neutral")
                models = {
                    "XGBoost":   report.get("xgb_score",50),
                    "ARIMA":     report.get("arima_score",50),
                    "LSTM":      report.get("lstm_score",50),
                    "RandForest":report.get("rf_score",50),
                    "GradBoost": report.get("gb_score",50)
                }
                for model, ms in models.items():
                    cn,cb = st.columns([2,3])
                    cn.markdown(
                        f'<p style="color:#666;'
                        f'font-size:12px;margin:2px 0;">'
                        f'{model}</p>',
                        unsafe_allow_html=True)
                    cb.markdown(
                        score_bar(ms or 50, width=120) +
                        f'<p style="color:#888;'
                        f'font-size:11px;margin:0;">'
                        f'{ms}/100</p>',
                        unsafe_allow_html=True)
                st.markdown(
                    f"**Ensemble: {ml_score}/100"
                    f" — {ml_lean}**")

            st.divider()
            st.subheader("🕯️ First Candle")
            cc1,cc2,cc3 = st.columns(3)

            spy_dir  = report.get("spy_candle_dir","Unknown")
            spy_conv = report.get("spy_candle_conv","")
            spy_sc   = report.get("spy_candle_score",50)
            qqq_dir  = report.get("qqq_candle_dir","Unknown")
            qqq_conv = report.get("qqq_candle_conv","")
            reaction = report.get("reaction_type","Unknown")

            cc1.markdown(card(
                f'<p style="color:#666;font-size:11px;'
                f'margin:0;">SPY CANDLE</p>'
                f'<p style="color:{bias_color(spy_dir)};'
                f'font-size:18px;font-weight:bold;'
                f'margin:4px 0 0;">{spy_dir}</p>'
                f'<p style="color:#888;font-size:11px;'
                f'margin:0;">{spy_conv} | {spy_sc}/100</p>',
                border_color=bias_color(spy_dir)
            ), unsafe_allow_html=True)

            cc2.markdown(card(
                f'<p style="color:#666;font-size:11px;'
                f'margin:0;">QQQ CANDLE</p>'
                f'<p style="color:{bias_color(qqq_dir)};'
                f'font-size:18px;font-weight:bold;'
                f'margin:4px 0 0;">{qqq_dir}</p>'
                f'<p style="color:#888;font-size:11px;'
                f'margin:0;">{qqq_conv}</p>',
                border_color=bias_color(qqq_dir)
            ), unsafe_allow_html=True)

            cc3.markdown(card(
                f'<p style="color:#666;font-size:11px;'
                f'margin:0;">REACTION</p>'
                f'<p style="color:#FF8C00;font-size:14px;'
                f'font-weight:bold;margin:4px 0 0;">'
                f'{reaction}</p>',
                border_color="#FF8C00"
            ), unsafe_allow_html=True)

            st.divider()
            st.subheader("📍 Key Intraday Levels")
            kc1,kc2 = st.columns(2)

            with kc1:
                st.markdown("**SPY**")
                spy_lv = levels.get("SPY",{})
                if spy_lv:
                    lk1,lk2,lk3 = st.columns(3)
                    lk1.metric("Prev High",
                               f"${spy_lv['pdh']:.2f}")
                    lk2.metric("Prev Close",
                               f"${spy_lv['pdc']:.2f}")
                    lk3.metric("Prev Low",
                               f"${spy_lv['pdl']:.2f}")

            with kc2:
                st.markdown("**QQQ**")
                qqq_lv = levels.get("QQQ",{})
                if qqq_lv:
                    qk1,qk2,qk3 = st.columns(3)
                    qk1.metric("Prev High",
                               f"${qqq_lv['pdh']:.2f}")
                    qk2.metric("Prev Close",
                               f"${qqq_lv['pdc']:.2f}")
                    qk3.metric("Prev Low",
                               f"${qqq_lv['pdl']:.2f}")

            if events:
                st.divider()
                st.subheader("📅 Today's Events")
                for ev in events:
                    ic = ("#CC0000" if ev[3]=="High"
                          else "#FF8C00")
                    actual   = ev[1]
                    previous = ev[2]
                    diff_txt = ""
                    if actual and previous:
                        diff = float(actual)-float(previous)
                        diff_txt = (f" ↑ {diff:+.2f}"
                                    if diff > 0
                                    else f" ↓ {diff:+.2f}")
                    st.markdown(card(
                        f'<span style="color:{ic};'
                        f'font-size:11px;font-weight:bold;">'
                        f'[{ev[3]}]</span>'
                        f'<span style="color:#333;'
                        f'font-size:13px;margin-left:8px;">'
                        f'{ev[0]}</span>'
                        f'<span style="color:#888;'
                        f'font-size:12px;margin-left:12px;">'
                        f'A:{actual} P:{previous}'
                        f'{diff_txt}</span>',
                        border_color=ic
                    ), unsafe_allow_html=True)
            else:
                st.info(
                    f"No events for {today}. "
                    f"Add via Kaggle add_todays_events([])"
                )

    # ══════════════════════════════════════════════════════════
    # TAB 2 — DECISION SUPPORT
    # ══════════════════════════════════════════════════════════
    with tabs[1]:
        st.subheader("🎯 Decision Support")
        report = get_latest_report()
        levels = get_spy_levels()

        if not report:
            st.warning("Run morning script first.")
        else:
            rpt_date = report.get("report_date", today)
            if str(rpt_date) != str(today):
                st.info(f"Showing data from {rpt_date}")

            st.markdown("### Timeframe Alignment")
            al_score = report.get("alignment_score") or 50
            al_label = report.get("alignment","Unknown")
            daily_tr = report.get("daily_trend","Unknown")
            hourly   = report.get("hourly_bias","Unknown")
            m15      = report.get("m15_bias","Unknown")

            tc1,tc2,tc3,tc4 = st.columns(4)
            tc1.metric("Daily Trend",     daily_tr)
            tc2.metric("1-Hour Bias",     hourly)
            tc3.metric("15-Min Bias",     m15)
            tc4.metric("Alignment Score",
                       f"{al_score}/100")

            al_color = ("#0066CC" if al_score >= 58
                        else "#CC0000" if al_score <= 42
                        else "#FF8C00")
            st.markdown(card(
                f'<p style="color:#666;font-size:11px;'
                f'margin:0;">ALIGNMENT</p>'
                f'<p style="color:{al_color};font-size:15px;'
                f'font-weight:bold;margin:4px 0 0;">'
                f'{al_label}</p>',
                border_color=al_color
            ), unsafe_allow_html=True)

            st.divider()
            st.markdown("### Previous Day Key Levels")
            lc1,lc2 = st.columns(2)

            with lc1:
                st.markdown("**SPY**")
                spy_lv = levels.get("SPY",{})
                if spy_lv:
                    sk1,sk2,sk3 = st.columns(3)
                    sk1.metric("PDH",
                        f"${spy_lv['pdh']:.2f}",
                        "Resistance")
                    sk2.metric("PDC",
                        f"${spy_lv['pdc']:.2f}",
                        "Pivot")
                    sk3.metric("PDL",
                        f"${spy_lv['pdl']:.2f}",
                        "Support")

            with lc2:
                st.markdown("**QQQ**")
                qqq_lv = levels.get("QQQ",{})
                if qqq_lv:
                    qk1,qk2,qk3 = st.columns(3)
                    qk1.metric("PDH",
                        f"${qqq_lv['pdh']:.2f}",
                        "Resistance")
                    qk2.metric("PDC",
                        f"${qqq_lv['pdc']:.2f}",
                        "Pivot")
                    qk3.metric("PDL",
                        f"${qqq_lv['pdl']:.2f}",
                        "Support")

            div_sig = report.get("divergence_signal","")
            if div_sig:
                st.divider()
                st.markdown("### Divergence Alert")
                st.warning(f"**{div_sig}**")

    # ══════════════════════════════════════════════════════════
    # TAB 3 — RISK ADVISORY
    # ══════════════════════════════════════════════════════════
    with tabs[2]:
        st.subheader("⚖️ Risk Advisory")
        col_b, col_c = st.columns(2)

        with col_b:
            st.markdown("### Today's Risk Budget")
            account = st.number_input(
                "Account size ($)",
                min_value=1000,
                max_value=1000000,
                value=10000,
                step=1000
            )
            risk_tier = st.radio(
                "Risk tier",
                ["0.25% — Minimal",
                 "0.50% — Reduced",
                 "0.75% — Normal",
                 "1.00% — Full"],
                index=1
            )
            risk_map = {
                "0.25% — Minimal": 0.25,
                "0.50% — Reduced": 0.50,
                "0.75% — Normal":  0.75,
                "1.00% — Full":    1.00
            }
            risk_pct  = risk_map[risk_tier]
            max_risk  = round(account * risk_pct/100, 2)
            daily_lim = round(max_risk * 3, 2)

            report = get_latest_report()
            tp = (report.get("trade_prob",45)
                  if report else 45)
            max_trades = (1 if tp < 45
                          else 2 if tp < 60
                          else 3)

            rc1,rc2 = st.columns(2)
            rc1.metric("Max Risk/Trade",
                       f"${max_risk:,.2f}",
                       f"{risk_pct}% of account")
            rc2.metric("Daily Loss Limit",
                       f"${daily_lim:,.2f}",
                       f"Max {max_trades} trades")

            if report and report.get("is_event_day"):
                st.warning(
                    "⚠️ Event day — consider lower tier")

        with col_c:
            st.markdown("### Trade Calculator")
            ticker_c = st.selectbox(
                "Ticker",
                ["NQ","ES","MNQ","MES","SPY","QQQ"],
                key="calc_ticker"
            )
            pv_map = {
                "NQ":20,"ES":50,"MNQ":2,
                "MES":5,"SPY":1,"QQQ":1
            }
            pv = pv_map.get(ticker_c, 1)

            entry = st.number_input(
                "Entry price",
                value=21500.0,
                step=0.25,
                format="%.2f"
            )
            stop = st.number_input(
                "Stop loss",
                value=21480.0,
                step=0.25,
                format="%.2f"
            )

            if entry != stop:
                rps       = abs(entry - stop)
                direction = ("Long" if stop < entry
                             else "Short")
                dollar_risk = rps * pv
                contracts   = max(1, int(
                    max_risk/dollar_risk
                )) if dollar_risk > 0 else 1

                t1 = round(
                    entry+rps if direction=="Long"
                    else entry-rps, 2)
                t2 = round(
                    entry+rps*2 if direction=="Long"
                    else entry-rps*2, 2)
                t3 = round(
                    entry+rps*3 if direction=="Long"
                    else entry-rps*3, 2)

                st.markdown(card(
                    f'<b style="color:#333;">'
                    f'{direction} — {contracts} contract(s)'
                    f'</b><br>'
                    f'<span style="color:#666;'
                    f'font-size:12px;">'
                    f'Risk/contract: ${dollar_risk:.2f} | '
                    f'Total: ${dollar_risk*contracts:.2f}'
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

    # ══════════════════════════════════════════════════════════
    # TAB 4 — SENTIMENT
    # ══════════════════════════════════════════════════════════
    with tabs[3]:
        st.subheader("😊 Market Sentiment")
        vix    = get_vix()
        report = get_latest_report()
        events = get_todays_events()

        sc1,sc2,sc3 = st.columns(3)
        vix_lbl = ("Low fear" if vix < 15
                   else "High fear" if vix >= 25
                   else "Moderate")
        sc1.metric("VIX", f"{vix:.2f}", vix_lbl)

        if report:
            ss = report.get("sentiment_score",50)
            vt = report.get("vix_trend","Unknown")
            sc2.metric("Sentiment Score", f"{ss}/100")
            sc3.metric("VIX Trend", vt)

        st.divider()
        if report:
            vix_score = (80 if vix < 15
                         else 65 if vix < 20
                         else 45 if vix < 25
                         else 25)
            sv1,sv2 = st.columns(2)
            with sv1:
                st.markdown("**VIX Signal (60% weight)**")
                vix_col = ("#0066CC" if vix < 15
                           else "#CC0000" if vix >= 25
                           else "#FF8C00")
                st.markdown(
                    f'<p style="color:{vix_col};'
                    f'font-size:18px;font-weight:bold;">'
                    f'{vix_score}/100 — {vix_lbl}</p>',
                    unsafe_allow_html=True
                )
            with sv2:
                st.markdown("**News Signal (40% weight)**")
                combined = (report.get("sentiment_score",50)
                            or 50)
                raw_news = ((combined - vix_score*0.6)/0.4)
                news_sc  = max(10, min(90, round(raw_news)))
                st.markdown(
                    f'<p style="color:#333;font-size:18px;'
                    f'font-weight:bold;">'
                    f'{news_sc}/100</p>'
                    f'<p style="color:#666;font-size:12px;">'
                    f'VADER sentiment</p>',
                    unsafe_allow_html=True
                )

        if events:
            st.divider()
            st.markdown("### Today's Events")
            for ev in events:
                ic = ("#CC0000" if ev[3]=="High"
                      else "#FF8C00")
                actual   = ev[1]
                previous = ev[2]
                arrow = ""
                if actual and previous:
                    diff  = float(actual)-float(previous)
                    arrow = " ↑" if diff > 0 else " ↓"
                st.markdown(card(
                    f'<b style="color:{ic};">[{ev[3]}]</b> '
                    f'<span style="color:#333;">{ev[0]}</span>'
                    f'<br><span style="color:#666;'
                    f'font-size:12px;">'
                    f'A:{actual} P:{previous}{arrow}</span>',
                    border_color=ic
                ), unsafe_allow_html=True)
        else:
            st.info("No events for today yet.")

    # ══════════════════════════════════════════════════════════
    # TAB 5 — MY PROFILE + LAYER 7
    # ══════════════════════════════════════════════════════════
    with tabs[4]:
        events_b, scores_b, today_b, today_t = \
            get_behavioral_data()

        # Behavioral state banner
        today_losses = 0
        hi_behaviors = 0
        if today_t and today_t[0]:
            total_today  = int(today_t[0] or 0)
            wins_today   = int(today_t[1] or 0)
            today_losses = total_today - wins_today
        hi_behaviors = sum(
            1 for b in today_b if b[1]=="High")

        if today_losses >= 2 or hi_behaviors >= 3:
            sc = "#CC0000"; st_txt = "🔴 STOP TRADING"
            st_desc = (f"{today_losses} losses today. "
                       f"Close platform now.")
        elif today_losses >= 1 or hi_behaviors >= 2:
            sc = "#FF6600"; st_txt = "🟠 TILT RISK"
            st_desc = "Elevated risk. Minimum size."
        elif hi_behaviors >= 1:
            sc = "#FF8C00"; st_txt = "🟡 ELEVATED"
            st_desc = "Minor issues. Trade with caution."
        else:
            sc = "#0066CC"; st_txt = "🟢 NORMAL"
            st_desc = "No behavioral concerns today."

        st.markdown(
            f"""
            <div style='background:{sc}15;padding:14px;
            border-radius:8px;border-left:4px solid {sc};
            margin-bottom:12px;'>
            <p style='color:{sc};font-size:18px;
            font-weight:bold;margin:0;'>{st_txt}</p>
            <p style='color:#333;font-size:13px;
            margin:4px 0 0;'>{st_desc}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        col_brief, col_log = st.columns([1,1])

        # Morning brief
        with col_brief:
            st.subheader("📋 Morning Brief")

            if events_b:
                st.markdown(
                    "**Your patterns — last 30 days:**")
                for e in events_b[:5]:
                    cost  = float(e[2] or 0)
                    count = int(e[1])
                    color = ("#CC0000" if cost < -50
                             else "#FF8C00"
                             if cost < 0
                             else "#0066CC")
                    st.markdown(
                        f"""
                        <div style='background:#F8F9FA;
                        padding:8px 12px;border-radius:6px;
                        border-left:3px solid {color};
                        margin-bottom:4px;display:flex;
                        justify-content:space-between;'>
                        <span style='color:{color};
                        font-weight:bold;font-size:12px;'>
                        {e[0]}</span>
                        <span>
                        <span style='color:#666;
                        font-size:12px;'>{count}x</span>
                        <span style='color:{color};
                        font-size:12px;margin-left:12px;'>
                        ${cost:+.0f}</span>
                        </span></div>
                        """,
                        unsafe_allow_html=True
                    )
            else:
                st.info("Log trades to see patterns.")

            st.markdown("**Today's warnings:**")
            shown = 0

            revenge = next(
                (e for e in events_b
                 if e[0]=="Revenge Trading"), None)
            if revenge and int(revenge[1]) >= 1:
                st.markdown(
                    f"""<div style='background:#FFE8E8;
                    padding:8px 12px;border-radius:6px;
                    margin-bottom:4px;'>
                    🔴 <b>Revenge trading</b>
                    ({int(revenge[1])}x)<br>
                    <span style='color:#666;font-size:12px;'>
                    After ANY loss → 30 min break
                    </span></div>""",
                    unsafe_allow_html=True
                )
                shown += 1

            fomo = next(
                (e for e in events_b
                 if e[0]=="FOMO"), None)
            if fomo and int(fomo[1]) >= 1:
                st.markdown(
                    f"""<div style='background:#FFE8E8;
                    padding:8px 12px;border-radius:6px;
                    margin-bottom:4px;'>
                    🔴 <b>FOMO pattern</b>
                    ({int(fomo[1])}x)<br>
                    <span style='color:#666;font-size:12px;'>
                    Check system BEFORE every trade
                    </span></div>""",
                    unsafe_allow_html=True
                )
                shown += 1

            if shown == 0:
                st.success("No major patterns yet.")

            if scores_b:
                st.markdown("**Score trend:**")
                vals  = [int(s[0]) for s in
                         reversed(scores_b)]
                dts   = [str(s[2]) for s in
                         reversed(scores_b)]
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=dts, y=vals,
                    mode="lines+markers",
                    line=dict(color="#0066CC",width=2),
                    marker=dict(size=6)
                ))
                fig.update_layout(
                    height=150,
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
            st.caption("45 seconds — log every trade")

            with st.form("trade_log_form",
                         clear_on_submit=True):
                fc1,fc2 = st.columns(2)
                t_ticker = fc1.selectbox("Ticker",
                    ["NQ","ES","SPY","QQQ","MNQ","MES"])
                t_acct = fc2.selectbox("Account",
                    ["Live","Topstep","Combine","Paper"])

                fc3,fc4 = st.columns(2)
                t_dir = fc3.radio("Direction",
                    ["Long","Short"], horizontal=True)
                t_setup = fc4.selectbox("Setup",
                    ["Momentum","Reversal","Breakout",
                     "Range","Event","Mean Reversion",
                     "Trend Pullback","FOMO",
                     "Revenge","Other"])

                fc5,fc6,fc7 = st.columns(3)
                t_entry = fc5.number_input(
                    "Entry", value=0.0,
                    step=0.25, format="%.2f")
                t_exit  = fc6.number_input(
                    "Exit", value=0.0,
                    step=0.25, format="%.2f")
                t_stop  = fc7.number_input(
                    "Stop", value=0.0,
                    step=0.25, format="%.2f")

                t_emotion = st.slider(
                    "Emotion (1=calm 10=stressed)",
                    min_value=1, max_value=10, value=5)

                fc8,fc9 = st.columns(2)
                t_plan = fc8.radio(
                    "Followed plan?",
                    ["Yes","No"], horizontal=True)
                t_checked = fc9.radio(
                    "Checked system?",
                    ["Yes","No"], horizontal=True)

                t_mistake = st.text_input(
                    "Mistake? (leave blank if none)")

                submitted = st.form_submit_button(
                    "💾 Log Trade",
                    use_container_width=True)

                if submitted and t_entry > 0 and t_exit > 0:
                    pv_map = {
                        "NQ":20,"ES":50,"MNQ":2,
                        "MES":5,"SPY":1,"QQQ":1
                    }
                    pv = pv_map.get(t_ticker, 1)

                    if t_dir == "Long":
                        pnl = (t_exit - t_entry) * pv
                    else:
                        pnl = (t_entry - t_exit) * pv

                    outcome = ("Win" if pnl > 0
                               else "Loss" if pnl < 0
                               else "Scratch")
                    risk  = abs(t_entry - t_stop)
                    pnl_r = round(
                        pnl/(risk*pv), 2
                    ) if risk > 0 else 0

                    # Rapid reentry check
                    reentry_warning = None
                    try:
                        with engine.connect() as conn:
                            last_t = conn.execute(
                                text("""
                                SELECT created_at, pnl
                                FROM trade_journal
                                WHERE market='US'
                                AND trade_date=:td
                                ORDER BY created_at
                                DESC LIMIT 1
                            """), {
                                "td": str(date.today())
                            }).fetchone()

                        if last_t:
                            utc  = pytz.utc
                            mins = abs((
                                datetime.now(utc) -
                                last_t[0]
                            ).total_seconds()) / 60
                            prev = float(last_t[1])
                            if prev < 0 and mins < 30:
                                rem = round(30-mins)
                                reentry_warning = (
                                    f"⛔ Only {mins:.0f}min "
                                    f"since last LOSS. "
                                    f"Wait {rem} more min."
                                )
                            elif mins < 15:
                                rem = round(15-mins)
                                reentry_warning = (
                                    f"⚠️ Only {mins:.0f}min "
                                    f"since last trade. "
                                    f"Wait {rem} more min."
                                )
                    except:
                        pass

                    if reentry_warning:
                        st.error(reentry_warning)
                    else:
                        try:
                            with engine.connect() as conn:
                                rpt = conn.execute(
                                    text("""
                                    SELECT matrix_score,bias
                                    FROM intelligence_reports
                                    WHERE market='US'
                                    AND report_date=:td
                                    ORDER BY created_at
                                    DESC LIMIT 1
                                """), {
                                    "td": str(date.today())
                                }).fetchone()

                                ms   = (int(rpt[0])
                                        if rpt else 50)
                                bias = (rpt[1] if rpt
                                        else "Unknown")

                                conn.execute(text("""
                                    INSERT INTO trade_journal(
                                        market,trade_date,
                                        trade_time,ticker,
                                        account_type,
                                        direction,setup_type,
                                        entry_price,
                                        exit_price,
                                        stop_price,
                                        pnl,pnl_r,
                                        matrix_score,
                                        bias_today,
                                        emotional_state,
                                        followed_plan,
                                        mistake,
                                        checked_system,
                                        pre_trade_gate)
                                    VALUES(
                                        'US',:td,:tt,
                                        :ticker,:acct,
                                        :dir,:setup,
                                        :entry,:exit,
                                        :stop,
                                        :pnl,:pnl_r,
                                        :ms,:bias,
                                        :emotion,:plan,
                                        :mistake,
                                        :checked,:gate)
                                """), {
                                    "td":  str(date.today()),
                                    "tt":  datetime.now(EST
                                        ).strftime("%H:%M"),
                                    "ticker":  t_ticker,
                                    "acct":    t_acct,
                                    "dir":     t_dir,
                                    "setup":   t_setup,
                                    "entry":   t_entry,
                                    "exit":    t_exit,
                                    "stop":    t_stop,
                                    "pnl":     round(pnl,2),
                                    "pnl_r":   pnl_r,
                                    "ms":      ms,
                                    "bias":    bias,
                                    "emotion": t_emotion,
                                    "plan":    t_plan=="Yes",
                                    "mistake": t_mistake,
                                    "checked": t_checked=="Yes",
                                    "gate": (
                                        t_plan=="Yes" and
                                        t_checked=="Yes")
                                })
                                conn.commit()

                            color = ("#0066CC" if pnl > 0
                                     else "#CC0000")
                            st.markdown(
                                f"""
                                <div style='background:
                                {color}15;padding:12px;
                                border-radius:8px;
                                border-left:4px solid
                                {color};'>
                                <b style='color:{color};
                                font-size:16px;'>
                                {outcome} — ${pnl:+.2f}
                                ({pnl_r:+.2f}R)</b>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            st.rerun()

                        except Exception as e:
                            st.error(f"Save failed: {e}")

        # Today's behavioral alerts
        if today_b:
            st.divider()
            st.subheader("⚠️ Today's Behavioral Alerts")
            for b in today_b:
                color = ("#CC0000" if b[1]=="High"
                         else "#FF8C00")
                st.markdown(
                    f"""
                    <div style='background:{color}15;
                    padding:10px 14px;border-radius:6px;
                    border-left:3px solid {color};
                    margin-bottom:6px;'>
                    <b style='color:{color};'>{b[0]}</b>
                    <span style='color:#666;font-size:12px;
                    margin-left:8px;'>
                    {b[1]} — {int(b[2])}x today
                    </span></div>
                    """,
                    unsafe_allow_html=True
                )

        st.divider()
        st.subheader("📊 Trade Journal")

        col_f1,col_f2 = st.columns(2)
        days_filter = col_f1.selectbox(
            "Period",
            ["Today","Last 7 days","Last 30 days"])
        acct_filter = col_f2.selectbox(
            "Account",
            ["All","Live","Topstep","Combine","Paper"])

        days_map = {"Today":1,"Last 7 days":7,
                    "Last 30 days":30}
        trades = get_trade_journal(
            days_map[days_filter])

        if acct_filter != "All":
            trades = [t for t in trades
                      if t[12] == acct_filter]

        if trades:
            total     = len(trades)
            wins      = sum(1 for t in trades
                            if float(t[6]) > 0)
            total_pnl = sum(float(t[6]) for t in trades)
            wr        = round(wins/total*100,1)

            sm1,sm2,sm3,sm4 = st.columns(4)
            sm1.metric("Trades",    total)
            sm2.metric("Win Rate",  f"{wr}%")
            sm3.metric("Total P&L", f"${total_pnl:+.2f}")
            sm4.metric("Avg Emotion",
                round(sum(
                    int(t[8]) for t in trades
                )/total, 1))

            st.divider()
            for t in trades[:20]:
                pnl   = float(t[6])
                pnl_r = float(t[7] or 0)
                color = ("#0066CC" if pnl > 0
                         else "#CC0000" if pnl < 0
                         else "#888")
                em    = ("✅" if pnl > 0
                         else "❌" if pnl < 0
                         else "➖")
                plan  = "✓" if t[9] else "✗"
                st.markdown(
                    f"""
                    <div style='background:#F8F9FA;
                    padding:10px 14px;border-radius:8px;
                    border-left:4px solid {color};
                    margin-bottom:6px;'>
                    <div style='display:flex;
                    justify-content:space-between;'>
                    <span><b style='color:#333;'>
                    {em} {t[2]} {t[3]}</b>
                    <span style='color:#888;
                    font-size:12px;margin-left:8px;'>
                    {t[0]} {t[1] or ''} •
                    {t[10] or ''} • {t[12] or ''}
                    </span></span>
                    <b style='color:{color};'>
                    ${pnl:+.2f} ({pnl_r:+.2f}R)
                    </b></div>
                    <div style='color:#888;font-size:11px;
                    margin-top:4px;'>
                    {float(t[4]):.2f} →
                    {float(t[5]):.2f} •
                    Emotion:{t[8]}/10 • Plan:{plan}
                    {f"• ⚠️ {t[11]}" if t[11] else ""}
                    </div></div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.info("No trades logged yet.")

        # Money leaks
        st.divider()
        st.subheader("💸 Money Leaks")
        start_30 = date.today() - timedelta(days=30)
        try:
            with engine.connect() as conn:
                leaks = conn.execute(text("""
                    SELECT behavior_type,
                           COUNT(*) as cnt,
                           SUM(financial_cost) as cost
                    FROM behavioral_events
                    WHERE market='US'
                    AND event_date >= :start
                    GROUP BY behavior_type
                    ORDER BY cost ASC
                    LIMIT 10
                """), {"start":str(start_30)}).fetchall()

            if leaks:
                costs    = [abs(float(l[2] or 0))
                            for l in leaks]
                max_cost = max(costs) if costs else 1
                max_cost = max(max_cost, 1)

                for l in leaks:
                    cost  = float(l[2] or 0)
                    count = int(l[1])
                    pct   = min(100,
                                abs(cost)/max_cost*100)
                    color = ("#CC0000" if cost < -50
                             else "#FF8C00"
                             if cost < 0
                             else "#0066CC")
                    st.markdown(
                        f"""
                        <div style='background:#F8F9FA;
                        padding:8px 14px;border-radius:6px;
                        margin-bottom:4px;'>
                        <div style='display:flex;
                        justify-content:space-between;'>
                        <span style='color:#333;
                        font-weight:bold;'>{l[0]}</span>
                        <span style='color:{color};
                        font-weight:bold;'>
                        ${cost:+.0f}
                        <span style='color:#888;
                        font-size:11px;
                        font-weight:normal;'>
                        ({count}x)</span></span>
                        </div>
                        <div style='background:#E8E8E8;
                        border-radius:3px;height:4px;
                        margin-top:4px;'>
                        <div style='background:{color};
                        width:{pct:.0f}%;height:4px;
                        border-radius:3px;'>
                        </div></div></div>
                        """,
                        unsafe_allow_html=True
                    )
            else:
                st.info("No behavioral data yet.")
        except Exception as e:
            st.error(f"Could not load: {e}")

        # Forward test record
        st.divider()
        st.subheader("📈 Forward Test Record")
        log_df = get_learning_log_deduped()
        if log_df.empty:
            st.info("No forward test data yet.")
        else:
            total_d = len(log_df)
            correct = log_df["correct"].sum()
            wr_days = round(
                correct/total_d*100,1
            ) if total_d > 0 else 0

            fl1,fl2,fl3 = st.columns(3)
            fl1.metric("Days Tested", total_d)
            fl2.metric("Correct",     int(correct))
            fl3.metric("Accuracy",    f"{wr_days}%")

            st.dataframe(
                log_df[[
                    "date","predicted","actual",
                    "return","correct","score"
                ]],
                use_container_width=True
            )

    # ══════════════════════════════════════════════════════════
    # TAB 6 — SETTINGS
    # ══════════════════════════════════════════════════════════
    with tabs[5]:
        st.subheader("⚙️ Settings & Status")

        st.markdown("### Database Status")
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
                tables = {
                    "price_data":           "Price rows",
                    "vix_data":             "VIX rows",
                    "economic_events":      "Events",
                    "news_headlines":       "Headlines",
                    "sentiment_scores":     "Sentiment",
                    "intelligence_reports": "Reports",
                    "learning_log":         "Learning log",
                    "trade_journal":        "Trade journal",
                    "behavioral_events":    "Behavioral",
                    "behavioral_scores":    "B. Scores"
                }
                cols = st.columns(4)
                i = 0
                for table, label in tables.items():
                    try:
                        r = conn.execute(text(
                            f"SELECT COUNT(*) "
                            f"FROM {table}"))
                        count = r.fetchone()[0]
                        cols[i%4].metric(
                            label, f"{count:,}")
                    except:
                        cols[i%4].metric(label, "N/A")
                    i += 1
        except Exception as e:
            st.error(f"Stats unavailable: {e}")

        st.divider()
        st.markdown("### Layer Status")
        layers = {
            "Layer 1 — Data Pipeline":
                "✅ Railway 24/7",
            "Layer 2 — ML Matrix Engine":
                "✅ Kaggle daily",
            "Layer 3 — Decision Support":
                "✅ Complete",
            "Layer 4 — Risk Advisory":
                "✅ Complete",
            "Layer 5 — Trade Execution":
                "✅ Complete",
            "Layer 6 — Portal":
                "✅ Live",
            "Layer 7 — Behavioral Intel":
                "✅ Complete"
        }
        for layer, status in layers.items():
            st.markdown(f"**{layer}:** {status}")


if __name__ == "__main__":
    main()
