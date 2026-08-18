# ══════════════════════════════════════════════════════════════
# MLTrading System — Portal v1 (Streamlit)
# Layer 6 — Daily Intelligence Portal
# ══════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from datetime import datetime, date, timedelta
import pytz
import plotly.graph_objects as go

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title  = "MLTrading Intelligence",
    page_icon   = "📊",
    layout      = "wide",
    initial_sidebar_state = "collapsed"
)

# ── Constants ─────────────────────────────────────────────────
EST = pytz.timezone("America/New_York")

# ── Database connection ───────────────────────────────────────
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

# ── Helper functions ──────────────────────────────────────────
def get_last_trading_day():
    today   = datetime.now(EST).date()
    weekday = today.weekday()
    if weekday == 5:   return today - timedelta(days=1)
    elif weekday == 6: return today - timedelta(days=2)
    return today

def get_latest_report():
    """Pull latest intelligence report from Supabase."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT *
                FROM intelligence_reports
                WHERE market='US'
                ORDER BY report_date DESC, created_at DESC
                LIMIT 1
            """))
            row = result.fetchone()
            if row:
                return dict(zip(result.keys(), row))
    except Exception as e:
        return None
    return None

def get_learning_log(days_back=30):
    """Pull recent learning log entries."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT log_date, predicted_bias,
                       actual_bias, actual_return,
                       was_correct, matrix_score
                FROM learning_log
                WHERE market='US'
                AND log_date >= :start
                ORDER BY log_date DESC
                LIMIT 30
            """), {"start": str(date.today() -
                               timedelta(days=days_back))})
            rows = result.fetchall()
            if rows:
                return pd.DataFrame(rows,
                    columns=["date","predicted","actual",
                             "return","correct","score"])
    except:
        pass
    return pd.DataFrame()

def get_trade_log():
    """Pull trade log from Supabase."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT trade_date, ticker, direction,
                       entry_price, exit_price,
                       pnl, outcome, matrix_score,
                       bias, scenario, notes
                FROM trade_log
                WHERE market='US'
                ORDER BY trade_date DESC, created_at DESC
                LIMIT 50
            """))
            rows = result.fetchall()
            if rows:
                return pd.DataFrame(rows,
                    columns=["date","ticker","direction",
                             "entry","exit","pnl","outcome",
                             "score","bias","scenario","notes"])
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

def get_spy_price():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT CAST(open AS FLOAT),
                       CAST(close AS FLOAT),
                       CAST(high AS FLOAT),
                       CAST(low AS FLOAT),
                       DATE(timestamp) as dt
                FROM price_data
                WHERE market='US' AND ticker='SPY'
                AND timeframe='1d'
                ORDER BY timestamp DESC LIMIT 2
            """))
            rows = result.fetchall()
            return rows if rows else []
    except:
        return []

def get_todays_events():
    today = get_last_trading_day()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT event_type, actual_value,
                       previous_value, impact_score
                FROM economic_events
                WHERE market='US' AND event_date=:td
                ORDER BY impact_score ASC
            """), {"td": str(today)})
            rows = result.fetchall()
            return rows if rows else []
    except:
        return []

# ── Styling helpers ───────────────────────────────────────────
def bias_color(bias):
    if bias == "Bullish":  return "#00D4AA"
    if bias == "Bearish":  return "#FF4B4B"
    return "#FFD700"

def bias_emoji(bias):
    if bias == "Bullish":  return "🟢"
    if bias == "Bearish":  return "🔴"
    return "⚪"

def score_bar(score, width=200):
    """HTML progress bar for scores."""
    color = ("#00D4AA" if score >= 58
             else "#FF4B4B" if score <= 42
             else "#FFD700")
    pct = score
    return (f'<div style="background:#1A1D27;'
            f'border-radius:4px;width:{width}px;height:8px;">'
            f'<div style="background:{color};'
            f'width:{pct}%;height:8px;'
            f'border-radius:4px;"></div></div>')

