from __future__ import annotations

import hashlib
import json
from pathlib import Path


def message_fingerprint(recipient: str, subject: str, body: str, pdf_path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(
        json.dumps([recipient.strip().lower(), subject, body], ensure_ascii=False).encode(
            "utf-8"
        )
    )
    digest.update(pdf_path.read_bytes())
    return digest.hexdigest()


def managed_output_path(root: Path, application_id: str, filename: str) -> Path:
    directory = (root / application_id).resolve()
    output_root = root.resolve()
    if directory.parent != output_root:
        raise ValueError("Invalid application output directory.")
    target = (directory / filename).resolve()
    if target.parent != directory or Path(filename).name != filename:
        raise ValueError("Invalid output filename.")
    directory.mkdir(parents=True, exist_ok=True)
    return target
