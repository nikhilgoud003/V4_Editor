"""Split one block, plus its page neighbours, into pieces that fit a length cap.

The cap is the model's own maximum (word cap and token cap). A whole document
is never passed in.
"""

from __future__ import annotations


def _words(text: str) -> list[str]:
    return (text or "").split()


def windows(text: str, max_words: int) -> list[str]:
    """Split text into pieces of at most max_words words. Pieces cover the text in order."""
    if max_words < 1:
        raise ValueError("max_words must be at least 1")
    words = _words(text)
    if not words:
        return []
    return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]


def _token_count(text: str, count_tokens) -> int:
    if count_tokens is None:
        return len(_words(text))
    return int(count_tokens(text))


def fit_piece(piece: str, prev: str, nxt: str, max_words: int, max_tokens: int, count_tokens) -> str:
    """Return piece, with as much neighbour text as still fits both caps."""
    piece_words = _words(piece)
    if len(piece_words) > max_words:
        piece_words = piece_words[:max_words]
        piece = " ".join(piece_words)
    prev_words = _words(prev)
    next_words = _words(nxt)
    # Neighbours sit outside the block. Shrink them until the wrapped text fits.
    pre_n = min(len(prev_words), max(0, max_words - len(piece_words)) // 2)
    post_n = min(len(next_words), max(0, max_words - len(piece_words) - pre_n))

    def build(pn: int, qn: int, pw: list[str]) -> str:
        parts = []
        if pn:
            parts.append(" ".join(prev_words[-pn:]))
        parts.append(" ".join(pw))
        if qn:
            parts.append(" ".join(next_words[:qn]))
        return "\n".join(parts)

    piece_list = piece_words
    while True:
        text = build(pre_n, post_n, piece_list)
        words_ok = len(_words(text)) <= max_words
        tokens_ok = _token_count(text, count_tokens) <= max_tokens
        if words_ok and tokens_ok:
            return text
        if pre_n:
            pre_n -= 1
            continue
        if post_n:
            post_n -= 1
            continue
        if len(piece_list) > 1:
            piece_list = piece_list[:-1]
            continue
        return " ".join(piece_list)


def block_inputs(block: str, prev: str, nxt: str, max_words: int, max_tokens: int, count_tokens) -> list[tuple[str, str]]:
    """List of (model_input, block_piece). block_piece is the only span we keep entities from."""
    pieces = windows(block, max_words) or ([block] if (block or "").strip() else [])
    out = []
    for piece in pieces:
        # A single piece can still be over the token cap. fit_piece shrinks it.
        wrapped = fit_piece(piece, prev or "", nxt or "", max_words, max_tokens, count_tokens)
        # The piece may have been shortened to fit tokens. Keep only text that is in the model input.
        focus = piece if piece in wrapped else wrapped
        out.append((wrapped, focus))
    return out
