from __future__ import annotations

from typing import Any

from knowledge.processor.query_processor.base import BaseNode
from knowledge.processor.query_processor.state import QueryGraphState


def _unauthorized_card(unit_id: str, title: str | None = None) -> dict[str, Any]:
    display = title or unit_id
    return {
        "unit_id": unit_id,
        "title": display,
        "message": f"无权限访问知识单元「{display}」",
    }


class AuthzFilterNode(BaseNode):
    name = "authz_filter_node"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        docs = list(state.get("reranked_docs") or [])
        unit_ids: list[str] = []
        for doc in docs:
            unit_id = doc.get("unit_id")
            if unit_id and unit_id not in unit_ids:
                unit_ids.append(unit_id)

        recalled = list(state.get("recalled_unit_ids") or [])
        for unit_id in unit_ids:
            if unit_id not in recalled:
                recalled.append(unit_id)
        state["recalled_unit_ids"] = recalled

        checker = state.get("permission_checker")
        if checker is None:
            unauthorized_units = [_unauthorized_card(unit_id) for unit_id in unit_ids]
            state["authorized_unit_ids"] = []
            state["unauthorized_unit_ids"] = list(unit_ids)
            state["unauthorized_units"] = unauthorized_units
            state["reranked_docs"] = [doc for doc in docs if not doc.get("unit_id")]
            return state

        if not unit_ids:
            state["authorized_unit_ids"] = []
            state["unauthorized_unit_ids"] = []
            state["unauthorized_units"] = []
            return state

        results = checker(unit_ids)
        auth_map = {
            item["unit_id"]: bool(item.get("authorized"))
            for item in results
            if item.get("unit_id")
        }

        authorized_docs: list[dict[str, Any]] = []
        unauthorized_units: list[dict[str, Any]] = []
        authorized_ids: list[str] = []
        unauthorized_ids: list[str] = []

        seen_unauthorized: set[str] = set()
        for doc in docs:
            unit_id = doc.get("unit_id")
            if not unit_id:
                authorized_docs.append(doc)
                continue
            if auth_map.get(unit_id, False):
                authorized_docs.append(doc)
                if unit_id not in authorized_ids:
                    authorized_ids.append(unit_id)
            else:
                if unit_id not in seen_unauthorized:
                    seen_unauthorized.add(unit_id)
                    unauthorized_ids.append(unit_id)
                    unauthorized_units.append(
                        _unauthorized_card(unit_id, doc.get("title") or unit_id)
                    )

        state["reranked_docs"] = authorized_docs
        state["authorized_unit_ids"] = authorized_ids
        state["unauthorized_unit_ids"] = unauthorized_ids
        state["unauthorized_units"] = unauthorized_units
        return state
