# ── Forward Test Tab ─────────────
import streamlit as st
from db import get_engine
from datetime import date, timedelta, datetime
from sqlalchemy import text
import pytz
EST = pytz.timezone("America/New_York")


def render(engine, **kwargs):
    # TAB 7 — FORWARD TEST
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

