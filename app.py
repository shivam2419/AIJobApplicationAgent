import streamlit as st

from config.settings import settings
from ui.dashboard import show_dashboard
from ui.history import show_history
from ui.new_application import show_new_application
from ui.settings import show_settings
from utils.logging_config import configure_logging

configure_logging()

st.set_page_config(
    page_title="AI Job Application Agent",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.title("AI Job Application Agent")
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "New Application", "Application History", "Settings"],
)
st.sidebar.caption("Your applications stay on this computer.")

if page == "Dashboard":
    show_dashboard()
elif page == "New Application":
    show_new_application()
elif page == "Application History":
    show_history()
else:
    show_settings()
