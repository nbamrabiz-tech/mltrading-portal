# ── Settings Tab ─────────────────
import streamlit as st
from db import get_engine
from datetime import date, timedelta, datetime
from sqlalchemy import text
import pytz
EST = pytz.timezone("America/New_York")

from queries.trades import get_latest_report


def render(engine, **kwargs):
    # TAB 8 — SETTINGS
    # ══════════════════════════════════════════════
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
    st.divider()
    st.markdown("### 🏦 Account Management")

    # Show existing accounts
    try:
        uid = st.session_state.get("user_id", 1)
        with engine.connect() as conn:
            accounts = conn.execute(text("""
                SELECT account_name, account_type,
                       starting_balance, risk_pct,
                       max_loss_multiplier,
                       is_active
                FROM account_settings
                WHERE market='US'
                AND user_id=:uid
                ORDER BY is_active DESC,
                         account_name ASC
            """), {"uid": uid}).fetchall()

        if accounts:
            for a in accounts:
                status = "✅ Active"                     if a[5] else "❌ Archived"
                col1, col2 = st.columns([3,1])
                col1.markdown(
                    f"**{a[0]}** ({a[1]}) — "
                    f"${float(a[2]):,.0f} — "
                    f"{float(a[3])}% risk — "
                    f"{status}")
                if a[5]:
                    if col2.button(
                            "Archive",
                            key=f"arch_{a[0]}"):
                        with engine.connect()                                 as conn:
                            conn.execute(text("""
                                UPDATE
                                account_settings
                                SET is_active=FALSE
                                WHERE market='US'
                                AND user_id=:uid
                                AND account_name=:an
                            """), {
                                "uid": uid,
                                "an": a[0]
                            })
                            conn.commit()
                        st.rerun()
                else:
                    if col2.button(
                            "Restore",
                            key=f"rest_{a[0]}"):
                        with engine.connect()                                 as conn:
                            conn.execute(text("""
                                UPDATE
                                account_settings
                                SET is_active=TRUE
                                WHERE market='US'
                                AND user_id=:uid
                                AND account_name=:an
                            """), {
                                "uid": uid,
                                "an": a[0]
                            })
                            conn.commit()
                        st.rerun()

    except Exception as e:
        st.error(f"Account error: {e}")

    # Add new account
    st.markdown("#### ➕ Add Account")
    with st.form("add_account_form"):
        ac1, ac2 = st.columns(2)
        new_name = ac1.text_input(
            "Account name",
            placeholder="e.g. Apex")
        new_type = ac2.selectbox(
            "Type",
            ["Live","Funded","Paper",
             "Combine","Practice"])
        ac3, ac4, ac5 = st.columns(3)
        new_bal  = ac3.number_input(
            "Starting balance",
            min_value=100,
            value=10000,
            key="new_bal")
        new_risk = ac4.number_input(
            "Risk %",
            min_value=0.1,
            max_value=10.0,
            value=1.0,
            step=0.1,
            key="new_risk")
        new_mult = ac5.number_input(
            "Max loss multiplier",
            min_value=1,
            max_value=10,
            value=2,
            key="new_mult")

        if st.form_submit_button(
                "Add Account",
                use_container_width=True):
            if new_name:
                try:
                    uid = st.session_state.get(
                        "user_id", 1)
                    with engine.connect() as conn:
                        conn.execute(text("""
                            INSERT INTO
                            account_settings(
                                user_id, market,
                                account_name,
                                account_type,
                                starting_balance,
                                current_balance,
                                risk_pct,
                                max_loss_multiplier,
                                is_active)
                            VALUES(:uid,'US',
                                :an,:at,:bal,
                                :bal,:risk,
                                :mult,TRUE)
                        """), {
                            "uid":  uid,
                            "an":   new_name,
                            "at":   new_type,
                            "bal":  new_bal,
                            "risk": new_risk,
                            "mult": new_mult
                        })
                        conn.commit()
                    st.success(
                        f"✓ {new_name} added")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning(
                    "Enter an account name.")

