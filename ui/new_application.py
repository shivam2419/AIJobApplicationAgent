from __future__ import annotations

import re
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from config.settings import settings
from models.application import (
    ApplicationRecord,
    ApplicationStatus,
    EmailDraft,
    JobDetails,
)
from models.job_analysis import JobAnalysis
from services.application_service import (
    claim_email_send,
    create_application,
    update_status,
)
from services.email_generator import generate_email
from services.gmail_service import GmailServiceError, send_email
from services.job_analyzer import analyze_job
from services.latex_compiler import LatexCompilationError, compile_latex
from services.llm_service import LLMConfigurationError
from services.pdf_reader import compare_resume_sources, extract_pdf_text
from services.pdf_validator import validate_generated_pdf
from services.resume_analyzer import tailor_resume_latex
from utils.file_validation import (
    FileValidationError,
    safe_filename,
    validate_latex,
)
from utils.security import managed_output_path


def _workflow() -> dict | None:
    return st.session_state.get("application_workflow")


def _record(workflow: dict) -> ApplicationRecord:
    return ApplicationRecord.model_validate(workflow["record"])


def _save_record(workflow: dict, record: ApplicationRecord) -> None:
    workflow["record"] = record.model_dump(mode="json")


def show_new_application() -> None:
    st.title("New application")
    st.caption("Your source files remain unchanged; generated files are stored per application.")
    workflow = _workflow()
    if workflow is None:
        _collect_application()
        return
    _show_workflow(workflow)


def _collect_application() -> None:
    st.write("Provide the job description, resume PDF, matching LaTeX source, and HR email.")
    with st.form("new_application_form"):
        job_description = st.text_area("Job description", height=180)
        pdf_file = st.file_uploader("Resume PDF", type=["pdf"])
        tex_file = st.file_uploader("Matching LaTeX source", type=["tex"])
        hr_email = st.text_input("HR email address")
        submitted = st.form_submit_button("Analyze job and resume", type="primary")
    if not submitted:
        return
    if not pdf_file or not tex_file:
        st.error("Upload both the reference resume PDF and its LaTeX source.")
        return
    try:
        details = JobDetails(
            job_description=job_description.strip(),
            hr_email=hr_email.strip(),
        )
        pdf_bytes = pdf_file.getvalue()
        resume_text = extract_pdf_text(pdf_bytes, pdf_file.name)
        latex_source = validate_latex(tex_file.getvalue(), tex_file.name)
        similarity = compare_resume_sources(resume_text, latex_source)
        with st.spinner("Analyzing the job and tailoring your resume in its existing format..."):
            analysis = analyze_job(details)
            details = details.model_copy(
                update={
                    "job_title": analysis.job_title or "the role",
                    "company_name": analysis.company_name or "Company not specified",
                }
            )
            record = create_application(
                details, f"{safe_filename(pdf_file.name)}.pdf"
            )
            tailored_latex = tailor_resume_latex(
                resume_text, latex_source, analysis, details
            )
        st.session_state.application_workflow = {
            "record": record.model_dump(mode="json"),
            "details": details.model_dump(mode="json"),
            "pdf_text": resume_text,
            "latex_source": latex_source,
            "latex_filename": safe_filename(tex_file.name),
            "analysis": analysis.model_dump(mode="json"),
            "tailored_latex": tailored_latex,
            "similarity": similarity,
            "email_draft": None,
            "send_in_progress": False,
        }
        st.rerun()
    except (FileValidationError, ValidationError, ValueError) as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(_safe_error(exc))


def _show_workflow(workflow: dict) -> None:
    if st.button("Clear workflow and start another application", key="clear_workflow"):
        st.session_state.pop("application_workflow", None)
        st.rerun()
    record = _record(workflow)
    details = JobDetails.model_validate(workflow["details"])
    st.subheader(f"{details.job_title} at {details.company_name}")
    similarity = workflow["similarity"]
    if similarity < 0.12:
        st.warning(
            "The PDF and LaTeX source look substantially different. Confirm they belong "
            "together before approving changes."
        )
    st.progress(min(similarity, 1.0), text=f"PDF/source text overlap: {similarity:.0%}")
    st.markdown("### Job analysis")
    analysis = workflow["analysis"]
    for key, label in (
        ("required_technical_skills", "Required skills"),
        ("preferred_skills", "Preferred skills"),
        ("required_experience", "Required experience"),
        ("key_responsibilities", "Key responsibilities"),
        ("important_keywords", "Important keywords"),
        ("tools_and_technologies", "Tools and technologies"),
        ("relevant_projects_and_achievements", "Relevant evidence to emphasize"),
        ("unsupported_skills_to_avoid_claiming", "Skills not to claim without evidence"),
        ("tailoring_recommendations", "Tailoring recommendations"),
    ):
        with st.expander(label, expanded=key in {"required_technical_skills", "tailoring_recommendations"}):
            values = analysis.get(key, [])
            st.write("\n".join(f"- {value}" for value in values) if values else "None identified.")
    st.warning(
        "AI tailored the LaTeX body while preserving the original preamble and document "
        "boundary. Carefully inspect every resume claim in the generated PDF before sending."
    )
    with st.expander("Review AI-generated LaTeX source"):
        st.code(workflow["tailored_latex"], language="latex")
        st.download_button(
            "Download tailored LaTeX source",
            data=workflow["tailored_latex"].encode("utf-8"),
            file_name="resume_tailored.tex",
            mime="application/x-tex",
            key=f"download_latex_{record.application_id}",
        )
    reviewed = st.checkbox(
        "I reviewed the generated resume and its factual claims.",
        key=f"reviewed_resume_{record.application_id}",
    )
    if st.button(
        "Compile tailored resume PDF",
        type="primary",
        disabled=not reviewed,
        key="generate_resume",
    ):
        _generate_resume(workflow, details)
    if workflow.get("pdf_path"):
        _show_generated_resume(workflow, details)


