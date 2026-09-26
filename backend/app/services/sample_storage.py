"""样品留存业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "sample_storage"
REQUIRED_FIELDS = ["留存编号", "样品编号", "留存位置"]
STATUS_ORDER = ["留存中", "即将到期", "已处置", "已延期"]
ACTION_RULES = {"确认处置": "已处置", "申请延期": "已延期", "登记处置": "已处置"}
NEGATIVE_ACTIONS = []
# 列表与概览共用的字段筛选口径：查询参数 -> 数据字段，统一做包含匹配
FIELD_FILTERS = {
    "retention_no": "留存编号",
    "sample_no": "样品编号",
    "location": "留存位置",
    "period": "留存期限",
}
# 已处置视为退出留存，其余状态都算仍在留存中的样品
ACTIVE_STATUSES = [name for name in STATUS_ORDER if name != "已处置"]


class SampleStorageService:
    def _filter_rows(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        field_filters: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("留存编号", ""))]
        for param, field in FIELD_FILTERS.items():
            value = str((field_filters or {}).get(param) or "").strip()
            if value:
                rows = [row for row in rows if value in str(row.get(field, ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        field_filters: dict[str, str] | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self._filter_rows(keyword=keyword, status=status, field_filters=field_filters)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def summarize(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        field_filters: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """工作台概览：与列表走同一套筛选条件，条件一切换数字跟着变。"""
        rows = self._filter_rows(keyword=keyword, status=status, field_filters=field_filters)
        by_status = {name: 0 for name in STATUS_ORDER}
        for row in rows:
            name = str(row.get("status") or "")
            if name in by_status:
                by_status[name] += 1
        return {
            "total": len(rows),
            "active": sum(by_status[name] for name in ACTIVE_STATUSES),
            "by_status": by_status,
        }

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
