"""Mention rows. Field names match the mentions written by v4_run_ctx.py, plus document fields."""

from __future__ import annotations

import re

V4_FIELDS = (
    "mention_id",
    "raw_name",
    "clean_name",
    "entity_type",
    "ucid",
    "court",
    "context",
    "entity_id",
)

EXTRA_FIELDS = (
    "source",
    "name",
    "type",
    "role",
    "side",
    "email",
    "phone",
    "address",
    "firm",
    "page",
    "bbox",
    "block_confidence",
    "model_score",
    "source_text",
    "document_number",
    "filename",
    "json_path",
    "review_reason",
)


def clean_name(name: str) -> str:
    text = " ".join((name or "").split()).lower()
    return text.strip(".,;:\"'`()[]{}")


def make_mention(
    *,
    raw_name: str,
    entity_type: str,
    ucid: str,
    court: str,
    role: str,
    side: str,
    email: str,
    phone: str,
    address: str,
    firm: str,
    page,
    bbox,
    block_confidence,
    model_score,
    source_text: str,
    document_number: str,
    filename: str,
    json_path: str,
    review_reason: str = "",
) -> dict:
    raw = " ".join((raw_name or "").split())
    context = {
        "emails": [email] if email else [],
        "phones": [phone] if phone else [],
        "addresses": [address] if address else [],
        "offices": [firm] if firm else [],
        "role": [role] if role else [],
        "side": [side] if side else [],
    }
    row = {
        "mention_id": "",
        "raw_name": raw,
        "clean_name": clean_name(raw),
        "entity_type": entity_type,
        "ucid": ucid,
        "court": court,
        "context": context,
        "entity_id": None,
        "source": "document",
        "name": raw,
        "type": entity_type,
        "role": role,
        "side": side,
        "email": email,
        "phone": phone,
        "address": address,
        "firm": firm,
        "page": page,
        "bbox": bbox,
        "block_confidence": block_confidence,
        "model_score": model_score,
        "source_text": source_text,
        "document_number": document_number,
        "filename": filename,
        "json_path": json_path,
        "review_reason": review_reason,
    }
    return row


def assign_ids(rows: list[dict], start: int = 0) -> list[dict]:
    for offset, row in enumerate(rows):
        row["mention_id"] = f"mnt_{start + offset}"
    return rows


_SPACE = re.compile(r"\s+")


def squash(text: str) -> str:
    return _SPACE.sub(" ", text or "").strip()
