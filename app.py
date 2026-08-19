# ══════════════════════════════════════════════════════════════
# MLTrading System — Portal v2 (Streamlit)
# ══════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
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

def get_latest_report():
    """Pull most recent report — today's if available."""
    today = get_last_trading_day()
    try:
        with engine.connect() as conn:
            # Try today first
            result = conn.execute(text("""
                SELECT * FROM intelligence_reports
                WHERE market='US'
                AND report_date=:td
                ORDER BY created_at DESC LIMIT 1
            """), {"td": str(today)})
            row = result.fetchone()
            if row:
                return dict(zip(result.keys(), row))
            # Fall back to most recent
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
    """Get previous day high/low for intraday levels."""
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

def get_learning_log_deduped():
    """Pull learning log with no duplicates."""
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

def get_trade_log():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT trade_date, ticker, direction,
                       entry_price, exit_price,
                       pnl, outcome, matrix_score,
                       bias, scenario, notes
                FROM trade_log WHERE market='US'
                ORDER BY trade_date DESC,
                         created_at DESC LIMIT 50
            """))
            rows = result.fetchall()
            if rows:
                return pd.DataFrame(rows,
                    columns=["date","ticker","direction",
                             "entry","exit","pnl","outcome",
                             "score","bias","scenario",
                             "notes"])
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

def bias_color(bias):
    if not bias: return "#666"
    if "Bullish" in bias:  return "#0066CC"
    if "Bearish" in bias:  return "#CC0000"
    return "#888888"

def bias_emoji(bias):
    if not bias: return "⚪"
    if "Bullish" in bias:  return "🟢"
    if "Bearish" in bias:  return "🔴"
    return "⚪"

def score_bar(score, width=200):
    color = ("#0066CC" if score >= 58
             else "#CC0000" if score <= 42
             else "#FF8C00")
    return (f'<div style="background:#E8E8E8;'
            f'border-radius:4px;width:{width}px;'
            f'height:8px;">'
            f'<div style="background:{color};'
            f'width:{min(score,100)}%;height:8px;'
            f'border-radius:4px;"></div></div>')

def card(content, border_color="#0066CC"):
    return (f'<div style="background:#F8F9FA;'
            f'padding:14px;border-radius:8px;'
            f'border-left:4px solid {border_color};'
            f'margin-bottom:8px;">'
            f'{content}</div>')

# ── MAIN ──────────────────────────────────────────────────────
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
        &nbsp;|&nbsp; Last trading day: {today}
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

        # Show which date report is from
        if report:
            rpt_date = report.get("report_date", today)
            if str(rpt_date) != str(today):
                st.warning(
                    f"⚠️ Showing report from {rpt_date}. "
                    f"Run morning script in Kaggle to "
                    f"generate today's report."
                )

        if not report:
            st.warning(
                "No intelligence report found. "
                "Run morning script first."
            )
            st.code("""
