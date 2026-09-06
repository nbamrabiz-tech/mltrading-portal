# ── User management & selector ────────────────
import streamlit as st
from sqlalchemy import text
from config import STRATEGIES


def init_user():
    """Initialize session state user."""
    if "user_id" not in st.session_state:
        st.session_state.user_id     = 1
        st.session_state.username    = "sunny"
        st.session_state.display_name = "Sunny"
        st.session_state.prev_user_id = 1


def render_user_selector(engine):
    """Render user selector in sidebar."""
    init_user()
    try:
        with engine.connect() as conn:
            all_users = conn.execute(text("""
                SELECT id, username,
                       display_name,
                       persona_type,
                       is_test_user
                FROM users
                WHERE is_active=TRUE
                ORDER BY is_test_user ASC, id ASC
            """)).fetchall()

        user_options = {
            f"{'🧪 ' if u[4] else '👤 '}"
            f"{u[2]} ({u[3]})": u
            for u in all_users}

        with st.sidebar:
            st.markdown("**👤 Active User**")
            selected = st.selectbox(
                "View as:",
                list(user_options.keys()),
                key="user_selector")
            selected_user = \
                user_options[selected]

            # Detect user change → rerun
            prev_uid = st.session_state.get(
                "prev_user_id", 1)
            new_uid  = selected_user[0]
            if prev_uid != new_uid:
                st.session_state.prev_user_id\
                    = new_uid
                st.rerun()

            st.session_state.user_id = \
                selected_user[0]
            st.session_state.username = \
                selected_user[1]
            st.session_state.display_name = \
                selected_user[2]

            username = selected_user[1]
            strategy = STRATEGIES.get(
                username, "")

            if selected_user[4]:
                st.caption(
                    f"🧪 {selected_user[3]}")
            else:
                st.caption("👤 Real user")

            if strategy:
                st.markdown(
                    f"<div style='"
                    f"background:#F0F4FF;"
                    f"border-radius:6px;"
                    f"padding:6px 10px;"
                    f"font-size:12px;"
                    f"font-weight:600;"
                    f"color:#0066CC;'>"
                    f"{strategy}</div>",
                    unsafe_allow_html=True)

    except Exception as e:
        st.session_state.user_id = 1
        st.sidebar.error(
            f"User selector: {e}")


def current_uid():
    """Get current user_id from session."""
    return st.session_state.get("user_id", 1)


def current_user():
    """Get current username from session."""
    return st.session_state.get(
        "username", "sunny")


def current_display():
    """Get display name from session."""
    return st.session_state.get(
        "display_name", "Sunny")


