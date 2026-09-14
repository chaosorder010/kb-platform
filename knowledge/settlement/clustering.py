from __future__ import annotations

from collections import defaultdict
from typing import Callable


def cluster_indices(
    vectors: list[list[float]],
    threshold: float,
    similarity: Callable[[list[float], list[float]], float],
) -> dict[int, list[int]]:
    parent = list(range(len(vectors)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            if similarity(vectors[i], vectors[j]) >= threshold:
                union(i, j)

    clusters: dict[int, list[int]] = defaultdict(list)
    for idx in range(len(vectors)):
        clusters[find(idx)].append(idx)
    return clusters