def _generate_resume(
    workflow: dict,
    details: JobDetails,
) -> None:
    record = _record(workflow)
    try:
        tex_path = managed_output_path(
            settings.output_dir, record.application_id, "resume_tailored.tex"
        )
        tex_source = workflow["tailored_latex"]
        tex_path.write_text(tex_source, encoding="utf-8")
        with st.spinner("Compiling and validating the tailored PDF..."):
            pdf_path = compile_latex(tex_path)
            emails = re.findall(
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", workflow["pdf_text"]
            )
            validate_generated_pdf(pdf_path, emails[:5])
        record = update_status(
            record,
            ApplicationStatus.RESUME_GENERATED,
            pdf_filename=pdf_path.name,
        )
        workflow["pdf_path"] = str(pdf_path)
        workflow["tex_path"] = str(tex_path)
        _save_record(workflow, record)
        st.rerun()
    except (LatexCompilationError, OSError, ValueError) as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(_safe_error(exc))


def _show_generated_resume(workflow: dict, details: JobDetails) -> None:
    pdf_path = Path(workflow["pdf_path"])
    tex_path = Path(workflow["tex_path"])
    if not pdf_path.is_file() or not tex_path.is_file():
        st.error("Generated resume files are missing. Generate the resume again.")
        return
    st.markdown("### Resume preview")
    st.success("The generated PDF passed readability and content checks.")
    left, right = st.columns(2)
    left.download_button(
        "Download tailored PDF",
        data=pdf_path.read_bytes(),
        file_name=pdf_path.name,
        mime="application/pdf",
    )
    right.download_button(
        "Download tailored LaTeX",
        data=tex_path.read_bytes(),
        file_name=tex_path.name,
        mime="application/x-tex",
    )
    st.markdown("### HR email")
    if st.button("Generate email draft", key="generate_email"):
        try:
            with st.spinner("Drafting a concise email from supported resume evidence..."):
                draft = generate_email(
                    details,
                    JobAnalysis.model_validate(workflow["analysis"]),
                    workflow["pdf_text"],
                    _applicant_name(workflow["pdf_text"]),
                )
            workflow["email_draft"] = draft.model_dump(mode="json")
            record = update_status(
                _record(workflow),
                ApplicationStatus.AWAITING_APPROVAL,
                email_subject=draft.subject,
            )
            _save_record(workflow, record)
            st.rerun()
        except Exception as exc:
            st.error(_safe_error(exc))
    if workflow.get("email_draft"):
        _show_email_review(workflow, pdf_path)


def _show_email_review(workflow: dict, pdf_path: Path) -> None:
    draft = EmailDraft.model_validate(workflow["email_draft"])
    details = JobDetails.model_validate(workflow["details"])
    record = _record(workflow)
    st.markdown("### Final email review")
    st.write(f"**From:** {settings.gmail_expected_sender}")
    st.write(f"**To:** {details.hr_email}")
    st.write(f"**Subject:** {draft.subject}")
    st.text(draft.body)
    st.write(f"**Attachment:** `{pdf_path.name}`")
    st.download_button(
        "Download attached resume PDF",
        data=pdf_path.read_bytes(),
        file_name=pdf_path.name,
        mime="application/pdf",
    )
    st.caption("Gmail API acceptance does not guarantee delivery or that the recipient has read it.")
    if record.email_status == ApplicationStatus.EMAIL_SENT:
        st.success(f"Email accepted by Gmail. Message ID: `{record.gmail_message_id}`")
        return
    if st.button(
        "Send Email",
        type="primary",
        disabled=workflow.get("send_in_progress", False),
        key="send_email",
    ):
        _send_reviewed_email(
            workflow,
            str(details.hr_email),
            draft.subject,
            draft.body,
            pdf_path,
        )


def _send_reviewed_email(
    workflow: dict,
    recipient: str,
    subject: str,
    body: str,
    pdf_path: Path,
) -> None:
    record = _record(workflow)
    if record.email_status == ApplicationStatus.EMAIL_SENT:
        st.success(f"This application was already sent (message ID {record.gmail_message_id}).")
        return
    if not claim_email_send(record):
        st.error("A send attempt is already in progress or this message has already been sent.")
        return
    workflow["send_in_progress"] = True
    try:
        message_id = send_email(recipient, subject, body, pdf_path)
        updated = update_status(
            record,
            ApplicationStatus.EMAIL_SENT,
            email_subject=subject,
            gmail_message_id=message_id,
        )
        _save_record(workflow, updated)
        st.success(
            f"Gmail accepted the message. Message ID: `{message_id}`. "
            "Acceptance does not guarantee recipient delivery or reading."
        )
    except GmailServiceError as exc:
        failed = update_status(record, ApplicationStatus.EMAIL_FAILED, email_subject=subject)
        _save_record(workflow, failed)
        st.error(str(exc))
    except Exception as exc:
        failed = update_status(record, ApplicationStatus.EMAIL_FAILED, email_subject=subject)
        _save_record(workflow, failed)
        st.error(_safe_error(exc))
    finally:
        workflow["send_in_progress"] = False


def _applicant_name(resume_text: str) -> str:
    first_line = next((line.strip() for line in resume_text.splitlines() if line.strip()), "")
    return first_line[:100] or "Applicant"


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, (LLMConfigurationError, ValueError)) and not isinstance(
        exc, ValidationError
    ):
        return str(exc)
    return f"Operation failed ({type(exc).__name__}). Check your configuration and try again."
