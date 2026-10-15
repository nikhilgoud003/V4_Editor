"""Parse a case id from a filename. The pattern is structural, not a list of courts."""

from __future__ import annotations

import re
from pathlib import Path

# court + separator (;; or _) + office-year-kind-seq + optional _document
_FILENAME = re.compile(
    r"(?P<court>[A-Za-z]+)"
    r"(?:;;|_)"
    r"(?P<office>\d+)-(?P<year>\d{2})-(?P<kind>[A-Za-z]+)-(?P<seq>\d+)"
    r"(?:_(?P<doc>\d+))?"
)

# The same case number as it appears in prose, with a colon or a hyphen after the office.
_IN_TEXT = re.compile(
    r"\b(?P<office>\d+)\s*[:\-]\s*(?P<year>\d{2})\s*-\s*(?P<kind>[A-Za-z]+)\s*-\s*(?P<seq>\d+)\b"
)


def parse_filename(filename: str) -> dict:
    """Return ucid, court, document_number, and the case key. Empty when the name does not match."""
    stem = Path(filename).name
    stem = re.sub(r"\.json$", "", stem, flags=re.IGNORECASE)
    match = _FILENAME.search(stem)
    if not match:
        return {
            "ucid": "",
            "court": "",
            "document_number": "",
            "case_key": "",
        }
    court = match.group("court").lower()
    office = match.group("office")
    year = match.group("year")
    kind = match.group("kind").lower()
    seq = match.group("seq")
    doc = match.group("doc") or ""
    case_key = f"{office}:{year}-{kind}-{seq}"
    return {
        "ucid": f"{court};;{case_key}",
        "court": court,
        "document_number": doc,
        "case_key": case_key,
    }


def case_keys_in_text(text: str) -> list[str]:
    keys = []
    for match in _IN_TEXT.finditer(text or ""):
        key = (
            f"{match.group('office')}:{match.group('year')}-"
            f"{match.group('kind').lower()}-{match.group('seq')}"
        )
        if key not in keys:
            keys.append(key)
    return keys


def cross_check(case_key: str, text: str) -> str:
    """Compare the filename case key with case numbers found in the text."""
    found = case_keys_in_text(text)
    if not case_key:
        return "filename_unparsed" if not found else "text_only"
    if not found:
        return "not_in_text"
    if case_key in found:
        return "match"
    return "mismatch"
