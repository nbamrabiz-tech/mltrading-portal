# ══════════════════════════════════════════════
# MLTrading Intelligence Portal
# Main entry point — thin shell
# ══════════════════════════════════════════════

import streamlit as st
from datetime import datetime
import pytz

from mltrading.db import get_engine
from mltrading.config import EST
from mltrading.auth import render_user_selector
from mltrading.queries.trades import (
    get_last_trading_day,
    get_latest_report,
    get_trade_journal,
    get_todays_events,
    get_spy_levels,
    get_learning_log,
)
from mltrading.queries.behavioral import (
    get_behavioral_data,
    get_streaks,
    calculate_daily_score,
    check_reentry_timing,
    detect_all_behaviors,
)
from mltrading.queries.analytics import (
    get_expectancy,
    get_time_analysis,
    get_setup_analysis,
    get_account_breakdown,
    get_drawdown,
    get_weekly_report,
)
from mltrading.tabs import (
    intelligence,
    decision_support,
    risk_advisory,
    sentiment,
    profile,
    analytics,
    forward_test,
    settings,
)

st.set_page_config(
    page_title="MLTrading Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

engine = get_engine()


def main():
    now_est = datetime.now(EST)
    today   = get_last_trading_day()

    # User selector in sidebar
    render_user_selector(engine)

    from mltrading.auth import current_display
    display_name = current_display()

    # Header
    st.markdown(
        f"<div style='text-align:center;"
        f"padding:8px 0;'>"
        f"<h1 style='color:#0066CC;margin:0;"
        f"font-size:26px;'>"
        f"📊 MLTrading Intelligence</h1>"
        f"<p style='color:#888;margin:0;"
        f"font-size:12px;'>"
        f"{now_est.strftime('%A %B %d %Y — %H:%M EST')}"
        f" &nbsp;|&nbsp; Trading day: {today}"
        f" &nbsp;|&nbsp; 👤 {display_name}"
        f"</p></div>",
        unsafe_allow_html=True)
    st.divider()

    # Tabs
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

    with tabs[0]:
        intelligence.render(engine, today,
                            now_est)
    with tabs[1]:
        decision_support.render(engine, today)
    with tabs[2]:
        risk_advisory.render(engine, today)
    with tabs[3]:
        sentiment.render(engine, today)
    with tabs[4]:
        profile.render(engine, today, now_est)
    with tabs[5]:
        analytics.render(engine)
    with tabs[6]:
        forward_test.render(engine)
    with tabs[7]:
        settings.render(engine)


if __name__ == "__main__":
    main()

main()
