import shutil

import streamlit as st

from config.settings import settings


def show_settings() -> None:
    st.title("Settings and integration status")
    st.write("Configuration is loaded from the project `.env` file.")
    st.write(f"Groq API key: {'Configured' if settings.groq_api_key else 'Not configured'}")
    st.write(f"Groq model: `{settings.groq_model}`")
    st.write(f"Configured sender: `{settings.gmail_expected_sender}`")
    st.write(
        "Gmail OAuth client: "
        + ("Configured" if settings.gmail_credentials_file.is_file() else "Not configured")
    )
    st.write(
        "Saved Gmail authorization: "
        + ("Available" if settings.gmail_token_file.is_file() else "Not authorized")
    )
    st.write(f"LaTeX compiler: {shutil.which('pdflatex') or 'pdflatex not found on PATH'}")
    st.caption("Secrets and OAuth token contents are never shown here.")
