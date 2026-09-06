# ── Database connection ───────────────────────
import streamlit as st
from sqlalchemy import create_engine
from urllib.parse import quote_plus


@st.cache_resource
def get_engine():
    pw = quote_plus(
        st.secrets["SUPABASE_PASSWORD"])
    return create_engine(
        f"postgresql://postgres.hjcmfkllwarrqougwdiy"
        f":{pw}"
        f"@aws-0-ca-central-1.pooler.supabase.com"
        f":6543/postgres",
        pool_pre_ping=True
    )


