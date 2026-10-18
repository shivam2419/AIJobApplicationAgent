from pathlib import Path

import streamlit as st

from config.settings import settings
from services.application_service import list_applications
from utils.security import managed_output_path


def show_history() -> None:
    st.title("Application history")
    records = list_applications()
    if not records:
        st.info("No applications yet.")
        return
    for record in records:
        with st.expander(f"{record.company_name} — {record.job_title} · {record.email_status.value}"):
            st.write(f"Created: {record.created_at.astimezone().strftime('%Y-%m-%d %H:%M')}")
            st.write(f"Recipient: {record.recipient_email}")
            st.write(f"Resume source: {record.resume_filename}")
            if record.gmail_message_id:
                st.write(f"Gmail message ID: `{record.gmail_message_id}`")
            if record.pdf_filename:
                try:
                    pdf_path = managed_output_path(
                        settings.output_dir, record.application_id, record.pdf_filename
                    )
                    if pdf_path.is_file():
                        st.download_button(
                            "Download tailored PDF",
                            data=pdf_path.read_bytes(),
                            file_name=pdf_path.name,
                            mime="application/pdf",
                            key=f"history_{record.application_id}",
                        )
                except (OSError, ValueError) as exc:
                    st.warning(f"Saved PDF is unavailable: {exc}")
