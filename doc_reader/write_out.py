"""Write mentions.jsonl, review.jsonl, review_docs.csv, and report.md."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from doc_reader.records import EXTRA_FIELDS, V4_FIELDS


def write_outputs(folder: Path, mentions: list[dict], review: list[dict], infos: list[dict], models_used: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    _jsonl(folder / "mentions.jsonl", mentions)
    _jsonl(folder / "review.jsonl", review)
    _csv(folder / "review_docs.csv", mentions + review)
    (folder / "report.md").write_text(_report(infos, mentions, review, models_used), encoding="utf-8")


def _jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _csv(path: Path, rows: list[dict]) -> None:
    columns = list(V4_FIELDS) + list(EXTRA_FIELDS) + ["correct?"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["context"] = json.dumps(row.get("context") or {}, ensure_ascii=False)
            flat["bbox"] = json.dumps(row.get("bbox"), ensure_ascii=False)
            flat["correct?"] = ""
            writer.writerow(flat)


def _report(infos: list[dict], mentions: list[dict], review: list[dict], models_used: str) -> str:
    lines = [
        "# Document reader report",
        "",
        f"Models: {models_used}",
        "",
        f"Mentions written: {len(mentions)}",
        f"Review rows: {len(review)}",
        "",
        "## Per document",
        "",
        "| file | kind | ucid | case check | judge | party | counsel | firm | review | dropped low | dropped duplicate | threshold | seconds |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for info in infos:
        counts = info.get("counts") or {}
        dropped = info.get("dropped") or {}
        seconds = info.get("seconds")
        sec = f"{seconds:.2f}" if isinstance(seconds, (int, float)) else ""
        threshold = dropped.get("confidence_threshold")
        thr = "" if threshold is None else str(threshold)
        lines.append(
            "| {file} | {kind} | {ucid} | {check} | {j} | {p} | {c} | {f} | {r} | {low} | {dup} | {thr} | {sec} |".format(
                file=info.get("file") or "",
                kind=info.get("kind") or "",
                ucid=info.get("ucid") or "",
                check=info.get("case_check") or "",
                j=counts.get("judge", 0),
                p=counts.get("party", 0),
                c=counts.get("counsel", 0),
                f=counts.get("firm", 0),
                r=info.get("review_count", 0),
                low=dropped.get("dropped_low_confidence", 0),
                dup=dropped.get("dropped_duplicate", 0),
                thr=thr,
                sec=sec,
            )
        )
    lines.append("")
    return "\n".join(lines)
