from __future__ import annotations

import shutil
import subprocess
import os
import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)


class LatexCompilationError(RuntimeError):
    """LaTeX source could not be compiled to PDF."""


def compile_latex(source_path: Path, timeout_seconds: int = 120) -> Path:
    compiler = shutil.which("pdflatex")
    if not compiler:
        raise LatexCompilationError(
            "pdflatex is not installed. Install MiKTeX or TeX Live and ensure "
            "pdflatex is on PATH, then restart the application."
        )
    output = source_path.with_suffix(".pdf")
    environment = {
        key: os.environ[key]
        for key in (
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
            "HOME",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
        )
        if key in os.environ
    }
    try:
        result = subprocess.run(
            [
                compiler,
                "-no-shell-escape",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={source_path.parent}",
                source_path.name,
            ],
            cwd=source_path.parent,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise LatexCompilationError("LaTeX compilation exceeded its 120-second limit.") from exc
    except OSError as exc:
        raise LatexCompilationError("The LaTeX compiler could not be started.") from exc
    finally:
        for suffix in (".aux", ".log", ".out", ".toc", ".fls", ".fdb_latexmk"):
            artifact = source_path.with_suffix(suffix)
            try:
                artifact.unlink(missing_ok=True)
            except OSError:
                LOGGER.warning("Could not remove temporary LaTeX artifact: %s", artifact.name)
    if result.returncode != 0 or not output.is_file():
        LOGGER.warning(
            "LaTeX compilation failed for %s (exit code %s).",
            source_path.name,
            result.returncode,
        )
        raise LatexCompilationError(
            "LaTeX compilation failed. Check source syntax and whether required packages "
            "are installed. The original source file was not changed."
        )
    return output
