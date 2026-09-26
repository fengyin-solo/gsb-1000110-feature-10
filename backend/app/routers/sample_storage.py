"""样品留存接口：维护留存样品，覆盖确认处置、申请延期、登记处置等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.sample_storage import SampleStorageService

router = APIRouter(prefix="/api/sample_storage", tags=["样品留存"])

service = SampleStorageService()

LIST_FIELDS = ["留存编号", "样品编号", "留存位置", "留存期限", "到期日期", "保管人员", "处理方式", "留存状态"]
STATUSES = ["留存中", "即将到期", "已处置", "已延期"]


def _field_filters(
    retention_no: str | None,
    sample_no: str | None,
    location: str | None,
    period: str | None,
) -> dict[str, str]:
    """把查询参数收拢成服务层认识的字段筛选字典，空条件直接丢掉。"""
    candidates = {
        "retention_no": retention_no,
        "sample_no": sample_no,
        "location": location,
        "period": period,
    }
    return {key: value for key, value in candidates.items() if value}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按留存编号检索"),
    retention_no: str | None = Query(default=None, description="按留存编号模糊检索"),
    sample_no: str | None = Query(default=None, description="按样品编号模糊检索"),
    location: str | None = Query(default=None, description="按留存位置模糊检索"),
    period: str | None = Query(default=None, description="按留存期限检索"),
    status: str | None = Query(default=None, description="留存中、即将到期、已处置、已延期"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按留存编号、样品编号、留存位置、留存期限与状态过滤列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword,
        status=status,
        field_filters=_field_filters(retention_no, sample_no, location, period),
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/summary")
def summarize_entries(
    keyword: str | None = Query(default=None, description="按留存编号检索"),
    retention_no: str | None = Query(default=None, description="按留存编号模糊检索"),
    sample_no: str | None = Query(default=None, description="按样品编号模糊检索"),
    location: str | None = Query(default=None, description="按留存位置模糊检索"),
    period: str | None = Query(default=None, description="按留存期限检索"),
    status: str | None = Query(default=None, description="留存中、即将到期、已处置、已延期"),
) -> dict[str, Any]:
    """工作台概览：与列表共用同一套筛选条件，条件切换后留存中、即将到期、已处置等数字一起变。"""
    return service.summarize(
        keyword=keyword,
        status=status,
        field_filters=_field_filters(retention_no, sample_no, location, period),
    )


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出样品留存清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "sample_storage", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条留存样品明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"留存样品 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条留存样品，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="留存样品已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条留存样品执行确认处置、申请延期、登记处置；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
