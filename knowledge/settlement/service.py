from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Callable

from knowledge.qa.access_logs import MemoryQaAccessLogRepository, QaAccessLogRepository
from knowledge.settlement.embeddings import TextEmbedder, HashingEmbedder, cosine, get_default_embedder
from knowledge.settlement.faqs import FaqRepository, MemoryFaqRepository
from knowledge.units.schemas import utc_now_iso

DEFAULT_MINE_THRESHOLD = 0.82
DEFAULT_CACHE_THRESHOLD = 0.88
DEFAULT_MIN_CLUSTER_SIZE = 2


class SettlementService:
    def __init__(
        self,
        faqs: FaqRepository | None = None,
        access_logs: QaAccessLogRepository | None = None,
        embedder: TextEmbedder | None = None,
        mine_threshold: float = DEFAULT_MINE_THRESHOLD,
        cache_threshold: float = DEFAULT_CACHE_THRESHOLD,
        min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
    ) -> None:
        self._faqs = faqs or MemoryFaqRepository()
        self._logs = access_logs or MemoryQaAccessLogRepository()
        self._embedder = embedder or get_default_embedder()
        self._mine_threshold = mine_threshold
        self._cache_threshold = cache_threshold
        self._min_cluster_size = min_cluster_size

    def mine_recommendations(self) -> list[dict[str, Any]]:
        entries = self._logs.list_all()
        questions: list[str] = []
        meta: list[dict[str, Any]] = []
        for entry in entries:
            question = str(entry.get("question") or "").strip()
            if not question:
                continue
            questions.append(question)
            meta.append(
                {
                    "question": question,
                    "authorized_unit_ids": list(entry.get("authorized_unit_ids") or []),
                    "answer": str(entry.get("answer") or ""),
                }
            )
        if not questions:
            return self.list_recommendations()

        vectors = self._embedder.embed(questions)
        parent = list(range(len(questions)))

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
                if cosine(vectors[i], vectors[j]) >= self._mine_threshold:
                    union(i, j)

        clusters: dict[int, list[int]] = defaultdict(list)
        for idx in range(len(questions)):
            clusters[find(idx)].append(idx)

        for members in clusters.values():
            if len(members) < self._min_cluster_size:
                continue
            member_meta = [meta[i] for i in members]
            representative = max(member_meta, key=lambda m: len(m["question"]))
            unit_ids: list[str] = []
            answers: list[str] = []
            for item in member_meta:
                for unit_id in item["authorized_unit_ids"]:
                    if unit_id and unit_id not in unit_ids:
                        unit_ids.append(unit_id)
                if item["answer"]:
                    answers.append(item["answer"])
            suggested = answers[0] if answers else ""
            digest = hashlib.sha1(representative["question"].encode("utf-8")).hexdigest()[:12]
            faq_id = f"faq-auto-{digest}"
            existing = self._faqs.get(faq_id)
            if existing and existing.get("status") in {"published", "rejected"}:
                continue
            payload = {
                "id": faq_id,
                "question": representative["question"],
                "answer": suggested,
                "category": "auto",
                "related_unit_ids": unit_ids,
                "related_unit_id": unit_ids[0] if unit_ids else "",
                "source_type": "auto_mined",
                "status": "pending_review",
                "hit_count": len(members),
                "cache_enabled": False,
                "embedding": vectors[members[0]],
                "sample_questions": [m["question"] for m in member_meta],
            }
            if existing:
                payload["answer"] = existing.get("answer") or suggested
            self._faqs.upsert(payload)

        return self.list_recommendations()

    def list_recommendations(self) -> list[dict[str, Any]]:
        return self._faqs.list(status="pending_review")

    def list_published(self) -> list[dict[str, Any]]:
        return self._faqs.list(status="published")

    def review(
        self,
        faq_id: str,
        *,
        action: str,
        edited_answer: str = "",
        reviewer_id: str = "",
    ) -> dict[str, Any]:
        faq = self._faqs.get(faq_id)
        if faq is None:
            raise KeyError(faq_id)
        if action not in {"approve", "reject"}:
            raise ValueError("action 必须是 approve 或 reject")
        patch: dict[str, Any] = {
            "reviewer_id": reviewer_id,
            "reviewed_at": utc_now_iso(),
        }
        if edited_answer.strip():
            patch["answer"] = edited_answer.strip()
        if action == "approve":
            if not (patch.get("answer") or faq.get("answer")):
                raise ValueError("审核通过需要标准答案")
            patch["status"] = "published"
            patch["cache_enabled"] = True
            patch["embedding"] = self._embedder.embed([str(faq.get("question") or "")])[0]
        else:
            patch["status"] = "rejected"
            patch["cache_enabled"] = False
        updated = self._faqs.update(faq_id, patch)
        if updated is None:
            raise KeyError(faq_id)
        return updated

    def set_cache_enabled(self, faq_id: str, enabled: bool) -> dict[str, Any]:
        faq = self._faqs.get(faq_id)
        if faq is None:
            raise KeyError(faq_id)
        if faq.get("status") != "published":
            raise ValueError("仅已发布 FAQ 可切换缓存")
        updated = self._faqs.update(faq_id, {"cache_enabled": bool(enabled)})
        if updated is None:
            raise KeyError(faq_id)
        return updated

    def match_cache(self, question: str) -> dict[str, Any] | None:
        text = question.strip()
        if not text:
            return None
        published = [
            f
            for f in self._faqs.list(status="published")
            if f.get("cache_enabled", True)
        ]
        if not published:
            return None
        for faq in published:
            if str(faq.get("question") or "").strip() == text:
                hit_count = int(faq.get("hit_count") or 0) + 1
                self._faqs.update(faq["id"], {"hit_count": hit_count})
                matched = self._faqs.get(faq["id"]) or faq
                matched = dict(matched)
                matched["match_score"] = 1.0
                return matched
        query_vec = self._embedder.embed([text])[0]
        best: dict[str, Any] | None = None
        best_score = -1.0
        for faq in published:
            emb = faq.get("embedding")
            if not emb:
                emb = self._embedder.embed([str(faq.get("question") or "")])[0]
                self._faqs.update(faq["id"], {"embedding": emb})
            score = cosine(query_vec, list(emb))
            if score > best_score:
                best_score = score
                best = faq
        if best is None or best_score < self._cache_threshold:
            return None
        hit_count = int(best.get("hit_count") or 0) + 1
        self._faqs.update(best["id"], {"hit_count": hit_count})
        matched = self._faqs.get(best["id"]) or best
        matched = dict(matched)
        matched["match_score"] = round(best_score, 4)
        return matched
