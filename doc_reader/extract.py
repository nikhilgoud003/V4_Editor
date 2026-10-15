"""Read one JSON document into mentions and review rows."""

from __future__ import annotations

import statistics
from pathlib import Path

from doc_reader.case_id import cross_check, parse_filename
from doc_reader.chunk import block_inputs
from doc_reader.clean import clean_pages
from doc_reader.detect import detect_kind, iter_text_fields
from doc_reader.gate import gate_decision, gliner_kind, probablepeople_kind, spacy_flags
from doc_reader.labels import CONTACT_LABELS, LABEL_TO_TYPE
from doc_reader.models import ReaderModels
from doc_reader.records import make_mention, squash


def _score(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _inside_focus(span: dict, model_input: str, focus: str) -> bool:
    start, end = span.get("start"), span.get("end")
    if isinstance(start, int) and isinstance(end, int):
        at = model_input.find(focus)
        if at < 0:
            return False
        return start >= at and end <= at + len(focus)
    text = squash(span.get("text") or "")
    return bool(text) and text in squash(focus)


def _attach_contacts(people: list[dict], contacts: list[dict]) -> None:
    for contact in contacts:
        if not people:
            break
        label = contact["label"]
        if label not in {"email", "phone", "address", "law_firm"}:
            continue
        value = squash(contact.get("text") or "")
        if not value:
            continue
        host = min(
            people,
            key=lambda row: abs((row.get("start") or 0) - (contact.get("start") or 0)),
        )
        field = {"email": "email", "phone": "phone", "address": "address", "law_firm": "firm"}[label]
        if not host.get(field):
            host[field] = value


def _spans_to_mentions(spans: list[dict], model_input: str, focus: str) -> list[dict]:
    people = []
    contacts = []
    for span in spans:
        label = span.get("label")
        if label not in LABEL_TO_TYPE and label not in CONTACT_LABELS:
            continue
        if not _inside_focus(span, model_input, focus):
            continue
        if label in CONTACT_LABELS:
            contacts.append(span)
            continue
        entity_type, role, side = LABEL_TO_TYPE[label]
        people.append(
            {
                "label": label,
                "name": squash(span.get("text") or ""),
                "entity_type": entity_type,
                "role": role,
                "side": side,
                "score": _score(span.get("score")),
                "start": span.get("start") if isinstance(span.get("start"), int) else 0,
                "email": span.get("email") or "",
                "phone": span.get("phone") or "",
                "address": span.get("address") or "",
                "firm": span.get("firm") or "",
            }
        )
    _attach_contacts(people, contacts)
    for contact in contacts:
        if contact.get("label") != "law_firm":
            continue
        people.append(
            {
                "label": "law_firm",
                "name": squash(contact.get("text") or ""),
                "entity_type": "firm",
                "role": "firm",
                "side": "",
                "score": _score(contact.get("score")),
                "start": contact.get("start") if isinstance(contact.get("start"), int) else 0,
                "email": "",
                "phone": "",
                "address": "",
                "firm": "",
            }
        )
    return [row for row in people if row["name"]]


def _review_cutoff(scores: list[float]) -> float | None:
    if len(scores) < 4:
        return None
    ordered = sorted(scores)

    def q(p: float) -> float:
        pos = (len(ordered) - 1) * p
        lo = int(pos)
        hi = min(lo + 1, len(ordered) - 1)
        frac = pos - lo
        return ordered[lo] * (1 - frac) + ordered[hi] * frac

    q1, q3 = q(0.25), q(0.75)
    return max(0.0, q1 - 1.5 * (q3 - q1))


def _apply_gate(row: dict, doc, models: ReaderModels) -> str:
    if row["entity_type"] == "firm":
        return "keep"
    person, org = spacy_flags(doc, row["name"])
    if models.pp_available:
        second = probablepeople_kind(row["name"])
    else:
        second = gliner_kind(row["label"])
    return gate_decision(row["entity_type"], person, second, org)


def _read_block(models: ReaderModels, block: dict, prev: str, nxt: str) -> list[dict]:
    pieces = block_inputs(
        block["text"],
        prev,
        nxt,
        models.max_words,
        models.max_tokens,
        models.count_tokens,
    )
    found = []
    for model_input, focus in pieces:
        spans = models.extract(model_input)
        found.extend(_spans_to_mentions(spans, model_input, focus))
    return found


def _row_from(found: dict, block: dict, case: dict, filename: str, json_path: str, reason: str) -> dict:
    return make_mention(
        raw_name=found["name"],
        entity_type=found["entity_type"],
        ucid=case["ucid"],
        court=case["court"],
        role=found["role"],
        side=found["side"],
        email=found.get("email") or "",
        phone=found.get("phone") or "",
        address=found.get("address") or "",
        firm=found.get("firm") or "",
        page=block.get("page"),
        bbox=block.get("bbox"),
        block_confidence=block.get("confidence"),
        model_score=found.get("score"),
        source_text=block.get("text") or "",
        document_number=case["document_number"],
        filename=filename,
        json_path=json_path,
        review_reason=reason,
    )


def _counts(rows: list[dict]) -> dict:
    counts = {"judge": 0, "party": 0, "counsel": 0, "firm": 0}
    for row in rows:
        key = row.get("entity_type")
        if key in counts:
            counts[key] += 1
    return counts


def read_document(path: Path, data, models: ReaderModels) -> dict:
    kind = detect_kind(data)
    filename = ""
    if isinstance(data, dict) and isinstance(data.get("filename"), str):
        filename = data["filename"]
    if not filename:
        filename = path.name
    case = parse_filename(filename)
    mentions: list[dict] = []
    review: list[dict] = []
    info = {
        "file": path.name,
        "kind": kind,
        "ucid": case["ucid"],
        "court": case["court"],
        "document_number": case["document_number"],
        "case_check": "",
        "counts": {},
        "dropped": {},
    }
    if kind == "docket":
        info["case_check"] = "skipped_docket"
        info["counts"] = _counts(mentions)
        info["review_count"] = 0
        return {"mentions": mentions, "review": review, "info": info}

    if kind == "ocr":
        blocks, dropped = clean_pages(data.get("pages") or [])
        info["dropped"] = dropped
        info["case_check"] = cross_check(case["case_key"], "\n".join(b["text"] for b in blocks))
        units = []
        for index, block in enumerate(blocks):
            prev = blocks[index - 1]["text"] if index and blocks[index - 1]["page"] == block["page"] else ""
            nxt = ""
            if index + 1 < len(blocks) and blocks[index + 1]["page"] == block["page"]:
                nxt = blocks[index + 1]["text"]
            page = block.get("page")
            units.append((block, prev, nxt, f"$.pages[{page}].blocks[{index}]"))
    else:
        info["dropped"] = {
            "blocks_in": 0,
            "blocks_kept": 0,
            "dropped_low_confidence": 0,
            "dropped_duplicate": 0,
            "confidence_threshold": None,
        }
        fields = list(iter_text_fields(data))
        info["case_check"] = cross_check(case["case_key"], "\n".join(text for _path, text in fields))
        units = [
            ({"text": text, "page": None, "bbox": None, "confidence": None}, "", "", json_path)
            for json_path, text in fields
        ]

    for block, prev, nxt, json_path in units:
        doc = models.spacy_doc(block["text"])
        for found in _read_block(models, block, prev, nxt):
            decision = _apply_gate(found, doc, models)
            if decision == "firm":
                found = dict(found)
                found["entity_type"] = "firm"
                found["role"] = "firm"
                mentions.append(_row_from(found, block, case, filename, json_path, ""))
            elif decision == "keep":
                mentions.append(_row_from(found, block, case, filename, json_path, ""))
            else:
                review.append(_row_from(found, block, case, filename, json_path, "person_gate"))

    scores = [row["model_score"] for row in mentions + review if isinstance(row["model_score"], float)]
    cutoff = _review_cutoff(scores)
    if cutoff is not None:
        still = []
        for row in mentions:
            score = row["model_score"]
            if isinstance(score, float) and score < cutoff:
                row["review_reason"] = "low_model_score"
                review.append(row)
            else:
                still.append(row)
        mentions = still
    info["counts"] = _counts(mentions)
    info["review_count"] = len(review)
    info["model_score_review_cutoff"] = cutoff
    return {"mentions": mentions, "review": review, "info": info}


def summarise_times(infos: list[dict]) -> str:
    times = [item["seconds"] for item in infos if isinstance(item.get("seconds"), (int, float))]
    if not times:
        return "n=0"
    return f"n={len(times)} total={sum(times):.2f}s median={statistics.median(times):.2f}s"
