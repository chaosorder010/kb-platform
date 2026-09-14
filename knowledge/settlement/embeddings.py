from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Protocol


class TextEmbedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


_TOKEN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", re.UNICODE)


def tokenize(text: str) -> list[str]:
    parts = _TOKEN.findall(text.lower())
    tokens = list(parts)
    cjk = [p for p in parts if "\u4e00" <= p <= "\u9fff"]
    for i in range(len(cjk) - 1):
        tokens.append(cjk[i] + cjk[i + 1])
    return tokens


def _stable_index(token: str, dims: int) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % dims


class HashingEmbedder:
    def __init__(self, dims: int = 128) -> None:
        self._dims = dims

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            counts = Counter(tokenize(text))
            vec = [0.0] * self._dims
            for token, freq in counts.items():
                idx = _stable_index(token, self._dims)
                vec[idx] += float(freq)
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def get_default_embedder() -> TextEmbedder:
    try:
        from knowledge.utils.client.ai_clients import AIClients

        model = AIClients.get_bge_m3_client()

        class BgeEmbedder:
            def embed(self, texts: list[str]) -> list[list[float]]:
                result = model.encode_documents(texts)
                dense = result["dense"]
                return [list(map(float, row)) for row in dense]

        return BgeEmbedder()
    except Exception:
        return HashingEmbedder()
