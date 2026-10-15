"""Load the extractor once. Cache one result per distinct text. Run on CPU."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable

from doc_reader.gate import PP_AVAILABLE
from doc_reader.labels import LABELS

GLINER_ID = "fastino/gliner2-base-v1"
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_SHOW = "http://localhost:11434/api/show"


def _finite_int(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value <= 0 or value >= 100_000:
        return None
    return value


def find_tokenizer(model):
    seen = set()
    stack = [model]
    while stack and len(seen) < 40:
        obj = stack.pop()
        if obj is None or id(obj) in seen:
            continue
        seen.add(id(obj))
        if hasattr(obj, "model_max_length") and callable(getattr(obj, "encode", None)):
            return obj
        for attr in ("tokenizer", "transformer_tokenizer", "data_processor", "processor"):
            child = getattr(obj, attr, None)
            if child is not None and not isinstance(child, (str, int, float, dict, list)):
                stack.append(child)
    return None


def gliner_limits(model) -> tuple[int, int, Callable[[str], int] | None, str]:
    """Word cap and token cap taken from the loaded model. Reported as text."""
    cfg = getattr(model, "config", None)
    word_cap = None
    for attr in ("max_len", "max_length"):
        word_cap = _finite_int(getattr(cfg, attr, None))
        if word_cap:
            break
    tokenizer = find_tokenizer(model)
    token_cap = None
    if tokenizer is not None:
        token_cap = _finite_int(getattr(tokenizer, "model_max_length", None))
    if word_cap is None:
        word_cap = 384
    if token_cap is None:
        token_cap = word_cap

    def count_tokens(text: str) -> int:
        if tokenizer is None:
            return len(text.split())
        encoded = tokenizer(text, add_special_tokens=True, truncation=False)
        ids = encoded["input_ids"]
        shape = getattr(ids, "shape", None)
        if shape is not None:
            return int(shape[-1])
        return len(ids)

    note = (
        f"gliner word_cap={word_cap} token_cap={token_cap} "
        f"tokenizer={'yes' if tokenizer else 'no'}"
    )
    return word_cap, token_cap, count_tokens, note


def ollama_context_length(model_name: str) -> int:
    body = json.dumps({"model": model_name}).encode()
    req = urllib.request.Request(
        OLLAMA_SHOW, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        info = json.loads(resp.read().decode())
    for key, value in (info.get("model_info") or {}).items():
        if str(key).endswith("context_length") and _finite_int(int(value) if str(value).isdigit() else value):
            return int(value)
    params = info.get("parameters") or ""
    for part in str(params).split():
        if part.startswith("num_ctx"):
            continue
    return 2048


class ReaderModels:
    def __init__(self, kind: str, ollama_model: str, gliner_id: str = GLINER_ID):
        self.kind = kind
        self.ollama_model = ollama_model
        self.gliner_id = gliner_id
        self.pp_available = PP_AVAILABLE
        self._extract_cache: dict[str, list] = {}
        self._spacy_cache: dict[str, object] = {}
        self.model = None
        self.nlp = None
        self.count_tokens = None
        self.max_words = 384
        self.max_tokens = 384
        self.limit_note = ""
        self._load()

    def _load(self) -> None:
        import spacy

        self.nlp = spacy.load("en_core_web_sm")
        if self.kind == "ollama":
            ctx = ollama_context_length(self.ollama_model)
            # Leave room for the instruction. Words stay under the context length.
            self.max_tokens = max(32, ctx - 256)
            self.max_words = max(16, self.max_tokens // 2)
            self.count_tokens = lambda text: len(text.split())
            self.limit_note = (
                f"ollama model={self.ollama_model} context_checked word_cap={self.max_words} "
                f"token_cap={self.max_tokens}"
            )
            self.model_note = f"ollama:{self.ollama_model}"
            return

        from gliner2 import GLiNER2

        self.model = GLiNER2.from_pretrained(self.gliner_id)
        to_cpu = getattr(self.model, "cpu", None)
        if callable(to_cpu):
            self.model = to_cpu()
        self.max_words, self.max_tokens, self.count_tokens, self.limit_note = gliner_limits(self.model)
        self.model_note = f"gliner2:{self.gliner_id}"

    def spacy_doc(self, text: str):
        key = text or ""
        doc = self._spacy_cache.get(key)
        if doc is None:
            doc = self.nlp(key)
            self._spacy_cache[key] = doc
        return doc

    def extract(self, text: str) -> list[dict]:
        key = text or ""
        if key in self._extract_cache:
            return self._extract_cache[key]
        if not key.strip():
            self._extract_cache[key] = []
            return []
        if self.kind == "ollama":
            rows = self._ollama(key)
        else:
            rows = self._gliner(key)
        self._extract_cache[key] = rows
        return rows

    def _gliner(self, text: str) -> list[dict]:
        result = self.model.extract_entities(
            text,
            LABELS,
            include_confidence=True,
            include_spans=True,
            max_len=self.max_words,
        )
        rows = []
        entities = (result or {}).get("entities") or {}
        if isinstance(entities, list):
            entities = entities[0] if entities and isinstance(entities[0], dict) else {}
        if not isinstance(entities, dict):
            entities = {}
        for label, spans in entities.items():
            if not isinstance(spans, list):
                continue
            for span in spans:
                if isinstance(span, str):
                    rows.append({"label": label, "text": span, "score": None, "start": None, "end": None})
                    continue
                if not isinstance(span, dict):
                    continue
                rows.append(
                    {
                        "label": label,
                        "text": span.get("text") or "",
                        "score": span.get("confidence"),
                        "start": span.get("start"),
                        "end": span.get("end"),
                    }
                )
        return rows

    def _ollama(self, text: str) -> list[dict]:
        instruction = (
            "Read only the text below. Return JSON with one key, mentions, a list. "
            "Each item has name, type, role, side, email, phone, address, firm, score. "
            "type is judge, party, counsel, or firm. "
            "role is judge, plaintiff, defendant, attorney, or firm. "
            "side is plaintiff, defendant, or an empty string. "
            "score is a number from 0 to 1. Use empty strings when a field is absent. "
            "Do not add names that are not in the text.\n\n"
        )
        payload = {
            "model": self.ollama_model,
            "stream": False,
            "format": "json",
            "messages": [{"role": "user", "content": instruction + text}],
        }
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc
        content = ((body.get("message") or {}).get("content")) or "{}"
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return []
        rows = []
        for item in parsed.get("mentions") or []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            type_name = str(item.get("type") or "")
            label = {
                "judge": "judge",
                "party": "plaintiff" if item.get("side") == "plaintiff" else "defendant",
                "counsel": "attorney",
                "firm": "law_firm",
            }.get(type_name, type_name)
            side = item.get("side") or ""
            if side == "plaintiff" and type_name == "counsel":
                label = "attorney_for_plaintiff"
            elif side == "defendant" and type_name == "counsel":
                label = "attorney_for_defendant"
            rows.append(
                {
                    "label": label,
                    "text": str(item.get("name")),
                    "score": item.get("score"),
                    "start": None,
                    "end": None,
                    "email": item.get("email") or "",
                    "phone": item.get("phone") or "",
                    "address": item.get("address") or "",
                    "firm": item.get("firm") or "",
                }
            )
        return rows

    def models_used(self) -> str:
        second = "probablepeople" if self.pp_available else "GLiNER2 label (probablepeople is not installed)"
        return f"{self.model_note}; spaCy en_core_web_sm; person second vote: {second}; {self.limit_note}"
