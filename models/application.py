from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field


class ApplicationStatus(StrEnum):
    DRAFT_CREATED = "Draft created"
    RESUME_GENERATED = "Resume generated"
    AWAITING_APPROVAL = "Awaiting approval"
    SENDING = "Sending"
    EMAIL_SENT = "Email sent"
    EMAIL_FAILED = "Email failed"


class JobDetails(BaseModel):
    job_title: str = Field(default="", max_length=200)
    company_name: str = Field(default="", max_length=200)
    job_description: str = Field(min_length=1, max_length=30000)
    hr_email: EmailStr


class EmailDraft(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10000)


class ApplicationRecord(BaseModel):
    application_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    company_name: str
    job_title: str
    recipient_email: EmailStr
    resume_filename: str
    pdf_filename: str = ""
    email_subject: str = ""
    email_status: ApplicationStatus = ApplicationStatus.DRAFT_CREATED
    gmail_message_id: str = ""