# ── Main portal ───────────────────────────────────────────────
def main():
    now_est = datetime.now(EST)
    today   = get_last_trading_day()

    # Header
    st.markdown(
        f"""
        <div style='text-align:center;padding:10px 0 5px 0;'>
        <h1 style='color:#00D4AA;margin:0;font-size:28px;'>
        📊 MLTrading Intelligence
        </h1>
        <p style='color:#888;margin:0;font-size:13px;'>
        {now_est.strftime('%A, %B %d %Y — %H:%M EST')}
        </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    # ── Tab navigation ────────────────────────────────────────
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
        prices = get_spy_price()
        events = get_todays_events()

        if not report:
            st.warning(
                "No intelligence report found for today. "
                "Run the morning script in Kaggle first."
            )
            st.info(
                "**Quick start:**\n"
                "1. Open ML_Layer_3 notebook in Kaggle\n"
                "2. Run Cell 1 (master script)\n"
                "3. Run Cell 2 (daily runner)\n"
                "4. Refresh this page"
            )
        else:
            bias  = report.get("bias","Neutral")
            score = report.get("matrix_score",50)
            conf  = report.get("confidence","Low")
            tp    = report.get("trade_prob",45)
            rpt_date = report.get("report_date",today)

            # ── Top metrics row ───────────────────────────────
            col1,col2,col3,col4 = st.columns(4)

            with col1:
                color = bias_color(bias)
                st.markdown(
                    f"""
                    <div style='background:#1A1D27;padding:16px;
                    border-radius:8px;border-left:4px solid {color};'>
                    <p style='color:#888;margin:0;font-size:12px;'>
                    MARKET BIAS</p>
                    <p style='color:{color};margin:4px 0 0 0;
                    font-size:24px;font-weight:bold;'>
                    {bias_emoji(bias)} {bias}</p>
                    <p style='color:#888;margin:0;font-size:11px;'>
                    {conf} confidence</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with col2:
                st.markdown(
                    f"""
                    <div style='background:#1A1D27;padding:16px;
                    border-radius:8px;'>
                    <p style='color:#888;margin:0;font-size:12px;'>
                    MATRIX SCORE</p>
                    <p style='color:#FAFAFA;margin:4px 0 4px 0;
                    font-size:24px;font-weight:bold;'>
                    {score}/100</p>
                    {score_bar(score)}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with col3:
                tp_color = ("#00D4AA" if tp >= 65
                            else "#FF4B4B" if tp <= 40
                            else "#FFD700")
                st.markdown(
                    f"""
                    <div style='background:#1A1D27;padding:16px;
                    border-radius:8px;'>
                    <p style='color:#888;margin:0;font-size:12px;'>
                    TRADE PROBABILITY</p>
                    <p style='color:{tp_color};margin:4px 0 4px 0;
                    font-size:24px;font-weight:bold;'>{tp}%</p>
                    {score_bar(tp)}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with col4:
                vix_color = ("#00D4AA" if vix < 15
                             else "#FF4B4B" if vix >= 25
                             else "#FFD700")
                vix_label = ("Low fear" if vix < 15
                             else "High fear" if vix >= 25
                             else "Moderate")
                st.markdown(
                    f"""
                    <div style='background:#1A1D27;padding:16px;
                    border-radius:8px;'>
                    <p style='color:#888;margin:0;font-size:12px;'>
                    VIX</p>
                    <p style='color:{vix_color};margin:4px 0 0 0;
                    font-size:24px;font-weight:bold;'>{vix}</p>
                    <p style='color:#888;margin:0;font-size:11px;'>
                    {vix_label}</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            st.divider()

            # ── Narrative ─────────────────────────────────────
            col_l, col_r = st.columns([3,2])

            with col_l:
                st.subheader("📰 Today's Narrative")
                headline = report.get(
                    "narrative_headline",
                    "No narrative available")
                st.markdown(
                    f"""
                    <div style='background:#1A1D27;padding:16px;
                    border-radius:8px;border-left:4px solid #00D4AA;'>
                    <p style='color:#FAFAFA;margin:0;font-size:14px;
                    line-height:1.6;'>{headline}</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                narr_score = report.get("narrative_score",50)
                is_event   = report.get("is_event_day",False)
                volatility = report.get("volatility","Normal")

                m1,m2,m3 = st.columns(3)
                m1.metric("Narrative Score",
                          f"{narr_score}/100")
                m2.metric("Event Day",
                          "Yes ★★★" if is_event else "No")
                m3.metric("Volatility", volatility or "Normal")

            with col_r:
                st.subheader("🤖 ML Ensemble")
                ml_score = report.get("ml_ensemble_score",50)
                ml_lean  = report.get("ml_ensemble_lean",
                                      "Neutral")

                models = {
                    "XGBoost":    report.get("xgb_score",50),
                    "ARIMA":      report.get("arima_score",50),
                    "LSTM":       report.get("lstm_score",50),
                    "RandForest": report.get("rf_score",50),
                    "GradBoost":  report.get("gb_score",50)
                }

                for model, mscore in models.items():
                    col_name, col_bar = st.columns([2,3])
                    col_name.markdown(
                        f"<p style='color:#888;font-size:12px;"
                        f"margin:2px 0;'>{model}</p>",
                        unsafe_allow_html=True
                    )
                    col_bar.markdown(
                        score_bar(mscore, width=150),
                        unsafe_allow_html=True
                    )
                    col_bar.markdown(
                        f"<p style='color:#888;font-size:11px;"
                        f"margin:0;'>{mscore}/100</p>",
                        unsafe_allow_html=True
                    )

                st.markdown(
                    f"**Ensemble: {ml_score}/100 — {ml_lean}**"
                )

            st.divider()

            # ── Candle info ───────────────────────────────────
            st.subheader("🕯️ First Candle")
            c1,c2,c3 = st.columns(3)

            spy_dir  = report.get("spy_candle_dir","Unknown")
            spy_conv = report.get("spy_candle_conv","Unknown")
            spy_sc   = report.get("spy_candle_score",50)
            qqq_dir  = report.get("qqq_candle_dir","Unknown")
            qqq_conv = report.get("qqq_candle_conv","Unknown")
            qqq_sc   = report.get("qqq_candle_score",50)
            reaction = report.get("reaction_type","Unknown")

            c1.markdown(
                f"""
                <div style='background:#1A1D27;padding:12px;
                border-radius:8px;'>
                <p style='color:#888;margin:0;font-size:11px;'>
                SPY CANDLE</p>
                <p style='color:{bias_color(spy_dir)};
                margin:4px 0 0 0;font-size:18px;
                font-weight:bold;'>{spy_dir}</p>
                <p style='color:#888;margin:0;font-size:11px;'>
                {spy_conv} | Score:{spy_sc}/100</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            c2.markdown(
                f"""
                <div style='background:#1A1D27;padding:12px;
                border-radius:8px;'>
                <p style='color:#888;margin:0;font-size:11px;'>
                QQQ CANDLE</p>
                <p style='color:{bias_color(qqq_dir)};
                margin:4px 0 0 0;font-size:18px;
                font-weight:bold;'>{qqq_dir}</p>
                <p style='color:#888;margin:0;font-size:11px;'>
                {qqq_conv} | Score:{qqq_sc}/100</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            c3.markdown(
                f"""
                <div style='background:#1A1D27;padding:12px;
                border-radius:8px;'>
                <p style='color:#888;margin:0;font-size:11px;'>
                REACTION TYPE</p>
                <p style='color:#FFD700;margin:4px 0 0 0;
                font-size:14px;font-weight:bold;'>
                {reaction}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.divider()

            # ── Key levels ────────────────────────────────────
            st.subheader("📍 Key Levels — SPY")
            kc1,kc2,kc3,kc4 = st.columns(4)
            kc1.metric("Resistance 1",
                       f"${report.get('spy_resistance_1',0):.2f}")
            kc2.metric("Resistance 2",
                       f"${report.get('spy_resistance_2',0):.2f}")
            kc3.metric("Support 1",
                       f"${report.get('spy_support_1',0):.2f}")
            kc4.metric("Support 2",
                       f"${report.get('spy_support_2',0):.2f}")

            # ── Economic events ───────────────────────────────
            if events:
                st.divider()
                st.subheader("📅 Today's Events")
                for ev in events:
                    imp_color = ("#FF4B4B" if ev[3]=="High"
                                 else "#FFD700"
                                 if ev[3]=="Medium"
                                 else "#888")
                    st.markdown(
                        f"""
                        <div style='background:#1A1D27;
                        padding:8px 12px;border-radius:6px;
                        border-left:3px solid {imp_color};
                        margin-bottom:4px;'>
                        <span style='color:{imp_color};
                        font-size:11px;font-weight:bold;'>
                        [{ev[3]}]</span>
                        <span style='color:#FAFAFA;
                        font-size:13px;margin-left:8px;'>
                        {ev[0]}</span>
                        <span style='color:#888;
                        font-size:12px;margin-left:12px;'>
                        Actual: {ev[1]}  Prev: {ev[2]}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    # ══════════════════════════════════════════════════════════
    # TAB 2 — DECISION SUPPORT
    # ══════════════════════════════════════════════════════════
    with tabs[1]:
        st.subheader("🎯 Decision Support")

        report = get_latest_report()
        if not report:
            st.warning("Run morning script first.")
        else:
            bias  = report.get("bias","Neutral")
            score = report.get("matrix_score",50)

            # Alignment
            al_label = report.get("alignment","Unknown")
            al_score = report.get("alignment_score",50)
            daily_tr = report.get("daily_trend","Unknown")
            hourly   = report.get("hourly_bias","Unknown")
            m15      = report.get("m15_bias","Unknown")

            st.markdown("### Timeframe Alignment")
            tc1,tc2,tc3,tc4 = st.columns(4)
            tc1.metric("Daily Trend",   daily_tr)
            tc2.metric("1-Hour Bias",   hourly)
            tc3.metric("15-Min Bias",   m15)
            tc4.metric("Alignment",
                       f"{al_score}/100")

            st.markdown(
                f"""
                <div style='background:#1A1D27;padding:12px;
                border-radius:8px;margin:8px 0;'>
                <p style='color:#888;margin:0;font-size:12px;'>
                ALIGNMENT SUMMARY</p>
                <p style='color:#FAFAFA;margin:4px 0 0 0;
                font-size:14px;'>{al_label}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.divider()
            st.markdown("### Key Levels")

            col_spy, col_qqq = st.columns(2)

            with col_spy:
                st.markdown("**SPY**")
                sk1,sk2 = st.columns(2)
                sk1.metric("R1",
                    f"${report.get('spy_resistance_1',0):.2f}")
                sk1.metric("R2",
                    f"${report.get('spy_resistance_2',0):.2f}")
                sk2.metric("S1",
                    f"${report.get('spy_support_1',0):.2f}")
                sk2.metric("S2",
                    f"${report.get('spy_support_2',0):.2f}")

            with col_qqq:
                st.markdown("**QQQ**")
                qk1,qk2 = st.columns(2)
                qk1.metric("R1",
                    f"${report.get('qqq_resistance_1',0):.2f}")
                qk1.metric("R2",
                    f"${report.get('qqq_resistance_2',0):.2f}")
                qk2.metric("S1",
                    f"${report.get('qqq_support_1',0):.2f}")
                qk2.metric("S2",
                    f"${report.get('qqq_support_2',0):.2f}")

            div_sig = report.get("divergence_signal","")
            div_gui = report.get("divergence_guidance","")
            if div_sig:
                st.divider()
                st.markdown("### Divergence Signal")
                st.warning(f"**{div_sig}**\n\n{div_gui}")

    # ══════════════════════════════════════════════════════════
    # TAB 3 — RISK ADVISORY
    # ══════════════════════════════════════════════════════════
    with tabs[2]:
        st.subheader("⚖️ Risk Advisory")

        col_budget, col_calc = st.columns(2)

        with col_budget:
            st.markdown("### Today's Risk Budget")

            account = st.number_input(
                "Account size ($)",
                min_value=1000,
                max_value=1000000,
                value=10000,
                step=1000,
                key="account_size"
            )

            report = get_latest_report()
            if report:
                tp = report.get("trade_prob",45)
                is_event = report.get("is_event_day",False)

                if tp >= 70:   base = 2.0
                elif tp >= 55: base = 1.5
                elif tp >= 45: base = 1.0
                elif tp >= 35: base = 0.5
                else:          base = 0.0

                if is_event: base *= 0.75

                risk_pct     = round(min(base, 3.0), 2)
                max_risk     = round(account * risk_pct/100, 2)
                daily_limit  = round(max_risk * 3, 2)
                max_trades   = (0 if risk_pct==0
                                else 1 if tp<45
                                else 2 if tp<60
                                else 3)

                risk_color = ("#00D4AA" if risk_pct >= 1.5
                              else "#FFD700" if risk_pct >= 0.75
                              else "#FF4B4B")

                st.markdown(
                    f"""
                    <div style='background:#1A1D27;padding:16px;
                    border-radius:8px;'>
                    <p style='color:#888;font-size:12px;margin:0;'>
                    MAX RISK PER TRADE</p>
                    <p style='color:{risk_color};font-size:28px;
                    font-weight:bold;margin:4px 0;'>
                    ${max_risk:,.2f}</p>
                    <p style='color:#888;font-size:12px;margin:0;'>
                    {risk_pct}% of account</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                r1,r2 = st.columns(2)
                r1.metric("Daily Loss Limit",
                          f"${daily_limit:,.2f}")
                r2.metric("Max Trades Today",
                          str(max_trades))

                if risk_pct == 0:
                    st.error(
                        "⛔ NO TRADE — No clear edge today. "
                        "Preserve capital."
                    )
                elif risk_pct <= 0.75:
                    st.warning(
                        "⚠️ MINIMAL SIZE — Low conviction. "
                        "Trade minimum only."
                    )
                else:
                    st.success(
                        f"✅ CONDITIONS SUPPORT A TRADE — "
                        f"Max ${max_risk:.0f} at risk per trade."
                    )

        with col_calc:
            st.markdown("### Trade Calculator")

            entry = st.number_input(
                "Entry price", value=770.00,
                step=0.25, format="%.2f")
            stop  = st.number_input(
                "Stop loss",   value=768.00,
                step=0.25, format="%.2f")

            if entry > 0 and stop > 0 and entry != stop:
                risk_per_share = abs(entry - stop)
                direction = "Long" if entry > stop else "Short"

                if risk_per_share > 0:
                    max_r = round(
                        account *
                        min(base if report else 1.0, 3.0)
                        / 100, 2)
                    shares = max(1,
                                 int(max_r / risk_per_share))

                    t1 = round(entry + risk_per_share
                               if direction=="Long"
                               else entry - risk_per_share, 2)
                    t2 = round(entry + risk_per_share*2
                               if direction=="Long"
                               else entry - risk_per_share*2, 2)
                    t3 = round(entry + risk_per_share*3
                               if direction=="Long"
                               else entry - risk_per_share*3, 2)

                    st.markdown(
                        f"""
                        <div style='background:#1A1D27;
                        padding:16px;border-radius:8px;'>
                        <p style='color:#888;font-size:12px;
                        margin:0;'>DIRECTION</p>
                        <p style='color:#FAFAFA;font-size:18px;
                        font-weight:bold;margin:4px 0 8px 0;'>
                        {direction}</p>
                        <p style='color:#888;font-size:12px;
                        margin:0;'>RISK PER SHARE</p>
                        <p style='color:#FAFAFA;font-size:16px;
                        margin:4px 0 8px 0;'>
                        ${risk_per_share:.2f}</p>
                        <p style='color:#888;font-size:12px;
                        margin:0;'>RECOMMENDED SIZE</p>
                        <p style='color:#00D4AA;font-size:22px;
                        font-weight:bold;margin:4px 0 8px 0;'>
                        {shares} shares</p>
                        <hr style='border-color:#333;'>
                        <p style='color:#888;font-size:12px;
                        margin:4px 0;'>
                        1:1 → ${t1:.2f} &nbsp;&nbsp;
                        (+${risk_per_share*shares:.0f})</p>
                        <p style='color:#FFD700;font-size:12px;
                        margin:4px 0;'>
                        1:2 → ${t2:.2f} &nbsp;&nbsp;
                        (+${risk_per_share*shares*2:.0f})</p>
                        <p style='color:#00D4AA;font-size:12px;
                        margin:4px 0;'>
                        1:3 → ${t3:.2f} &nbsp;&nbsp;
                        (+${risk_per_share*shares*3:.0f})</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    # ══════════════════════════════════════════════════════════
    # TAB 4 — SENTIMENT
    # ══════════════════════════════════════════════════════════
    with tabs[3]:
        st.subheader("😊 Market Sentiment")

        vix = get_vix()
        report = get_latest_report()

        sc1,sc2,sc3 = st.columns(3)

        vix_label = ("Low fear" if vix<15
                     else "High fear" if vix>=25
                     else "Moderate")
        sc1.metric("VIX", f"{vix:.2f}", vix_label)

        if report:
            sent_score = report.get("sentiment_score",50)
            sent_label = report.get("sentiment_label","Neutral")
            sc2.metric("Sentiment Score",
                       f"{sent_score}/100", sent_label)
            sc3.metric("VIX Trend",
                       report.get("vix_trend","Unknown"))

        events = get_todays_events()
        if events:
            st.divider()
            st.markdown("### Today's Economic Events")
            for ev in events:
                imp_color = ("#FF4B4B" if ev[3]=="High"
                             else "#FFD700")
                actual   = ev[1]
                previous = ev[2]
                if actual and previous:
                    diff = float(actual) - float(previous)
                    arrow = "↑" if diff > 0 else "↓"
                else:
                    arrow = "—"
                st.markdown(
                    f"""
                    <div style='background:#1A1D27;
                    padding:10px 14px;border-radius:6px;
                    border-left:3px solid {imp_color};
                    margin-bottom:6px;'>
                    <b style='color:{imp_color};
                    font-size:11px;'>[{ev[3]}]</b>
                    <span style='color:#FAFAFA;
                    font-size:13px;margin-left:8px;'>
                    {ev[0]}</span>
                    <span style='color:#888;
                    font-size:12px;margin-left:12px;'>
                    A:{actual} P:{previous} {arrow}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.info("No economic events found for today.")

    # ══════════════════════════════════════════════════════════
    # TAB 5 — MY PROFILE
    # ══════════════════════════════════════════════════════════
    with tabs[4]:
        st.subheader("👤 My Profile & Journal")

        # Log a trade
        st.markdown("### Log a Paper Trade")
        with st.form("trade_form"):
            fc1,fc2,fc3 = st.columns(3)
            t_ticker    = fc1.selectbox("Ticker",
                                        ["SPY","QQQ"])
            t_direction = fc2.selectbox("Direction",
                                        ["Long","Short"])
            t_scenario  = fc3.selectbox("Scenario",
                                        ["A","B","C","None"])

            fc4,fc5,fc6 = st.columns(3)
            t_entry  = fc4.number_input("Entry",
                value=770.0, step=0.25, format="%.2f")
            t_exit   = fc5.number_input("Exit",
                value=768.0, step=0.25, format="%.2f")
            t_risk   = fc6.number_input("Risk ($)",
                value=38.0, step=1.0)

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
                ms = report.get("matrix_score",50) if report else 50
                bias = report.get("bias","Neutral") if report else "Neutral"

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
                                :entry,:exit,:risk,:pnl,
                                :pnl_pct,:ms,:bias,
                                :scenario,:outcome,:notes)
                        """), {
                            "td":       str(date.today()),
                            "ticker":   t_ticker,
                            "dir":      t_direction,
                            "entry":    t_entry,
                            "exit":     t_exit,
                            "risk":     t_risk,
                            "pnl":      round(pnl,2),
                            "pnl_pct":  round(pnl/t_entry*100,4),
                            "ms":       ms,
                            "bias":     bias,
                            "scenario": t_scenario,
                            "outcome":  outcome,
                            "notes":    t_notes
                        })
                        conn.commit()
                    color = ("#00D4AA" if pnl>0
                             else "#FF4B4B")
                    st.markdown(
                        f"<p style='color:{color};'>"
                        f"Trade logged: "
                        f"{'WIN' if pnl>0 else 'LOSS'} "
                        f"${pnl:+.2f}</p>",
                        unsafe_allow_html=True
                    )
                except Exception as e:
                    st.error(f"Save failed: {e}")

        st.divider()

        # Performance summary
        st.markdown("### Performance Summary")
        trades_df = get_trade_log()

        if trades_df.empty:
            st.info("No trades logged yet. "
                    "Log your first paper trade above.")
        else:
            total  = len(trades_df)
            wins   = len(trades_df[trades_df["outcome"]=="Win"])
            losses = len(trades_df[trades_df["outcome"]=="Loss"])
            wr     = round(wins/total*100,1)
            total_pnl = round(
                trades_df["pnl"].astype(float).sum(),2)
            avg_win   = round(
                trades_df[trades_df["outcome"]=="Win"
                          ]["pnl"].astype(float).mean(),2
            ) if wins>0 else 0
            avg_loss  = round(
                trades_df[trades_df["outcome"]=="Loss"
                          ]["pnl"].astype(float).mean(),2
            ) if losses>0 else 0

            pm1,pm2,pm3,pm4 = st.columns(4)
            pm1.metric("Total Trades", total)
            pm2.metric("Win Rate", f"{wr}%")
            pm3.metric("Total P&L", f"${total_pnl:+.2f}")
            pm4.metric("Avg Win", f"${avg_win:+.2f}")

            st.divider()
            st.markdown("### Recent Trades")
            st.dataframe(
                trades_df[[
                    "date","ticker","direction",
                    "entry","exit","pnl","outcome"
                ]].head(20),
                use_container_width=True
            )

        st.divider()

        # Learning log
        st.markdown("### Forward Test Record")
        log_df = get_learning_log()

        if log_df.empty:
            st.info("No forward test data yet.")
        else:
            total_days = len(log_df)
            correct    = log_df["correct"].sum()
            wr_days    = round(correct/total_days*100,1)

            fl1,fl2,fl3 = st.columns(3)
            fl1.metric("Days Tested",  total_days)
            fl2.metric("Correct",      int(correct))
            fl3.metric("Accuracy",     f"{wr_days}%")

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
        st.subheader("⚙️ Settings")

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
                    "price_data":           "Price rows",
                    "vix_data":             "VIX rows",
                    "economic_events":      "Economic events",
                    "news_headlines":       "News headlines",
                    "intelligence_reports": "Intelligence reports",
                    "learning_log":         "Learning log entries",
                    "trade_log":            "Trade log entries"
                }
                for table, label in tables.items():
                    try:
                        r = conn.execute(
                            text(f"SELECT COUNT(*) FROM {table}"))
                        count = r.fetchone()[0]
                        st.markdown(
                            f"**{label}:** {count:,}")
                    except:
                        st.markdown(
                            f"**{label}:** Table not found")
        except Exception as e:
            st.error(f"Could not load stats: {e}")

        st.divider()
        st.markdown("### About")
        st.markdown("""
        **MLTrading Intelligence System**
        - Layer 1: Data Pipeline ✓
        - Layer 2: ML Matrix Engine ✓
        - Layer 3: Decision Support ✓
        - Layer 4: Risk Advisory ✓
        - Layer 5: Trade Execution ✓
        - Layer 6: Portal (this) ✓
        - Layer 7: Behavioral Intelligence ← coming soon
        """)


if __name__ == "__main__":
    main()
