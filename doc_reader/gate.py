"""Person check for judges, counsel, and person-parties.

spaCy must mark the name as PERSON in the block, and probablepeople must say
Person. If the two disagree, the mention goes to review. A counsel span that
is an organisation becomes a firm. If probablepeople is not installed, the
second vote is the GLiNER2 label instead.
"""

from __future__ import annotations

try:
    import probablepeople as _probablepeople
except ImportError:  # pragma: no cover - exercised only when the package is absent
    _probablepeople = None

PP_AVAILABLE = _probablepeople is not None


def probablepeople_kind(name: str) -> str:
    """Return Person, Corporation, or Unknown."""
    if _probablepeople is None or not (name or "").strip():
        return "Unknown"
    try:
        _parsed, kind = _probablepeople.tag(name)
    except Exception:
        return "Unknown"
    if kind in {"Person", "Corporation"}:
        return kind
    return "Unknown"


def gliner_kind(label: str) -> str:
    """Second vote used only when probablepeople is not installed."""
    if label in {"judge", "attorney", "attorney_for_plaintiff", "attorney_for_defendant"}:
        return "Person"
    if label == "law_firm":
        return "Corporation"
    return "Unknown"


def spacy_flags(doc, name: str) -> tuple[bool, bool]:
    """Whether the block's NER marks this name as PERSON and as ORG."""
    target = " ".join((name or "").split()).lower()
    if doc is None or not target:
        return False, False
    person = False
    org = False
    for ent in doc.ents:
        span = " ".join(ent.text.split()).lower()
        if not span:
            continue
        if target not in span and span not in target:
            continue
        if ent.label_ == "PERSON":
            person = True
        elif ent.label_ == "ORG":
            org = True
    return person, org


def gate_decision(entity_type: str, spacy_person: bool, second_kind: str, spacy_org: bool = False) -> str:
    """Return keep, firm, or review.

    firm: counsel that is an organisation, kept as a firm.
    keep: accepted into mentions.
    review: disagreement or an unconfirmed person.
    """
    if entity_type == "firm":
        return "keep"
    is_org = second_kind == "Corporation" or (spacy_org and not spacy_person)
    both_person = spacy_person and second_kind == "Person"
    if entity_type == "counsel" and is_org and not spacy_person:
        return "firm"
    if entity_type == "party" and is_org and not both_person and not spacy_person:
        return "keep"
    if entity_type in {"judge", "counsel", "party"}:
        if both_person:
            return "keep"
        return "review"
    return "review"
