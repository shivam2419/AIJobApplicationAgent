from __future__ import annotations

import re

from models.resume_changes import ResumeChange


class LatexEditError(ValueError):
    """The requested targeted LaTeX edit is unsafe or ambiguous."""


_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

_LINK_MACRO = re.compile(r"\\(?:href|url|nolinkurl|email|path)\b")
_SIMPLE_COMMAND_ARGUMENT = re.compile(
    r"^(?P<prefix>\\[A-Za-z@]+\*?(?:\[[^\]\n]*\])?\{)"
    r"(?P<content>[^{}\\$%]*)"
    r"(?P<suffix>\})$",
    re.DOTALL,
)


def _protected_link_spans(source: str) -> list[tuple[int, int]]:
    spans = []
    for command in _LINK_MACRO.finditer(source):
        cursor = command.end()
        argument_count = 2 if command.group().endswith("href") else 1
        for _ in range(argument_count):
            while cursor < len(source) and source[cursor].isspace():
                cursor += 1
            if cursor < len(source) and source[cursor] == "[":
                closing = source.find("]", cursor + 1)
                if closing < 0:
                    break
                cursor = closing + 1
                while cursor < len(source) and source[cursor].isspace():
                    cursor += 1
            if cursor >= len(source) or source[cursor] != "{":
                break
            depth = 0
            while cursor < len(source):
                char = source[cursor]
                if char == "\\":
                    cursor += 2
                    continue
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        cursor += 1
                        break
                cursor += 1
        if cursor > command.end():
            spans.append((command.start(), cursor))
    return spans


def escape_latex_text(value: str) -> str:
    return "".join(_SPECIALS.get(char, char) for char in value)


def _replacement_for_latex_span(original: str, proposed: str, section: str) -> str:
    if not any(char in original for char in ("\\", "{", "}", "$", "%")):
        return escape_latex_text(proposed)

    wrapper = _SIMPLE_COMMAND_ARGUMENT.fullmatch(original)
    if wrapper:
        return (
            wrapper.group("prefix")
            + escape_latex_text(proposed)
            + wrapper.group("suffix")
        )

    raise LatexEditError(
        f"The AI selected a LaTeX command instead of a plain-text phrase for "
        f"section '{section}'. Clear this workflow and analyze again; the template "
        "commands will be preserved."
    )


def _safe_replacement_spans(source: str) -> list[tuple[int, int]]:
    spans = [(match.start(), match.end()) for match in _LINK_MACRO.finditer(source)]
    spans.extend(
        (match.start(), match.end())
        for match in re.finditer(
            r"\\(?:input|include|includegraphics|write18|immediate)\b", source
        )
    )
    return spans


def apply_approved_changes(
    source: str, changes: list[ResumeChange], approved_indices: set[int]
) -> str:
    result = source
    selected = [change for index, change in enumerate(changes) if index in approved_indices]
    for change in selected:
        original = change.original_text
        if not original.strip() or original not in result:
            raise LatexEditError(
                f"Could not locate the exact original text for section '{change.section}'."
            )
        if result.count(original) != 1:
            raise LatexEditError(
                f"The original text for section '{change.section}' is ambiguous; edit skipped."
            )
        position = result.index(original)
        if any(start <= position < end for start, end in _protected_link_spans(result)):
            raise LatexEditError(
                f"The original text for section '{change.section}' is inside a link or URL; edit skipped."
            )
        if any(start <= position < end for start, end in _safe_replacement_spans(result)):
            raise LatexEditError(
                f"The original text for section '{change.section}' contains a command that "
                "must not be changed."
            )
        replacement = _replacement_for_latex_span(
            original, change.proposed_text, change.section
        )
        result = result.replace(original, replacement, 1)
    if result.count("\\begin{document}") != 1 or result.count("\\end{document}") != 1:
        raise LatexEditError("The edited source does not have a valid document boundary.")
    if not re.search(r"\\documentclass(?:\[[^\]]*\])?\{[^{}]+\}", result):
        raise LatexEditError("The edited source has no valid document class.")
    return result
