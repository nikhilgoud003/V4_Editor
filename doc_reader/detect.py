"""Choose a reader from the JSON shape, not from the file name."""

from __future__ import annotations


def is_ocr_layout(data) -> bool:
    if not isinstance(data, dict):
        return False
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        return False
    for page in pages:
        if not isinstance(page, dict):
            continue
        blocks = page.get("blocks")
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                return True
    return False


def is_docket(data) -> bool:
    """PACER docket JSON is out of scope for this reader."""
    if not isinstance(data, dict) or is_ocr_layout(data):
        return False
    has_case = "ucid" in data or "docket" in data
    has_parties = "parties" in data or "docket" in data
    return bool(has_case and has_parties)


def detect_kind(data) -> str:
    if is_ocr_layout(data):
        return "ocr"
    if is_docket(data):
        return "docket"
    return "generic"


def iter_text_fields(data, path: str = "$"):
    """Yield (json_path, text) for every string in a non-OCR JSON value."""
    if isinstance(data, dict):
        for key, value in data.items():
            yield from iter_text_fields(value, f"{path}.{key}")
    elif isinstance(data, list):
        for index, value in enumerate(data):
            yield from iter_text_fields(value, f"{path}[{index}]")
    elif isinstance(data, str) and data.strip():
        yield path, data
