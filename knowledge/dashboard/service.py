from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from knowledge.qa.access_logs import MemoryQaAccessLogRepository, QaAccessLogRepository


def _parse_created_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _bucket_key(dt: datetime, granularity: str) -> str:
    if granularity == "week":
        iso = dt.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return dt.strftime("%Y-%m-%d")


class DashboardService:
    def __init__(
        self,
        access_logs: QaAccessLogRepository | None = None,
        unit_counter: Callable[[], int] | None = None,
        unit_title_lookup: Callable[[str], str] | None = None,
    ) -> None:
        self._logs = access_logs or MemoryQaAccessLogRepository()
        self._unit_counter = unit_counter or (lambda: 0)
        self._unit_title_lookup = unit_title_lookup or (lambda unit_id: unit_id)

    def metrics(self) -> dict[str, Any]:
        entries = self._logs.list_all()
        visit_count = len(entries)
        uv = len({e.get("user_id") for e in entries if e.get("user_id")})
        total_tokens = sum(int(e.get("total_tokens") or 0) for e in entries)
        if visit_count:
            avg_ms = sum(int(e.get("response_time_ms") or 0) for e in entries) / visit_count
        else:
            avg_ms = 0.0
        return {
            "visit_count": visit_count,
            "uv": uv,
            "knowledge_unit_count": int(self._unit_counter()),
            "total_tokens": total_tokens,
            "avg_response_time_ms": round(avg_ms, 2),
        }

    def top_questions(self, limit: int = 10) -> list[dict[str, Any]]:
        counter: Counter[str] = Counter()
        for entry in self._logs.list_all():
            question = str(entry.get("question") or "").strip()
            if question:
                counter[question] += 1
        return [
            {"question": question, "count": count}
            for question, count in counter.most_common(max(1, limit))
        ]

    def top_units(self, limit: int = 10) -> list[dict[str, Any]]:
        counter: Counter[str] = Counter()
        for entry in self._logs.list_all():
            for unit_id in entry.get("authorized_unit_ids") or []:
                if unit_id:
                    counter[str(unit_id)] += 1
        return [
            {
                "unit_id": unit_id,
                "title": self._unit_title_lookup(unit_id),
                "count": count,
            }
            for unit_id, count in counter.most_common(max(1, limit))
        ]

    def token_stats(self, granularity: str = "day") -> dict[str, Any]:
        gran = "week" if granularity == "week" else "day"
        entries = self._logs.list_all()
        trend_map: dict[str, dict[str, float]] = defaultdict(
            lambda: {"visit_count": 0, "total_tokens": 0, "response_time_ms_sum": 0}
        )
        latency_values: list[int] = []
        for entry in entries:
            dt = _parse_created_at(entry.get("created_at")) or datetime.now(timezone.utc)
            key = _bucket_key(dt, gran)
            bucket = trend_map[key]
            bucket["visit_count"] += 1
            bucket["total_tokens"] += int(entry.get("total_tokens") or 0)
            latency = int(entry.get("response_time_ms") or 0)
            bucket["response_time_ms_sum"] += latency
            latency_values.append(latency)

        trend = []
        for key in sorted(trend_map):
            bucket = trend_map[key]
            visits = int(bucket["visit_count"])
            trend.append(
                {
                    "bucket": key,
                    "visit_count": visits,
                    "total_tokens": int(bucket["total_tokens"]),
                    "avg_response_time_ms": round(
                        bucket["response_time_ms_sum"] / visits, 2
                    )
                    if visits
                    else 0.0,
                }
            )

        edges = [0, 200, 500, 1000, 2000, 5000]
        labels = ["0-200", "200-500", "500-1000", "1000-2000", "2000-5000", "5000+"]
        dist = [0] * len(labels)
        for value in latency_values:
            placed = False
            for i in range(len(edges) - 1):
                if edges[i] <= value < edges[i + 1]:
                    dist[i] += 1
                    placed = True
                    break
            if not placed:
                dist[-1] += 1

        return {
            "granularity": gran,
            "trend": trend,
            "response_time_distribution": [
                {"bucket": labels[i], "count": dist[i]} for i in range(len(labels))
            ],
        }
