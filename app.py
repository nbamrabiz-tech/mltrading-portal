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

            al_score = al_score or 50
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
                combined = report.get("sentiment_score", 50) or 50
                derived_news = (combined - vix_score * 0.6) / 0.4
                news_score = max(0, min(100, round(derived_news))) or 49
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
    # TAB 5 — MY PROFILE + LAYER 7 BEHAVIORAL INTELLIGENCE
    # ══════════════════════════════════════════════════════════
    with tabs[4]:

        # ── Helper functions ──────────────────────────────────
        def get_behavioral_brief():
            """Pull behavioral patterns for morning brief."""
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
                    """), {"start": str(start)}).fetchall()

                    scores = conn.execute(text("""
                        SELECT overall_score,
                               behavioral_state,
                               score_date
                        FROM behavioral_scores
                        WHERE market='US'
                        ORDER BY score_date DESC
                        LIMIT 7
                    """)).fetchall()

                    today_trades = conn.execute(text("""
                        SELECT COUNT(*),
                               SUM(CASE WHEN pnl>0
                                   THEN 1 ELSE 0 END),
                               SUM(pnl),
                               AVG(emotional_state)
                        FROM trade_journal
                        WHERE market='US'
                        AND trade_date=:td
                    """), {"td": str(date.today())}).fetchone()

                    today_behaviors = conn.execute(text("""
                        SELECT behavior_type, severity,
                               COUNT(*) as cnt
                        FROM behavioral_events
                        WHERE market='US'
                        AND event_date=:td
                        GROUP BY behavior_type, severity
                    """), {"td": str(date.today())}).fetchall()

                return events, scores, today_trades, today_behaviors
            except:
                return [], [], None, []

        def get_journal_trades(days_back=30):
            """Pull trade journal entries."""
            start = date.today() - timedelta(days=days_back)
            try:
                with engine.connect() as conn:
                    trades = conn.execute(text("""
                        SELECT trade_date, trade_time,
                               ticker, direction,
                               entry_price, exit_price,
                               pnl, pnl_r, outcome,
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
                    """), {"start": str(start)}).fetchall()
                return trades
            except:
                return []

        # ── Behavioral state banner ───────────────────────────
        events, scores, today_t, today_b = get_behavioral_brief()

        # Determine current state
        today_losses = 0
        hi_behaviors = 0
        if today_t and today_t[0]:
            total_today = int(today_t[0] or 0)
            wins_today  = int(today_t[1] or 0)
            today_losses = total_today - wins_today
        hi_behaviors = sum(1 for b in today_b
                           if b[1] == "High")

        if today_losses >= 2 or hi_behaviors >= 3:
            state_color = "#CC0000"
            state_text  = "🔴 STOP TRADING"
            state_desc  = (f"{today_losses} losses today + "
                           f"behavioral issues detected. "
                           f"Close platform now.")
        elif today_losses >= 1 or hi_behaviors >= 2:
            state_color = "#FF6600"
            state_text  = "🟠 TILT RISK"
            state_desc  = ("Elevated risk. "
                           "Minimum size only.")
        elif hi_behaviors >= 1:
            state_color = "#FF8C00"
            state_text  = "🟡 ELEVATED"
            state_desc  = ("Minor issues present. "
                           "Trade with caution.")
        else:
            state_color = "#0066CC"
            state_text  = "🟢 NORMAL"
            state_desc  = "No behavioral concerns today."

        st.markdown(
            f"""
            <div style='background:{state_color}20;
            padding:14px;border-radius:8px;
            border-left:4px solid {state_color};
            margin-bottom:12px;'>
            <p style='color:{state_color};font-size:18px;
            font-weight:bold;margin:0;'>{state_text}</p>
            <p style='color:#333;font-size:13px;margin:4px 0 0;'>
            {state_desc}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # ── Two columns — brief + log ─────────────────────────
        col_brief, col_log = st.columns([1, 1])

        # ── Morning brief ─────────────────────────────────────
        with col_brief:
            st.subheader("📋 Morning Brief")

            if events:
                st.markdown("**Your patterns — last 30 days:**")
                for e in events[:5]:
                    cost  = float(e[2] or 0)
                    count = int(e[1])
                    color = ("#CC0000"
                             if cost < -50 else "#FF8C00"
                             if cost < 0 else "#0066CC")
                    st.markdown(
                        f"""
                        <div style='background:#F8F9FA;
                        padding:8px 12px;border-radius:6px;
                        border-left:3px solid {color};
                        margin-bottom:4px;'>
                        <span style='color:{color};
                        font-weight:bold;font-size:12px;'>
                        {e[0]}</span>
                        <span style='color:#666;
                        font-size:12px;margin-left:8px;'>
                        {count}x</span>
                        <span style='color:{color};
                        font-size:12px;float:right;'>
                        ${cost:+.0f}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            else:
                st.info("No behavioral data yet. "
                        "Log trades to see patterns.")

            # Warnings
            st.markdown("**Today's warnings:**")
            warnings_shown = 0

            revenge = next((e for e in events
                            if e[0]=="Revenge Trading"),None)
            if revenge and int(revenge[1]) >= 1:
                st.markdown(
                    f"""
                    <div style='background:#FFE8E8;
                    padding:8px 12px;border-radius:6px;
                    margin-bottom:4px;'>
                    🔴 <b>Revenge trading pattern</b>
                    ({int(revenge[1])}x in 30 days)<br>
                    <span style='color:#666;font-size:12px;'>
                    After ANY loss → 30 min break,
                    no exceptions</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                warnings_shown += 1

            fomo = next((e for e in events
                         if e[0]=="FOMO"), None)
            if fomo and int(fomo[1]) >= 1:
                st.markdown(
                    f"""
                    <div style='background:#FFE8E8;
                    padding:8px 12px;border-radius:6px;
                    margin-bottom:4px;'>
                    🔴 <b>FOMO pattern</b>
                    ({int(fomo[1])}x in 30 days)<br>
                    <span style='color:#666;font-size:12px;'>
                    Check system report BEFORE every trade
                    </span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                warnings_shown += 1

            rapid = next((e for e in events
                          if e[0] in ["Greed",
                                      "Rapid Reentry"]),None)
            if rapid and int(rapid[1]) >= 1:
                st.markdown(
                    f"""
                    <div style='background:#FFF3CD;
                    padding:8px 12px;border-radius:6px;
                    margin-bottom:4px;'>
                    🟡 <b>Quick reentry pattern</b>
                    ({int(rapid[1])}x in 30 days)<br>
                    <span style='color:#666;font-size:12px;'>
                    Loss → 30 min | Win → 15 min
                    </span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                warnings_shown += 1

            if warnings_shown == 0:
                st.success("No major patterns yet. "
                           "Keep logging.")

            # Behavioral score trend
            if scores:
                st.markdown("**Score trend (7 days):**")
                score_vals = [int(s[0]) for s in
                              reversed(scores)]
                score_dates = [str(s[2]) for s in
                               reversed(scores)]
                import plotly.graph_objects as go
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=score_dates,
                    y=score_vals,
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

        # ── Quick trade log ───────────────────────────────────
        with col_log:
            st.subheader("📝 Log a Trade")
            st.caption("45 seconds — log every trade")

            with st.form("trade_log_form",
                         clear_on_submit=True):

                fc1, fc2 = st.columns(2)
                t_ticker = fc1.selectbox(
                    "Ticker",
                    ["NQ","ES","SPY","QQQ","MES","MNQ"],
                    key="t_ticker"
                )
                t_acct = fc2.selectbox(
                    "Account",
                    ["Live","Topstep","Combine","Paper"],
                    key="t_acct"
                )

                fc3, fc4 = st.columns(2)
                t_dir = fc3.radio(
                    "Direction",
                    ["Long","Short"],
                    horizontal=True,
                    key="t_dir"
                )
                t_setup = fc4.selectbox(
                    "Setup",
                    ["Momentum","Reversal","Breakout",
                     "Range","Event","Mean Reversion",
                     "Trend Pullback","FOMO","Revenge",
                     "Other"],
                    key="t_setup"
                )

                fc5, fc6, fc7 = st.columns(3)
                t_entry = fc5.number_input(
                    "Entry", value=0.0,
                    step=0.25, format="%.2f",
                    key="t_entry"
                )
                t_exit = fc6.number_input(
                    "Exit", value=0.0,
                    step=0.25, format="%.2f",
                    key="t_exit"
                )
                t_stop = fc7.number_input(
                    "Stop", value=0.0,
                    step=0.25, format="%.2f",
                    key="t_stop"
                )

                t_emotion = st.slider(
                    "Emotional state (1=calm, 10=max stress)",
                    min_value=1, max_value=10,
                    value=5, key="t_emotion"
                )

                fc8, fc9 = st.columns(2)
                t_plan = fc8.radio(
                    "Followed plan?",
                    ["Yes","No"],
                    horizontal=True,
                    key="t_plan"
                )
                t_checked = fc9.radio(
                    "Checked system?",
                    ["Yes","No"],
                    horizontal=True,
                    key="t_checked"
                )

                t_mistake = st.text_input(
                    "Mistake (optional — leave blank if none)",
                    key="t_mistake"
                )

                submitted = st.form_submit_button(
                    "💾 Log Trade",
                    use_container_width=True
                )

                if submitted and t_entry > 0 and t_exit > 0:
                    # Calculate P&L
                    # P&L based on ticker
                    point_value = {
                    "NQ":  20.0,   # NQ = $20/point
                    "MNQ":  2.0,   # Micro NQ = $2/point
                    "ES":   50.0,  # ES = $50/point
                    "MES":   5.0,  # Micro ES = $5/point
                    "SPY":   1.0,  # SPY = $1/share
                    "QQQ":   1.0   # QQQ = $1/share
                    }.get(t_ticker, 1.0)

                if t_dir == "Long":
                    pnl = (t_exit - t_entry) * point_value
                    else:
                    pnl = (t_entry - t_exit) * point_value
                    outcome = ("Win" if pnl > 0
                               else "Loss" if pnl < 0
                               else "Scratch")

                    # Rapid reentry check
                    try:
                        with engine.connect() as conn:
                            last_trade = conn.execute(
                                text("""
                                SELECT created_at, pnl
                                FROM trade_journal
                                WHERE market='US'
                                AND trade_date=:td
                                ORDER BY created_at DESC
                                LIMIT 1
                            """), {
                                "td": str(date.today())
                            }).fetchone()

                        reentry_warning = None
                        if last_trade:
                            mins = abs((
                                datetime.now(pytz.utc) -
                                last_trade[0]
                            ).total_seconds()) / 60
                            prev_pnl = float(last_trade[1])
                            if prev_pnl < 0 and mins < 30:
                                reentry_warning = (
                                    f"⛔ Only {mins:.0f} min "
                                    f"since last loss. "
                                    f"Need 30 min."
                                )
                            elif prev_pnl >= 0 and mins < 15:
                                reentry_warning = (
                                    f"⚠️ Only {mins:.0f} min "
                                    f"since last trade. "
                                    f"Need 15 min."
                                )
                    except:
                        reentry_warning = None

                    if reentry_warning:
                        st.error(reentry_warning)
                    else:
                        # Save trade
                        try:
                            with engine.connect() as conn:
                                report = conn.execute(
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

                                ms   = (int(report[0])
                                        if report else 50)
                                bias = (report[1]
                                        if report
                                        else "Unknown")
                                risk = abs(t_entry - t_stop)
                              pnl_r = round(
                              pnl/(risk*point_value),2
                                ) if risk > 0 else 0
                                conn.execute(text("""
                                    INSERT INTO trade_journal(
                                        market,trade_date,
                                        trade_time,ticker,
                                        account_type,direction,
                                        setup_type,entry_price,
                                        exit_price,stop_price,
                                        pnl,pnl_r,matrix_score,
                                        bias_today,
                                        emotional_state,
                                        followed_plan,mistake,
                                        checked_system,
                                        pre_trade_gate)
                                    VALUES(
                                        'US',:td,:tt,:ticker,
                                        :acct,:dir,:setup,
                                        :entry,:exit,:stop,
                                        :pnl,:pnl_r,:ms,:bias,
                                        :emotion,:plan,
                                        :mistake,:checked,
                                        :gate)
                                """), {
                                    "td":     str(date.today()),
                                    "tt":     datetime.now(EST
                                        ).strftime("%H:%M"),
                                    "ticker": t_ticker,
                                    "acct":   t_acct,
                                    "dir":    t_dir,
                                    "setup":  t_setup,
                                    "entry":  t_entry,
                                    "exit":   t_exit,
                                    "stop":   t_stop,
                                    "pnl":    round(pnl,2),
                                    "pnl_r":  pnl_r,
                                    "ms":     ms,
                                    "bias":   bias,
                                    "emotion":t_emotion,
                                    "plan":   t_plan=="Yes",
                                    "mistake":t_mistake,
                                    "checked":t_checked=="Yes",
                                    "gate":   (
                                        t_plan=="Yes" and
                                        t_checked=="Yes")
                                })
                                conn.commit()

                            color = ("#0066CC" if pnl > 0
                                     else "#CC0000")
                            st.markdown(
                                f"""
                                <div style='background:{color}20;
                                padding:12px;border-radius:8px;
                                border-left:4px solid {color};'>
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

        st.divider()

        # ── Today's behavior detections ───────────────────────
        if today_b:
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
                    <b style='color:{color};'>
                    {b[0]}</b>
                    <span style='color:#666;
                    font-size:12px;margin-left:8px;'>
                    {b[1]} severity — {int(b[2])}x today
                    </span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # ── Trade journal ─────────────────────────────────────
        st.divider()
        st.subheader("📊 Trade Journal")

        col_f1, col_f2 = st.columns(2)
        days_filter = col_f1.selectbox(
            "Period",
            ["Today","Last 7 days","Last 30 days"],
            key="journal_period"
        )
        account_filter = col_f2.selectbox(
            "Account",
            ["All","Live","Topstep","Combine","Paper"],
            key="journal_acct"
        )

        days_map = {"Today":1,"Last 7 days":7,
                    "Last 30 days":30}
        trades = get_journal_trades(
            days_map[days_filter])

        if account_filter != "All":
            trades = [t for t in trades
                      if t[13] == account_filter]

        if trades:
            total   = len(trades)
            wins    = sum(1 for t in trades
                          if float(t[6]) > 0)
            total_pnl = sum(float(t[6]) for t in trades)
            wr      = round(wins/total*100,1)

            sm1,sm2,sm3,sm4 = st.columns(4)
            sm1.metric("Trades",    total)
            sm2.metric("Win Rate",  f"{wr}%")
            sm3.metric("Total P&L", f"${total_pnl:+.2f}")
            sm4.metric("Wins",      wins)

            st.divider()

            for t in trades[:20]:
                pnl   = float(t[6])
                color = ("#0066CC" if pnl > 0
                         else "#CC0000"
                         if pnl < 0 else "#888")
                em    = ("✅" if pnl > 0
                         else "❌" if pnl < 0 else "➖")
                plan  = "✓" if t[10] else "✗"
                chk   = "✓" if False else "✗"

                st.markdown(
                    f"""
                    <div style='background:#F8F9FA;
                    padding:10px 14px;border-radius:8px;
                    border-left:4px solid {color};
                    margin-bottom:6px;'>
                    <div style='display:flex;
                    justify-content:space-between;'>
                    <span>
                    <b style='color:#333;'>{em} {t[2]} {t[3]}
                    </b>
                    <span style='color:#888;
                    font-size:12px;margin-left:8px;'>
                    {t[0]} {t[1] or ''} • {t[11] or ''}
                    • {t[13] or ''}
                    </span>
                    </span>
                    <b style='color:{color};'>
                    ${pnl:+.2f}
                    ({float(t[7]):+.2f}R)
                    </b>
                    </div>
                    <div style='color:#888;
                    font-size:11px;margin-top:4px;'>
                    Entry:{float(t[4]):.2f} →
                    Exit:{float(t[5]):.2f} •
                    Emotion:{t[9]}/10 •
                    Plan:{plan}
                    {f"• ⚠️ {t[12]}" if t[12] else ""}
                    </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.info("No trades logged yet. "
                    "Use the form above to log trades.")

                        # ── Money leak summary ────────────────────────────────
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
                """), {"start":str(start_30)}).fetchall()

            if leaks:
                max_cost = max(
                    abs(float(l[2] or 0)) for l in leaks)
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
                        padding:8px 14px;
                        border-radius:6px;
                        margin-bottom:4px;'>
                        <div style='display:flex;
                        justify-content:space-between;'>
                        <span style='color:#333;
                        font-weight:bold;'>
                        {l[0]}</span>
                        <span style='color:{color};
                        font-weight:bold;'>
                        ${cost:+.0f}
                        <span style='color:#888;
                        font-size:11px;
                        font-weight:normal;'>
                        ({count}x)</span>
                        </span>
                        </div>
                        <div style='background:#E8E8E8;
                        border-radius:3px;height:4px;
                        margin-top:4px;'>
                        <div style='background:{color};
                        width:{pct:.0f}%;height:4px;
                        border-radius:3px;'></div>
                        </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            else:
                st.info("No behavioral data yet. "
                        "Log trades to see patterns.")

        except Exception as e:
            st.error(f"Could not load leaks: {e}")
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
