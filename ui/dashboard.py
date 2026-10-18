import streamlit as st

from services.application_service import list_applications


def show_dashboard() -> None:
    st.title("AI Job Application Agent")
    st.caption("Evidence-led resume tailoring, with you in control at every step.")
    records = list_applications()
    sent = sum(record.email_status.value == "Email sent" for record in records)
    left, middle, right = st.columns(3)
    left.metric("Applications", len(records))
    middle.metric("Emails accepted by Gmail", sent)
    right.metric("Awaiting approval", sum(record.email_status.value == "Awaiting approval" for record in records))
    st.info(
        "Start a new application to analyze a job posting, review proposed resume edits, "
        "generate a PDF, and optionally send an approved email."
    )
