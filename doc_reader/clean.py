"""Drop duplicate and very-low-confidence layout blocks.

The confidence cut is the lower Tukey fence of this file's own scores
(first quartile minus 1.5 times the interquartile range). It is not a fixed list.
"""

from __future__ import annotations

from difflib import SequenceMatcher

NEAR_TEXT = 0.92
STRONG_OVERLAP = 0.5


def _quantile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def confidence_threshold(values: list[float]) -> float:
    scores = sorted(v for v in values if isinstance(v, (int, float)))
    if not scores:
        return 0.0
    q1 = _quantile(scores, 0.25)
    q3 = _quantile(scores, 0.75)
    return max(0.0, q1 - 1.5 * (q3 - q1))


def norm_text(text: str) -> str:
    return " ".join((text or "").split()).lower()


def near_same_text(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    if abs(len(a) - len(b)) / max(len(a), len(b)) > 0.3:
        return False
    return SequenceMatcher(None, a, b).ratio() >= NEAR_TEXT


def bbox_iou(a, b) -> float:
    if not a or not b or len(a) < 4 or len(b) < 4:
        return 0.0
    ax1, ay1, ax2, ay2 = (float(x) for x in a[:4])
    bx1, by1, bx2, by2 = (float(x) for x in b[:4])
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def clean_pages(pages: list) -> tuple[list[dict], dict]:
    """Return kept blocks (page order) and a drop report for this file."""
    raw = []
    for page in pages or []:
        if not isinstance(page, dict):
            continue
        page_no = page.get("page")
        for block in page.get("blocks") or []:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            conf = block.get("confidence")
            try:
                conf_f = float(conf) if conf is not None else 0.0
            except (TypeError, ValueError):
                conf_f = 0.0
            raw.append(
                {
                    "page": page_no,
                    "text": text,
                    "norm": norm_text(text),
                    "confidence": conf_f,
                    "bbox": block.get("bbox"),
                    "block_class": block.get("class"),
                }
            )

    threshold = confidence_threshold([b["confidence"] for b in raw])
    kept_pool: list[dict] = []
    dropped_low = 0
    dropped_dup = 0
    # Higher confidence wins. Original order breaks ties.
    ranked = sorted(enumerate(raw), key=lambda item: (-item[1]["confidence"], item[0]))
    accepted_idx = set()
    for idx, block in ranked:
        if block["confidence"] < threshold:
            dropped_low += 1
            continue
        duplicate = False
        for other in kept_pool:
            if other["page"] != block["page"]:
                continue
            if near_same_text(block["norm"], other["norm"]) or bbox_iou(block["bbox"], other["bbox"]) >= STRONG_OVERLAP:
                duplicate = True
                break
        if duplicate:
            dropped_dup += 1
            continue
        kept_pool.append(block)
        accepted_idx.add(idx)

    kept = [raw[i] for i in range(len(raw)) if i in accepted_idx]
    report = {
        "blocks_in": len(raw),
        "blocks_kept": len(kept),
        "dropped_low_confidence": dropped_low,
        "dropped_duplicate": dropped_dup,
        "confidence_threshold": round(threshold, 6),
    }
    return kept, report
