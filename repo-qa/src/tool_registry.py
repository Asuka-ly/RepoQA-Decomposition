"""工具注册与调用追踪（轻量版，P0/P1）。

设计目标（最小侵入）：
1) 不改变原有工具实现，仅在调用外层增加统一记录；
2) 记录调用时机、输入摘要、输出摘要、耗时、成功状态；
3) 为 trajectory schema v2 提供 `tool_calls` 数据来源。
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from time import perf_counter
from typing import Any, Dict, List


@dataclass
class ToolCallRecord:
    """单次工具调用记录。"""

    step: int
    tool_name: str
    reason: str
    success: bool
    latency_ms: float
    input_summary: Dict[str, Any]
    output_summary: Dict[str, Any]
    error: str | None
    timestamp: str


class ToolRegistry:
    """轻量工具注册中心。

    说明：
    - 当前只负责“记录调用”，不强制改写工具接口；
    - 对输出做摘要，避免轨迹过大。
    """

    def __init__(self):
        self._calls: List[ToolCallRecord] = []

    def _summarize(self, value: Any, max_items: int = 5) -> Dict[str, Any]:
        """把任意输入/输出压缩成可写盘摘要。"""
        if isinstance(value, dict):
            keys = list(value.keys())[:max_items]
            return {
                "type": "dict",
                "keys": keys,
                "size": len(value),
            }
        if isinstance(value, list):
            return {
                "type": "list",
                "size": len(value),
                "preview": value[:max_items],
            }
        return {
            "type": type(value).__name__,
            "repr": str(value)[:200],
        }

    def record_tool_call(
        self,
        *,
        step: int,
        tool_name: str,
        reason: str,
        success: bool,
        latency_ms: float,
        input_obj: Any,
        output_obj: Any,
        error: str | None = None,
    ):
        self._calls.append(
            ToolCallRecord(
                step=step,
                tool_name=tool_name,
                reason=reason,
                success=success,
                latency_ms=round(latency_ms, 3),
                input_summary=self._summarize(input_obj),
                output_summary=self._summarize(output_obj),
                error=error,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )
        )

    def invoke(self, *, step: int, tool_name: str, reason: str, fn, input_obj: Any):
        """统一调用封装：执行函数并自动记录。"""
        start = perf_counter()
        try:
            out = fn()
            self.record_tool_call(
                step=step,
                tool_name=tool_name,
                reason=reason,
                success=True,
                latency_ms=(perf_counter() - start) * 1000,
                input_obj=input_obj,
                output_obj=out,
                error=None,
            )
            return out
        except Exception as exc:
            self.record_tool_call(
                step=step,
                tool_name=tool_name,
                reason=reason,
                success=False,
                latency_ms=(perf_counter() - start) * 1000,
                input_obj=input_obj,
                output_obj={},
                error=str(exc),
            )
            raise

    def get_calls(self) -> List[Dict[str, Any]]:
        return [asdict(x) for x in self._calls]

    def get_counters(self) -> Dict[str, int]:
        counters: Dict[str, int] = {}
        for call in self._calls:
            counters[call.tool_name] = counters.get(call.tool_name, 0) + 1
        return counters