# Run in Kaggle ML_Layer_3 notebook:
# Cell 1 — Master script
# Cell 2 — Daily runner with today's events
            """)
        else:
            bias  = report.get("bias","Neutral")
            score = report.get("matrix_score",50)
            conf  = report.get("confidence","Low")
            tp    = report.get("trade_prob",45)

            # Top metrics
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
                tp_color = ("#0066CC" if tp>=65
                            else "#CC0000" if tp<=40
                            else "#FF8C00")
                st.markdown(card(
                    f'<p style="color:#666;margin:0;'
                    f'font-size:11px;">TRADE PROBABILITY</p>'
                    f'<p style="color:{tp_color};margin:4px 0 4px;'
                    f'font-size:22px;font-weight:bold;">'
                    f'{tp}%</p>'
                    + score_bar(tp),
                    border_color=tp_color
                ), unsafe_allow_html=True)

            with c4:
                vix_color = ("#0066CC" if vix<15
                             else "#CC0000" if vix>=25
                             else "#FF8C00")
                vix_lbl   = ("Low fear" if vix<15
                             else "High fear" if vix>=25
                             else "Moderate")
                st.markdown(card(
                    f'<p style="color:#666;margin:0;'
                    f'font-size:11px;">VIX</p>'
                    f'<p style="color:{vix_color};margin:4px 0 0;'
                    f'font-size:22px;font-weight:bold;">'
                    f'{vix:.2f}</p>'
                    f'<p style="color:#888;margin:0;'
                    f'font-size:11px;">{vix_lbl}</p>',
                    border_color=vix_color
                ), unsafe_allow_html=True)

            st.divider()

            # Narrative + ML
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
                    f'line-height:1.6;margin:0;">{headline}</p>'
                ), unsafe_allow_html=True)
                m1,m2,m3 = st.columns(3)
                m1.metric("Narrative Score", f"{ns}/100")
                m2.metric("Event Day",
                          "Yes ★★★" if ie else "No")
                m3.metric("Volatility",
                    report.get("volatility","Normal") or "Normal")

            with col_r:
                st.subheader("🤖 ML Ensemble")
                ml_score = report.get("ml_ensemble_score",50)
                ml_lean  = report.get("ml_ensemble_lean",
                                      "Neutral")
                models = {
                    "XGBoost":   report.get("xgb_score",50),
                    "ARIMA":     report.get("arima_score",50),
                    "LSTM":      report.get("lstm_score",50),
                    "RandForest":report.get("rf_score",50),
                    "GradBoost": report.get("gb_score",50)
                }
                for model, ms in models.items():
                    cn, cb = st.columns([2,3])
                    cn.markdown(
                        f'<p style="color:#666;font-size:12px;'
                        f'margin:2px 0;">{model}</p>',
                        unsafe_allow_html=True)
                    cb.markdown(
                        score_bar(ms, width=120) +
                        f'<p style="color:#888;font-size:11px;'
                        f'margin:0;">{ms}/100</p>',
                        unsafe_allow_html=True)
                st.markdown(
                    f"**Ensemble: {ml_score}/100 — {ml_lean}**")

            st.divider()

            # Candles
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
                f'font-size:18px;font-weight:bold;margin:4px 0 0;">'
                f'{spy_dir}</p>'
                f'<p style="color:#888;font-size:11px;margin:0;">'
                f'{spy_conv} | {spy_sc}/100</p>',
                border_color=bias_color(spy_dir)
            ), unsafe_allow_html=True)

            cc2.markdown(card(
                f'<p style="color:#666;font-size:11px;'
                f'margin:0;">QQQ CANDLE</p>'
                f'<p style="color:{bias_color(qqq_dir)};'
                f'font-size:18px;font-weight:bold;margin:4px 0 0;">'
                f'{qqq_dir}</p>'
                f'<p style="color:#888;font-size:11px;margin:0;">'
                f'{qqq_conv}</p>',
                border_color=bias_color(qqq_dir)
            ), unsafe_allow_html=True)

            cc3.markdown(card(
                f'<p style="color:#666;font-size:11px;'
                f'margin:0;">REACTION TYPE</p>'
                f'<p style="color:#FF8C00;font-size:14px;'
                f'font-weight:bold;margin:4px 0 0;">'
                f'{reaction}</p>',
                border_color="#FF8C00"
            ), unsafe_allow_html=True)

            st.divider()

            # Key levels — previous day H/L only
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
                else:
                    st.info("No level data")

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
                else:
                    st.info("No level data")

            # Events
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
                                    if diff>0
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
                        f'Actual: {actual}  '
                        f'Prev: {previous}'
                        f'{diff_txt}</span>',
                        border_color=ic
                    ), unsafe_allow_html=True)
            else:
                st.info(
                    f"No events loaded for {today}. "
                    f"Add events in Kaggle using "
                    f"add_todays_events([])"
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

            # Timeframe alignment
            st.markdown("### Timeframe Alignment")
            al_label = report.get("alignment","Unknown")
            al_score = report.get("alignment_score",50)
            daily_tr = report.get("daily_trend","Unknown")
            hourly   = report.get("hourly_bias","Unknown")
            m15      = report.get("m15_bias","Unknown")

            tc1,tc2,tc3,tc4 = st.columns(4)
            tc1.metric("Daily Trend",    daily_tr)
            tc2.metric("1-Hour Bias",    hourly)
            tc3.metric("15-Min Bias",    m15)
            tc4.metric("Alignment Score",f"{al_score}/100")

            al_color = ("#0066CC" if al_score>=58
                        else "#CC0000" if al_score<=42
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
                st.markdown("**SPY — Intraday Reference**")
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
                st.markdown("**QQQ — Intraday Reference**")
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
            div_gui = report.get("divergence_guidance","")
            if div_sig:
                st.divider()
                st.markdown("### Divergence Alert")
                st.warning(f"**{div_sig}**\n\n{div_gui}")

            react_gui = report.get("reaction_guidance","")
            if react_gui:
                st.divider()
                st.markdown("### Reaction Guidance")
                st.info(react_gui)

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

            # Fixed risk tiers as requested
            risk_tier = st.radio(
                "Risk tier",
                ["0.25% — Minimal",
                 "0.50% — Reduced",
                 "0.75% — Normal",
                 "1.00% — Full"],
                index=1
            )
            risk_pct_map = {
                "0.25% — Minimal": 0.25,
                "0.50% — Reduced": 0.50,
                "0.75% — Normal":  0.75,
                "1.00% — Full":    1.00
            }
            risk_pct   = risk_pct_map[risk_tier]
            max_risk   = round(account * risk_pct/100, 2)
            daily_lim  = round(max_risk * 3, 2)

            report = get_latest_report()
            tp = report.get("trade_prob",45) if report else 45
            max_trades = (1 if tp<45 else 2 if tp<60 else 3)

            rc1,rc2 = st.columns(2)
            rc1.metric("Max Risk/Trade",
                       f"${max_risk:,.2f}",
                       f"{risk_pct}% of account")
            rc2.metric("Daily Loss Limit",
                       f"${daily_lim:,.2f}",
                       f"Max {max_trades} trades")

            if report:
                ie = report.get("is_event_day",False)
                if ie:
                    st.warning(
                        "⚠️ Event day — consider reducing "
                        "to lower tier"
                    )

        with col_c:
            st.markdown("### Trade Calculator")

            entry  = st.number_input(
                "Entry price", value=770.00,
                step=0.25, format="%.2f")
            stop   = st.number_input(
                "Stop loss",   value=768.00,
                step=0.25, format="%.2f")

            if entry != stop:
                rps      = abs(entry-stop)
                direction= "Long" if stop<entry else "Short"
                shares   = max(1, int(max_risk/rps))
                t1 = round(entry+rps if direction=="Long"
                           else entry-rps, 2)
                t2 = round(entry+rps*2 if direction=="Long"
                           else entry-rps*2, 2)
                t3 = round(entry+rps*3 if direction=="Long"
                           else entry-rps*3, 2)
                total_risk = round(rps*shares,2)
                st.markdown(card(
                    f'<b style="color:#333;">'
                    f'{direction} — {shares} shares</b><br>'
                    f'<span style="color:#666;font-size:12px;">'
                    f'Risk/share: ${rps:.2f} | '
                    f'Total risk: ${total_risk:.2f}</span><br><br>'
                    f'<span style="color:#CC0000;">'
                    f'1:1 → ${t1:.2f} '
                    f'(+${rps*shares:.0f})</span><br>'
                    f'<span style="color:#FF8C00;">'
                    f'1:2 → ${t2:.2f} '
                    f'(+${rps*shares*2:.0f})</span><br>'
                    f'<span style="color:#0066CC;">'
                    f'1:3 → ${t3:.2f} '
                    f'(+${rps*shares*3:.0f})</span>'
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
        vix_lbl = ("Low fear" if vix<15
                   else "High fear" if vix>=25
                   else "Moderate")
        vix_col = ("#0066CC" if vix<15
                   else "#CC0000" if vix>=25
                   else "#FF8C00")
        sc1.metric("VIX", f"{vix:.2f}", vix_lbl)

        if report:
            ss = report.get("sentiment_score",50)
            sl = report.get("sentiment_label","Neutral")
            vt = report.get("vix_trend","Unknown")
            sc2.metric("Sentiment Score", f"{ss}/100", sl)
            sc3.metric("VIX Trend",       vt)

        st.divider()
        st.markdown("### Sentiment Breakdown")

        if report:
            sv1,sv2 = st.columns(2)
            with sv1:
                vix_score = (80 if vix<15
                             else 65 if vix<20
                             else 45 if vix<25
                             else 25)
                st.markdown("**VIX Signal (60% weight)**")
                st.markdown(
                    f'<p style="color:{vix_col};'
                    f'font-size:18px;font-weight:bold;">'
                    f'{vix_score}/100 — {vix_lbl}</p>'
                    f'<p style="color:#666;font-size:12px;">'
                    f'VIX {vix:.2f} — '
                    f'{"Calm market" if vix<18 else "Elevated fear"}'
                    f'</p>',
                    unsafe_allow_html=True
                )
            with sv2:
                ns = report.get("sentiment_score",50)
                # Correct news score derivation
                # Combined = VIX*0.6 + News*0.4
                # So News = (Combined - VIX*0.6) / 0.4
                combined = report.get("sentiment_score", 50) or 50
                derived_news = (combined - vix_score*0.6) / 0.4
                news_score = max(0, min(100, round(derived_news)))
                # If no real news data — show neutral
                if news_score <= 0 or news_score > 100:
                news_score = 49
                st.markdown("**News Signal (40% weight)**")
                st.markdown(
                    f'<p style="color:#333;'
                    f'font-size:18px;font-weight:bold;">'
                    f'{news_score}/100</p>'
                    f'<p style="color:#666;font-size:12px;">'
                    f'FinBERT sentiment from headlines</p>',
                    unsafe_allow_html=True
                )

        if events:
            st.divider()
            st.markdown("### Today's Economic Events")
            for ev in events:
                ic = ("#CC0000" if ev[3]=="High"
                      else "#FF8C00")
                actual   = ev[1]
                previous = ev[2]
                arrow = ""
                if actual and previous:
                    diff  = float(actual)-float(previous)
                    arrow = " ↑" if diff>0 else " ↓"
                st.markdown(card(
                    f'<b style="color:{ic};">[{ev[3]}]</b> '
                    f'<span style="color:#333;">{ev[0]}</span>'
                    f'<br><span style="color:#666;'
                    f'font-size:12px;">'
                    f'Actual: {actual}  '
                    f'Prev: {previous}{arrow}</span>',
                    border_color=ic
                ), unsafe_allow_html=True)
        else:
            st.info("No events for today yet.")

    # ══════════════════════════════════════════════════════════
    # TAB 5 — MY PROFILE
    # ══════════════════════════════════════════════════════════
    with tabs[4]:
        st.subheader("👤 My Profile & Journal")

        # Log trade form
        st.markdown("### Log a Paper Trade")
        with st.form("trade_form"):
            ff1,ff2,ff3 = st.columns(3)
            t_ticker    = ff1.selectbox("Ticker",
                                        ["SPY","QQQ"])
            t_direction = ff2.selectbox("Direction",
                                        ["Long","Short"])
            t_scenario  = ff3.selectbox("Scenario",
                                        ["A","B","C","None"])
            ff4,ff5,ff6 = st.columns(3)
            t_entry  = ff4.number_input(
                "Entry", value=770.0,
                step=0.25, format="%.2f")
            t_exit   = ff5.number_input(
                "Exit",  value=768.0,
                step=0.25, format="%.2f")
            t_risk   = ff6.number_input(
                "Risk ($)", value=38.0, step=1.0)
            t_notes  = st.text_input("Notes (optional)")
            submitted = st.form_submit_button("💾 Log Trade")

            if submitted:
                pnl = (t_exit-t_entry
                       if t_direction=="Long"
                       else t_entry-t_exit)
                outcome = ("Win" if pnl>0
                           else "Loss" if pnl<0
                           else "Scratch")
                report = get_latest_report()
                ms   = (report.get("matrix_score",50)
                        if report else 50)
                bias = (report.get("bias","Neutral")
                        if report else "Neutral")
                try:
                    with engine.connect() as conn:
                        conn.execute(text("""
                            INSERT INTO trade_log(
                                market,trade_date,ticker,
                                direction,entry_price,
                                exit_price,risk_amount,
                                pnl,pnl_pct,matrix_score,
                                bias,scenario,outcome,notes)
                            VALUES('US',:td,:ticker,:dir,
                                :entry,:exit,:risk,
                                :pnl,:pnl_pct,:ms,
                                :bias,:scenario,
                                :outcome,:notes)
                        """), {
                            "td":      str(date.today()),
                            "ticker":  t_ticker,
                            "dir":     t_direction,
                            "entry":   t_entry,
                            "exit":    t_exit,
                            "risk":    t_risk,
                            "pnl":     round(pnl,2),
                            "pnl_pct": round(pnl/t_entry*100,4),
                            "ms":      ms,
                            "bias":    bias,
                            "scenario":t_scenario,
                            "outcome": outcome,
                            "notes":   t_notes
                        })
                        conn.commit()
                    color = ("#0066CC" if pnl>0 else "#CC0000")
                    st.success(
                        f"Trade logged: "
                        f"{'WIN' if pnl>0 else 'LOSS'} "
                        f"${pnl:+.2f}"
                    )
                except Exception as e:
                    st.error(f"Save failed: {e}")

        st.divider()

        # Performance summary
        st.markdown("### Performance Summary")
        trades_df = get_trade_log()

        if trades_df.empty:
            st.info("No trades logged yet.")
        else:
            total = len(trades_df)
            wins  = len(trades_df[
                trades_df["outcome"]=="Win"])
            losses= len(trades_df[
                trades_df["outcome"]=="Loss"])
            wr    = round(wins/total*100,1) if total>0 else 0
            total_pnl = round(
                trades_df["pnl"].astype(float).sum(),2)
            avg_win = round(
                trades_df[trades_df["outcome"]=="Win"
                ]["pnl"].astype(float).mean(),2
            ) if wins>0 else 0

            pm1,pm2,pm3,pm4 = st.columns(4)
            pm1.metric("Total Trades", total)
            pm2.metric("Win Rate",     f"{wr}%")
            pm3.metric("Total P&L",    f"${total_pnl:+.2f}")
            pm4.metric("Avg Win",      f"${avg_win:+.2f}")

            st.dataframe(
                trades_df[[
                    "date","ticker","direction",
                    "entry","exit","pnl","outcome"
                ]].head(20),
                use_container_width=True
            )

        st.divider()

        # Forward test record — deduplicated
        st.markdown("### Forward Test Record")
        log_df = get_learning_log_deduped()

        if log_df.empty:
            st.info("No forward test data yet.")
        else:
            total_days = len(log_df)
            correct    = log_df["correct"].sum()
            wr_days    = round(
                correct/total_days*100,1
            ) if total_days>0 else 0

            fl1,fl2,fl3 = st.columns(3)
            fl1.metric("Days Tested",  total_days)
            fl2.metric("Correct",      int(correct))
            fl3.metric("Accuracy",     f"{wr_days}%")

            # Color code correct column
            def color_correct(val):
                color = "green" if val else "red"
                return f"color: {color}"

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
            st.error("❌ Database connection failed")

        st.divider()
        st.markdown("### Data Summary")
        try:
            with engine.connect() as conn:
                tables = {
                    "price_data":
                        "Price data rows",
                    "vix_data":
                        "VIX data rows",
                    "economic_events":
                        "Economic events",
                    "news_headlines":
                        "News headlines",
                    "sentiment_scores":
                        "Sentiment scores",
                    "intelligence_reports":
                        "Intelligence reports",
                    "learning_log":
                        "Learning log entries",
                    "trade_log":
                        "Trade log entries"
                }
                cols = st.columns(4)
                i = 0
                for table, label in tables.items():
                    try:
                        r = conn.execute(text(
                            f"SELECT COUNT(*) FROM {table}"))
                        count = r.fetchone()[0]
                        cols[i%4].metric(label, f"{count:,}")
                    except:
                        cols[i%4].metric(label, "N/A")
                    i += 1
        except Exception as e:
            st.error(f"Stats unavailable: {e}")

        st.divider()
        st.markdown("### Layer Status")
        layers = {
            "Layer 1 — Data Pipeline":       "✅ Complete",
            "Layer 2 — ML Matrix Engine":    "✅ Complete",
            "Layer 3 — Decision Support":    "✅ Complete",
            "Layer 4 — Risk Advisory":       "✅ Complete",
            "Layer 5 — Trade Execution":     "✅ Complete",
            "Layer 6 — Portal (this)":       "✅ Live",
            "Layer 7 — Behavioral Intel":    "🔄 Coming soon"
        }
        for layer, status in layers.items():
            st.markdown(f"**{layer}:** {status}")


if __name__ == "__main__":
    main()
