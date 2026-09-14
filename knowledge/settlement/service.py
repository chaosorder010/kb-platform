from __future__ import annotations

import hashlib
from typing import Any

from knowledge.qa.access_logs import MemoryQaAccessLogRepository, QaAccessLogRepository
from knowledge.settlement.clustering import cluster_indices
from knowledge.settlement.embeddings import TextEmbedder, HashingEmbedder, cosine, get_default_embedder
from knowledge.settlement.faqs import FaqRepository, MemoryFaqRepository
from knowledge.settlement.gaps import GapRepository, MemoryGapRepository
from knowledge.units.schemas import utc_now_iso
from knowledge.units.service import KnowledgeService

DEFAULT_MINE_THRESHOLD = 0.82
DEFAULT_CACHE_THRESHOLD = 0.88
DEFAULT_GAP_RECALL_THRESHOLD = 0.45
DEFAULT_MIN_CLUSTER_SIZE = 2


class SettlementService:
    def __init__(
        self,
        faqs: FaqRepository | None = None,
        gaps: GapRepository | None = None,
        access_logs: QaAccessLogRepository | None = None,
        embedder: TextEmbedder | None = None,
        knowledge_service: KnowledgeService | None = None,
        mine_threshold: float = DEFAULT_MINE_THRESHOLD,
        cache_threshold: float = DEFAULT_CACHE_THRESHOLD,
        gap_recall_threshold: float = DEFAULT_GAP_RECALL_THRESHOLD,
        min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
    ) -> None:
        self._faqs = faqs or MemoryFaqRepository()
        self._gaps = gaps or MemoryGapRepository()
        self._logs = access_logs or MemoryQaAccessLogRepository()
        self._embedder = embedder or get_default_embedder()
        self._knowledge = knowledge_service
        self._mine_threshold = mine_threshold
        self._cache_threshold = cache_threshold
        self._gap_recall_threshold = gap_recall_threshold
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
        clusters = cluster_indices(vectors, self._mine_threshold, cosine)

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


    def _is_gap_entry(self, entry: dict[str, Any]) -> bool:
        if entry.get("faq_cache_hit"):
            return False
        if list(entry.get("authorized_unit_ids") or []):
            return False
        recalled = list(entry.get("recalled_unit_ids") or [])
        max_score = entry.get("max_recall_score")
        if max_score is not None:
            return float(max_score) < self._gap_recall_threshold
        return not recalled

    def mine_knowledge_gaps(self) -> list[dict[str, Any]]:
        entries = [e for e in self._logs.list_all() if self._is_gap_entry(e)]
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
                    "created_at": entry.get("created_at") or utc_now_iso(),
                }
            )
        if not questions:
            return self.list_knowledge_gaps()

        vectors = self._embedder.embed(questions)
        clusters = cluster_indices(vectors, self._mine_threshold, cosine)

        for members in clusters.values():
            member_meta = [meta[i] for i in members]
            samples = []
            for item in member_meta:
                if item["question"] not in samples:
                    samples.append(item["question"])
            pattern = max(samples, key=len)
            digest = hashlib.sha1(pattern.encode("utf-8")).hexdigest()[:12]
            gap_id = f"gap-auto-{digest}"
            existing = self._gaps.get(gap_id)
            if existing and existing.get("status") in {"resolved", "ignored"}:
                continue
            last_asked = max(item["created_at"] for item in member_meta)
            payload = {
                "id": gap_id,
                "question_pattern": pattern,
                "sample_questions": samples,
                "ask_count": len(members),
                "last_asked_at": last_asked,
                "status": (existing or {}).get("status") or "unresolved",
                "resolved_unit_id": (existing or {}).get("resolved_unit_id") or "",
                "embedding": vectors[members[0]],
            }
            self._gaps.upsert(payload)

        return self.list_knowledge_gaps()

    def list_knowledge_gaps(self, status: str | None = None) -> list[dict[str, Any]]:
        return self._gaps.list(status=status)

    def update_gap_status(self, gap_id: str, status_value: str) -> dict[str, Any]:
        if status_value not in {"unresolved", "resolved", "ignored"}:
            raise ValueError("status 必须是 unresolved / resolved / ignored")
        updated = self._gaps.update(gap_id, {"status": status_value})
        if updated is None:
            raise KeyError(gap_id)
        return updated

    def create_unit_from_gap(
        self,
        gap_id: str,
        *,
        creator_id: str,
        creator_name: str,
        title: str = "",
        content: str = "",
    ) -> dict[str, Any]:
        gap = self._gaps.get(gap_id)
        if gap is None:
            raise KeyError(gap_id)
        if self._knowledge is None:
            raise RuntimeError("未配置知识服务，无法建档")
        samples = list(gap.get("sample_questions") or [])
        unit_title = title.strip() or str(
            gap.get("question_pattern") or "知识缺口补全"
        )
        body = content.strip() or "\n".join(
            [
                "# 知识缺口补全",
                "",
                f"模式：{gap.get('question_pattern')}",
                "",
                "## 样例问法",
                *[f"- {s}" for s in samples],
            ]
        )
        created = self._knowledge.create_draft_unit(
            title=unit_title,
            content=body,
            creator_id=creator_id,
            creator_name=creator_name,
            category="knowledge-gap",
            tags=["knowledge-gap"],
            summary=f"由知识缺口「{gap.get('question_pattern')}」一键建档",
        )
        updated = self._gaps.update(
            gap_id,
            {
                "status": "resolved",
                "resolved_unit_id": created.get("id") or "",
            },
        )
        return {"gap": updated, "unit": created}

