import streamlit as st
from dav_tool.ui.onboarding import run as run_onboarding
from dav_tool.ui.existing import run as run_existing

st.set_page_config(page_title="DAV TOOL", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = "existing"

st.markdown(
    """
    <style>
    div.toggle-container {
        display: flex;
        border: 2px solid #4CAF50;
        border-radius: 6px;
        overflow: hidden;
        width: 320px;
        margin-bottom: 10px;
    }
    div.toggle-container button {
        flex: 1;
        padding: 8px 0;
        font-weight: 600;
        border: none;
        cursor: pointer;
    }
    .active {
        background-color: #1E88E5;
        color: white;
    }
    .inactive {
        background-color: white;
        color: #1E88E5;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

col_spacer, col_toggle = st.columns([6, 3])

with col_toggle:
    c1, c2 = st.columns(2)

    if c1.button("Onboarding", key="btn_onboarding", use_container_width=True):
        st.session_state.page = "onboarding"

    if c2.button("Existing", key="btn_existing", use_container_width=True):
        st.session_state.page = "existing"

    active_page = st.session_state.page
    st.markdown(
        f"""
        <script>
        const buttons = window.parent.document.querySelectorAll('button');
        buttons.forEach(btn => {{
            if (btn.innerText === "Onboarding") {{
                btn.className = btn.innerText === "{active_page.capitalize()}" ? "active" : "inactive";
            }}
            if (btn.innerText === "Existing") {{
                btn.className = btn.innerText === "{active_page.capitalize()}" ? "active" : "inactive";
            }}
        }});
        </script>
        """,
        unsafe_allow_html=True,
    )

if st.session_state.page == "onboarding":
    run_onboarding()
else:
    run_existing()
