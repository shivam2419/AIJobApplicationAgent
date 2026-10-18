from __future__ import annotations

import sqlite3
from datetime import datetime
from uuid import uuid4

from config.settings import settings
from models.application import ApplicationRecord, ApplicationStatus, JobDetails

def create_application(details: JobDetails, resume_filename: str) -> ApplicationRecord:
    record = ApplicationRecord(
        application_id=uuid4().hex,
        company_name=details.company_name,
        job_title=details.job_title,
        recipient_email=details.hr_email,
        resume_filename=resume_filename,
    )
    save_application(record)
    return record


def _connect() -> sqlite3.Connection:
    settings.ensure_directories()
    connection = sqlite3.connect(settings.database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            application_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            company_name TEXT NOT NULL,
            job_title TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            resume_filename TEXT NOT NULL,
            pdf_filename TEXT NOT NULL DEFAULT '',
            email_subject TEXT NOT NULL DEFAULT '',
            email_status TEXT NOT NULL,
            gmail_message_id TEXT NOT NULL DEFAULT ''
        )
        """
    )
    return connection


def save_application(record: ApplicationRecord) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO applications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(application_id) DO UPDATE SET
                pdf_filename=excluded.pdf_filename,
                email_subject=excluded.email_subject,
                email_status=excluded.email_status,
                gmail_message_id=excluded.gmail_message_id
            """,
            (
                record.application_id,
                record.created_at.isoformat(),
                record.company_name,
                record.job_title,
                str(record.recipient_email),
                record.resume_filename,
                record.pdf_filename,
                record.email_subject,
                record.email_status.value,
                record.gmail_message_id,
            ),
        )


def update_status(
    record: ApplicationRecord,
    status: ApplicationStatus,
    pdf_filename: str | None = None,
    email_subject: str | None = None,
    gmail_message_id: str | None = None,
) -> ApplicationRecord:
    updated = record.model_copy(
        update={
            "email_status": status,
            "pdf_filename": pdf_filename if pdf_filename is not None else record.pdf_filename,
            "email_subject": email_subject if email_subject is not None else record.email_subject,
            "gmail_message_id": (
                gmail_message_id if gmail_message_id is not None else record.gmail_message_id
            ),
        }
    )
    save_application(updated)
    return updated


def claim_email_send(record: ApplicationRecord) -> bool:
    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE applications SET email_status=?
            WHERE application_id=? AND email_status IN (?, ?)
            """,
            (
                ApplicationStatus.SENDING.value,
                record.application_id,
                ApplicationStatus.AWAITING_APPROVAL.value,
                ApplicationStatus.EMAIL_FAILED.value,
            ),
        )
    return cursor.rowcount == 1


def list_applications() -> list[ApplicationRecord]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM applications ORDER BY created_at DESC"
        ).fetchall()
    records = []
    for row in rows:
        records.append(
            ApplicationRecord(
                application_id=row["application_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                company_name=row["company_name"],
                job_title=row["job_title"],
                recipient_email=row["recipient_email"],
                resume_filename=row["resume_filename"],
                pdf_filename=row["pdf_filename"],
                email_subject=row["email_subject"],
                email_status=row["email_status"],
                gmail_message_id=row["gmail_message_id"],
            )
        )
    return records
