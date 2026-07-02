import streamlit as st
from dav_tool.ui.onboarding import run as run_onboarding
from dav_tool.ui.existing import run as run_existing

st.set_page_config(page_title="DAV TOOL", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = "existing"

st.markdown(
    """
    <style>
    div.row-widget.stButton button {
        font-weight: 600;
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

if st.session_state.page == "onboarding":
    run_onboarding()
else:
    run_existing()
