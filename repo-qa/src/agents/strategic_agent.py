"""战略分解 Agent（支持工具化与动态调度）。

核心职责：
1) 管理 DECOMPOSE_WITH_GRAPH 工具调用；
2) 管理图工具（retrieve/validate）调用；
3) 在执行循环中基于质量信号触发重规划。
"""
from __future__ import annotations

from datetime import datetime

from src.agents.base import BaseRepoQAAgent
from src.decomposer import StrategicDecomposer
from src.decomposition_action import DecompositionAction
from src.graph import CodeGraph
from src.graph_tools import GraphTools
from src.injectors import GraphInjector
from src.subquestion_manager import SubQuestionManager
from src.tool_registry import ToolRegistry
from src.utils import build_task_prompt, setup_logger

logger = setup_logger(__name__)


class StrategicRepoQAAgent(BaseRepoQAAgent):
    """带可选分解工具与图工具的 Agent。

    输入：模型、环境、实验配置。
    输出：最终答案文本 + 完整轨迹（由基类保存）。
    """

    def __init__(self, model, env, config, **kwargs):
        super().__init__(model, env, config, **kwargs)
        self.code_graph = None
        self.decomposer = None
        self.injector = None
        self.graph_tools = None
        self.graph_tool_calls = 0
        self.decompose_tool_calls = 0

        # P0/P1：统一工具调用追踪
        self.tool_registry = ToolRegistry()

        self.subq_manager = SubQuestionManager()
        self.decomposition = None
        self.decomposition_quality = None
        self.decomposition_workflow_trace = []

    def _run_decompose_tool(self, task: str, step: int = 0, reason: str = "initial") -> bool:
        """调用 DECOMPOSE_WITH_GRAPH 工具。

        Args:
            task: 当前问题文本（首次运行或重规划时使用）。
            step: 当前步数（用于工具调用记录）。
            reason: 调用原因（initial/lazy_bootstrap/replan）。
        Returns:
            bool: 是否成功执行了一次分解调用。
        """
        if not self.exp_config.enable_decomposition_tool:
            return False
        if self.decompose_tool_calls >= self.exp_config.max_decompose_calls:
            return False

        self.graph_tools = GraphTools(self.code_graph)
        self.decomposer = StrategicDecomposer(self.model, self.code_graph)
        decompose_action = DecompositionAction(self.decomposer)

        action_result = self.tool_registry.invoke(
            step=step,
            tool_name="DECOMPOSE_WITH_GRAPH",
            reason=reason,
            fn=lambda: decompose_action.execute(task),
            input_obj={"task": task[:300]},
        )

        decomposition = action_result.decomposition
        self.decomposition = decomposition
        self.decomposition_quality = action_result.quality
        self.decomposition_workflow_trace.extend(action_result.workflow_trace)
        self.subq_manager.initialize(decomposition)
        self.decompose_tool_calls += 1
        return True

    def run(self, task: str, repo_path: str = None):
        self.start_time = datetime.now()

        if self.exp_config.enable_graph and repo_path:
            self.code_graph = CodeGraph()
            self.code_graph.build(repo_path)

            if self.exp_config.enable_graph_injection:
                self.injector = GraphInjector(self.code_graph, enabled=True)

        # Graph tool wrapper is always available, but may be disabled by config.
        self.graph_tools = GraphTools(self.code_graph)

        # Optional start-time decomposition; can be disabled for tool-on-demand behavior.
        if self.exp_config.decompose_on_start:
            self._run_decompose_tool(task, step=0, reason="initial")

        enhanced_task = build_task_prompt(task, repo_path, self.decomposition, self.exp_config)

        try:
            _, message = super().run(enhanced_task)
            return message
        finally:
            self.end_time = datetime.now()
            self._save_trajectory()
            self._print_final_report()

    def _should_call_graph_tool(self, action: str, step: int) -> bool:
        """判断当前步骤是否应调用图工具。

        策略：
        - 静态开关优先；
        - 命中检索型 action 时优先调用；
        - 否则在证据停滞时按阈值触发。
        """
        if not self.exp_config.enable_graph_tools:
            return False
        if not self.graph_tools:
            return False

        action_l = (action or "").lower()
        has_lookup_intent = any(k in action_l for k in ["rg ", "grep", "cat ", "nl -ba", "sed -n", "class ", "def "])

        if not self.exp_config.enable_dynamic_graph_tool_calls:
            return bool(has_lookup_intent)

        if has_lookup_intent:
            return True

        # Dynamic fallback: call graph tools when evidence is stagnant.
        return self.subq_manager.no_new_evidence_steps >= self.exp_config.graph_tool_stagnation_steps and step % 2 == 0

    def _maybe_trigger_redecompose(self, task_hint: str, step: int):
        """基于质量信号尝试触发重分解。

        触发条件：来自 subquestion manager 的 replan 事件，且配置允许。
        """
        if not self.exp_config.enable_dynamic_redecompose:
            return
        if step < 2:
            return
        if len(self.subq_manager.replan_events) == 0:
            return

        latest = self.subq_manager.replan_events[-1]
        reasons = latest.get("reasons", [])
        if not reasons:
            return

        if any(r in {"high_priority_stagnation", "decomposition_quality_drop", "no_new_evidence_for_3_steps"} for r in reasons):
            logger.info(f"🔁 Dynamic redecompose triggered at step={step}, reasons={reasons}")
            self._run_decompose_tool(task_hint, step=step, reason="replan")

    def _maybe_bootstrap_decompose_from_action(self, action: str, step: int):
        """懒加载分解：当未开局分解时，从探索动作中触发。

        说明：
        - 仅在未初始化分解、且配置允许时执行；
        - 这是“分解是工具而非必选步骤”的工程落地。
        """
        if self.decomposition is not None:
            return
        if not self.exp_config.enable_decomposition_tool:
            return
        if self.exp_config.decompose_on_start:
            return

        action_l = (action or "").lower()
        # 避免“全库脚本化扫描”污染分解上下文：仅在轻量、可解释的检索动作上懒触发分解
        broad_scan_markers = ["while ", "for ", "xargs", "&& find ", "|", ";"]
        if any(m in action_l for m in broad_scan_markers):
            return

        should_bootstrap = any(k in action_l for k in ["rg ", "grep", "cat ", "nl -ba", "sed -n"])
        if should_bootstrap and step >= 0:
            task_hint = self.messages[1]["content"] if len(self.messages) > 1 else ""
            if self._run_decompose_tool(task_hint, step=step, reason="lazy_bootstrap"):
                logger.info("🧠 Lazy DECOMPOSE_WITH_GRAPH triggered from agent action.")

    def get_observation(self, response: dict) -> dict:
        """处理 observation 并执行动态工具调用。

        输入：基类返回的 observation 字典。
        输出：增强后的 observation（可能追加 GRAPH TOOL / REPLAN 信息）。
        """
        obs_dict = super().get_observation(response)

        if self.injector and "action" in obs_dict:
            raw_output = obs_dict.get("observation", "")
            obs_dict["observation"] = self.injector.inject(obs_dict["action"], raw_output)
            obs_dict["output"] = obs_dict["observation"]

        if "action" in obs_dict:
            step = max(0, (len(getattr(self, "messages", [])) - 2) // 2)
            action = obs_dict.get("action", "")
            self._maybe_bootstrap_decompose_from_action(action, step)

            # 提交指令（含被拦截场景）不参与子问题推进与重规划计数，避免死循环噪声
            if self._is_submit_signal(action):
                return obs_dict

            graph_hint = ""
            if self._should_call_graph_tool(obs_dict.get("action", ""), step):
                open_subq = [sq for sq in self.subq_manager.sub_questions if sq.get("status") != "satisfied"]
                symbols = []
                for sq in open_subq[:2]:
                    symbols.extend([s for s in sq.get("symbols", []) if isinstance(s, str)])
                symbols = list(dict.fromkeys(symbols))[:5]
                if symbols:
                    retrieve = self.tool_registry.invoke(
                        step=step,
                        tool_name="GRAPH_RETRIEVE",
                        reason="graph_lookup",
                        fn=lambda: self.graph_tools.graph_retrieve(symbols),
                        input_obj={"symbols": symbols},
                    )
                    validate = self.tool_registry.invoke(
                        step=step,
                        tool_name="GRAPH_VALIDATE",
                        reason="graph_lookup",
                        fn=lambda: self.graph_tools.graph_validate(open_subq[:3]),
                        input_obj={"sub_question_count": len(open_subq[:3])},
                    )
                    self.graph_tool_calls += 1
                    graph_hint = (
                        f"[GRAPH TOOL] grounded={retrieve.get('grounded', 0)} "
                        f"coverage={validate.get('grounding_coverage', 0.0)} "
                        f"exec={validate.get('executable_entry_rate', 0.0)}"
                    )
                    obs_dict["observation"] += "\n" + graph_hint
                    obs_dict["output"] = obs_dict["observation"]

            self.subq_manager.update(
                step=step,
                action=obs_dict.get("action", ""),
                observation=obs_dict.get("observation", ""),
                graph_hint=graph_hint,
            )
            if self.subq_manager.check_replan_needed(step):
                obs_dict["observation"] += (
                    "\n\n⚠️ [REPLAN SIGNAL] Quality indicates replanning is needed. "
                    "Refocus on unresolved symbols or switch entry candidates."
                )
                obs_dict["output"] = obs_dict["observation"]
                task_hint = self.messages[1]["content"] if len(self.messages) > 1 else ""
                self._maybe_trigger_redecompose(task_hint, step)

        return obs_dict

    def _get_stats(self) -> dict:
        stats = super()._get_stats()
        if self.injector:
            stats["total_injections"] = self.injector.injection_count
        stats["graph_tool_calls"] = self.graph_tool_calls
        stats["decompose_tool_calls"] = self.decompose_tool_calls

        # P0/P1：统一输出各工具调用次数
        stats["tool_call_counters"] = self.tool_registry.get_counters()

        if self.subq_manager.sub_questions:
            stats["sub_questions_total"] = len(self.subq_manager.sub_questions)
            stats["sub_questions_satisfied"] = sum(
                1 for sq in self.subq_manager.sub_questions if sq.get("status") == "satisfied"
            )
            stats["replan_events"] = len(self.subq_manager.replan_events)

        if self.decomposition_quality:
            stats["decomposition_quality"] = self.decomposition_quality.get("overall", 0.0)

        return stats
