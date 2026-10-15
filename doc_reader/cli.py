"""Command line: python -m doc_reader --input <folder or files> --output <folder>."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from doc_reader.extract import read_document
from doc_reader.models import ReaderModels
from doc_reader.records import assign_ids
from doc_reader.write_out import write_outputs


def collect_files(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(p for p in path.iterdir() if p.suffix.lower() == ".json" and p.is_file()))
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(path)
    unique = []
    seen = set()
    for path in files:
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def run(inputs: list[str], output: str, model: str, ollama_model: str) -> None:
    files = collect_files(inputs)
    if not files:
        raise SystemExit("No JSON files found.")
    models = ReaderModels(model, ollama_model)
    mentions: list[dict] = []
    review: list[dict] = []
    infos: list[dict] = []
    for path in files:
        started = time.perf_counter()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            infos.append(
                {
                    "file": path.name,
                    "kind": "error",
                    "ucid": "",
                    "case_check": str(exc),
                    "counts": {},
                    "dropped": {},
                    "review_count": 0,
                    "seconds": time.perf_counter() - started,
                }
            )
            continue
        result = read_document(path, data, models)
        mentions.extend(result["mentions"])
        review.extend(result["review"])
        info = result["info"]
        info["seconds"] = time.perf_counter() - started
        infos.append(info)
        print(
            f"{path.name} {info['kind']} mentions={sum((info.get('counts') or {}).values())} "
            f"review={info.get('review_count', 0)} {info['seconds']:.2f}s",
            flush=True,
        )
    assign_ids(mentions)
    assign_ids(review, start=len(mentions))
    out = Path(output)
    write_outputs(out, mentions, review, infos, models.models_used())
    print(f"wrote {out}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read OCR or layout JSON into entity mentions.")
    parser.add_argument("--input", nargs="+", required=True, help="JSON file or folder of JSON files")
    parser.add_argument("--output", required=True, help="Folder for mentions, review, and the report")
    parser.add_argument("--model", choices=("gliner", "ollama"), default="gliner")
    parser.add_argument("--ollama-model", default="qwen2.5:7b")
    args = parser.parse_args(argv)
    run(args.input, args.output, args.model, args.ollama_model)
    return 0
