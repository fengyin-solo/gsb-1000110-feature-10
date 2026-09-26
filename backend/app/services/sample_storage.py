"""样品留存业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "sample_storage"
REQUIRED_FIELDS = ["留存编号", "样品编号", "留存位置"]
STATUS_ORDER = ["留存中", "即将到期", "已处置", "已延期"]
ACTION_RULES = {"确认处置": "已处置", "申请延期": "已延期", "登记处置": "已处置"}
NEGATIVE_ACTIONS = []


class SampleStorageService:
    def _filter(
        self,
        *,
        keyword: str | None = None,
        sample_no: str | None = None,
        location: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("留存编号", ""))]
        if sample_no:
            rows = [row for row in rows if sample_no in str(row.get("样品编号", ""))]
        if location:
            rows = [row for row in rows if location in str(row.get("留存位置", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        sample_no: str | None = None,
        location: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self._filter(keyword=keyword, sample_no=sample_no, location=location, status=status)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def summarize(
        self,
        *,
        keyword: str | None = None,
        sample_no: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        """概览口径：跟随当前检索条件，但不含状态筛选，保证各状态卡片分布完整。"""
        rows = self._filter(keyword=keyword, sample_no=sample_no, location=location)
        counts = {status: 0 for status in STATUS_ORDER}
        for row in rows:
            status = str(row.get("status") or "")
            if status in counts:
                counts[status] += 1
        return {"total": len(rows), "counts": counts}

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"留存样品 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于样品留存可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"留存样品已{action}"
