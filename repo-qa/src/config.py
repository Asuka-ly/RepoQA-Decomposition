"""实验配置管理模块。

设计目标（最小侵入）：
1. 所有行为开关统一收敛到 `ExperimentConfig`，避免脚本/Agent 各自维护布尔值；
2. 配置支持 YAML 双向读写，便于实验复现与协作交接；
3. 新增字段保持向后兼容（旧 YAML 缺字段时自动使用默认值）。
"""
from dataclasses import asdict, dataclass
from typing import Optional

import yaml


@dataclass
class ExperimentConfig:
    """实验配置对象。

输入：
    - 来自 `configs/*.yaml` 的键值对。
输出：
    - 供 Agent / Runner / Prompt 构建阶段读取的统一配置对象。

说明：
    - 字段以“开关 + 参数 + 元信息”组织，便于在线实验做消融；
    - 所有字段都带默认值，保障旧配置可直接运行。
    """

    # Core switches
    enable_graph: bool = True
    enable_graph_injection: bool = True
    enable_command_filter: bool = True
    enable_pattern_detection: bool = False

    # Tool orchestration switches (Stage1 v2.2+)
    enable_decomposition_tool: bool = True
    decompose_on_start: bool = True
    enable_dynamic_redecompose: bool = True
    max_decompose_calls: int = 2
    enable_graph_tools: bool = True
    enable_dynamic_graph_tool_calls: bool = True
    graph_tool_stagnation_steps: int = 2

    # Compensation switches (stability before refactor)
    enable_scan_compensation: bool = True
    early_exploration_budget_steps: int = 2
    allow_broad_scan_after_stagnation: int = 3


    # Submit gate (stability)
    min_submit_total_evidence: int = 2
    min_submit_assistant_evidence: int = 2
    min_submit_steps: int = 4

    # Model
    model_name: str = "gpt-5-mini"
    model_api_base: Optional[str] = None

    # Params
    injection_min_length: int = 6
    max_steps: int = 50

    # Metadata
    name: str = "default"
    description: str = ""

    @classmethod
    def from_yaml(cls, path: str) -> "ExperimentConfig":
        """从 YAML 文件加载实验配置。

        Args:
            path: YAML 文件路径。
        Returns:
            ExperimentConfig: 解析后的配置对象。
        """
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**(data or {}))

    @classmethod
    def from_dict(cls, data: dict) -> "ExperimentConfig":
        """从字典构建配置对象（常用于测试）。"""
        return cls(**data)

    def to_yaml(self, path: str):
        """将当前配置写回 YAML 文件。"""
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(asdict(self), f, indent=2, sort_keys=False)

    def to_dict(self) -> dict:
        """导出为字典（用于轨迹写盘与调试输出）。"""
        return asdict(self)

    def __str__(self) -> str:
        return (
            f"Config: {self.name}\n"
            f"  Graph: {'✅' if self.enable_graph else '❌'}\n"
            f"  Graph Injection: {'✅' if self.enable_graph_injection else '❌'}\n"
            f"  Graph Tools: {'✅' if self.enable_graph_tools else '❌'}\n"
            f"  Decompose Tool: {'✅' if self.enable_decomposition_tool else '❌'}\n"
            f"  Decompose On Start: {'✅' if self.decompose_on_start else '❌'}\n"
            f"  Dynamic Re-decompose: {'✅' if self.enable_dynamic_redecompose else '❌'}\n"
            f"  Command Filter: {'✅' if self.enable_command_filter else '❌'}\n"
            f"  Max Steps: {self.max_steps}"
        )
