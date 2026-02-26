"""战略分解 Agent（支持工具化与动态调度）。

核心职责：
1) 管理 DECOMPOSE_WITH_GRAPH 工具调用；
2) 管理图工具（retrieve/validate）调用；
3) 在执行循环中基于质量信号触发重规划。
"""
from __future__ import annotations

from datetime import datetime
import json
import re

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
        self.root_task = ""
        self.unresolved_symbol_cooldown = {}
        self._pending_replan_suggestion = ""

    def _format_tool_result(self, tool: str, payload: dict, detail: dict | None = None) -> str:
        """统一工具结果展示：兼顾可读性与上下文完整性。"""
        detail_level = getattr(self.exp_config, "tool_result_detail_level", "hybrid")
        if tool == "DECOMPOSE_WITH_GRAPH":
            summary = (
                f"[TOOL] {tool} ok={payload.get('ok', False)} "
                f"subq={payload.get('subq_count', 0)}"
            )
        elif tool == "GRAPH_RETRIEVE":
            unresolved = payload.get("unresolved_symbols", []) or []
            summary = (
                f"[TOOL] {tool} grounded={payload.get('grounded', 0)} "
                f"mode={payload.get('retrieval_mode', 'unknown')} "
                f"unresolved={len(unresolved)}"
            )
        elif tool == "GRAPH_VALIDATE":
            summary = (
                f"[TOOL] {tool} coverage={payload.get('grounding_coverage', 0.0)} "
                f"exec={payload.get('executable_entry_rate', 0.0)}"
            )
        else:
            summary = f"[TOOL] {tool}"

        if detail_level == "summary" or not detail:
            return summary

        if detail_level == "full":
            return summary + "\n[TOOL_DETAIL_JSON] " + json.dumps(detail, ensure_ascii=False)

        # hybrid: 仅保留关键结构，避免长尾
        compact = dict(detail)
        if tool == "GRAPH_RETRIEVE":
            results = compact.get("results", {}) if isinstance(compact.get("results", {}), dict) else {}
            compact["results"] = {
                sym: [
                    {
                        "file": item.get("file"),
                        "line": item.get("line"),
                        "qname": item.get("qname"),
                        "type": item.get("type"),
                    }
                    for item in (items or [])[:2]
                ]
                for sym, items in list(results.items())[:6]
            }
        return summary + "\n[TOOL_DETAIL_JSON] " + json.dumps(compact, ensure_ascii=False)

    def _build_sq_dashboard(self) -> str:
        """战略状态可视化：每步输出紧凑 dashboard。"""
        subq = getattr(self.subq_manager, "sub_questions", []) or []
        if not subq:
            return "[SQ] total=0"
        total = len(subq)
        satisfied = sum(1 for x in subq if x.get("status") == "satisfied")
        blocked = sum(1 for x in subq if x.get("status") == "blocked")
        in_progress = sum(1 for x in subq if x.get("status") in {"in_progress", "open"})
        top = sorted(subq, key=lambda x: float(x.get("progress", 0.0)))[:2]
        top_ids = ",".join(f"{x.get('id','SQ?')}:{x.get('status','?')}" for x in top)
        return (
            f"[SQ] total={total} sat={satisfied} prog={in_progress} blocked={blocked} "
            f"stagnation={self.subq_manager.no_new_evidence_steps} focus={top_ids}"
        )

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

    def _handle_tool_call_command(self, command: str) -> dict:
        """通过统一命令通道触发工具：TOOL_CALL <TOOL_NAME> <JSON_ARGS>。"""
        m = re.match(r"^\s*TOOL_CALL\s+([A-Z_]+)(?:\s+(\{.*\}))?\s*$", command or "")
        if not m:
            return {"output": "Tool call parse error.", "returncode": 0}

        tool = m.group(1)
        args_raw = m.group(2)
        try:
            args = json.loads(args_raw) if args_raw else {}
        except Exception:
            return {"output": "Tool call parse error: args must be valid JSON.", "returncode": 0}

        step = max(0, (len(getattr(self, "messages", [])) - 2) // 2)

        if tool == "DECOMPOSE_WITH_GRAPH":
            task = str(args.get("task") or getattr(self, "root_task", "") or "")
            ok = self._run_decompose_tool(task, step=step, reason="manual_tool_call")
            payload = {
                "tool": tool,
                "ok": bool(ok),
                "subq_count": len(getattr(self.subq_manager, "sub_questions", []) or []),
            }
            return {"output": self._format_tool_result(tool, payload, detail=payload), "returncode": 0}

        if tool == "GRAPH_RETRIEVE":
            symbols = [str(x) for x in args.get("symbols", []) if str(x).strip()]
            result = self.tool_registry.invoke(
                step=step,
                tool_name="GRAPH_RETRIEVE",
                reason="manual_tool_call",
                fn=lambda: self.graph_tools.graph_retrieve(symbols),
                input_obj={"symbols": symbols},
            )
            unresolved = [sym for sym, items in (result.get("results", {}) or {}).items() if not items]
            if unresolved:
                for sym in unresolved:
                    self.unresolved_symbol_cooldown[sym.lower()] = step + 3
            payload = {
                "tool": tool,
                "grounded": result.get("grounded", 0),
                "retrieval_mode": result.get("retrieval_mode", "unknown"),
                "unresolved_symbols": unresolved,
            }
            return {"output": self._format_tool_result(tool, payload, detail=result), "returncode": 0}

        if tool == "GRAPH_VALIDATE":
            sub_questions = args.get("sub_questions") or (getattr(self.subq_manager, "sub_questions", []) or [])[:3]
            result = self.tool_registry.invoke(
                step=step,
                tool_name="GRAPH_VALIDATE",
                reason="manual_tool_call",
                fn=lambda: self.graph_tools.graph_validate(sub_questions),
                input_obj={"sub_question_count": len(sub_questions)},
            )
            payload = {
                "tool": tool,
                "grounding_coverage": result.get("grounding_coverage", 0.0),
                "executable_entry_rate": result.get("executable_entry_rate", 0.0),
            }
            return {"output": self._format_tool_result(tool, payload, detail=result), "returncode": 0}

        return {"output": f"Tool call blocked: unknown tool `{tool}`.", "returncode": 0}

    def run(self, task: str, repo_path: str = None):
        self.start_time = datetime.now()
        self.root_task = task or ""

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
        enhanced_task += (
            "\n\nTOOL CALL PROTOCOL (UNIFIED):"
            "\n- In bash block, use: TOOL_CALL <TOOL_NAME> <JSON_ARGS>."
            "\n- Tools: DECOMPOSE_WITH_GRAPH / GRAPH_RETRIEVE / GRAPH_VALIDATE."
            "\n- Example: TOOL_CALL GRAPH_RETRIEVE {\"symbols\":[\"parse_action\"]}."
            "\n- Use TOOL_CALL when you need planning/graph context; use rg/nl/sed for code reading."
        )


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

    def _maybe_trigger_redecompose(self, task_hint: str, step: int, extra_reasons: list[str] | None = None):
        """基于质量信号尝试触发重分解。

        触发条件：来自 subquestion manager 的 replan 事件，且配置允许。
        """
        if not self.exp_config.enable_dynamic_redecompose:
            return
        if step < 2:
            return
        if len(self.subq_manager.replan_events) == 0 and not extra_reasons:
            return

        reasons = list(extra_reasons or [])
        if len(self.subq_manager.replan_events) > 0:
            latest = self.subq_manager.replan_events[-1]
            reasons.extend(latest.get("reasons", []))
        reasons = [r for r in reasons if r]
        if not reasons:
            return

        if any(r in {"high_priority_stagnation", "decomposition_quality_drop", "no_new_evidence_for_3_steps", "relation_metric_imbalance"} for r in reasons):
            logger.info(f"🔁 Dynamic redecompose triggered at step={step}, reasons={reasons}")
            focused_hint = (
                "[REPLAN FOCUS] Keep decomposition strictly aligned with the original user question. "
                "Ignore unrelated file names or modules unless they directly explain the asked issue.\n"
                f"[ORIGINAL QUESTION] {task_hint}"
            )
            self._run_decompose_tool(focused_hint, step=step, reason="replan")

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
            task_hint = getattr(self, "root_task", "") or (self.messages[1]["content"] if len(self.messages) > 1 else "")
            if self._run_decompose_tool(task_hint, step=step, reason="lazy_bootstrap"):
                logger.info("🧠 Lazy DECOMPOSE_WITH_GRAPH triggered from agent action.")

    def _fallback_symbols_from_task(self, limit: int = 5) -> list[str]:
        """补偿方案 C：当 subq 尚未初始化时，从问题文本抽取轻量 symbols 供图检索。"""
        task = getattr(self, "root_task", "") or (self.messages[1]["content"] if len(getattr(self, "messages", [])) > 1 else "")
        cands = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b|\b[a-z_]{4,}\b", task)
        stop = {"with", "from", "that", "this", "what", "where", "when", "which", "about", "should"}
        filtered = []
        for c in cands:
            cl = c.lower()
            if cl in stop:
                continue
            if c not in filtered:
                filtered.append(c)
            if len(filtered) >= limit:
                break
        return filtered

    def _build_graph_action_hints(self, retrieve: dict, max_hints: int = 3) -> list[str]:
        """把图检索结果转成可直接执行的候选动作模板。"""
        hints = []
        results = retrieve.get("results", {}) if isinstance(retrieve, dict) else {}
        for symbol, items in results.items():
            if not isinstance(items, list):
                continue
            for item in items[:2]:
                file_path = item.get("file")
                line = item.get("line")
                qname = item.get("qname") or item.get("name") or symbol
                if not file_path:
                    continue
                hints.append(
                    f"rg -n \"{symbol}\" {file_path}  # anchor {qname}"
                )
                if line:
                    start = max(1, int(line) - 20)
                    end = int(line) + 40
                    hints.append(f"nl -ba {file_path} | sed -n '{start},{end}p'")
                if len(hints) >= max_hints:
                    return hints[:max_hints]
        return hints[:max_hints]

    def _relation_replan_needed(self) -> bool:
        """把 relation 指标纳入重分解判断（第4点落地）。"""
        if not self.decomposition_quality:
            return False
        relation = self.decomposition_quality.get("relation", {}) if isinstance(self.decomposition_quality, dict) else {}
        overlap_balance = float(relation.get("overlap_balance", 1.0))
        completeness_proxy = float(relation.get("completeness_proxy", 1.0))
        # 关系结构失衡 + 证据停滞时触发
        return (overlap_balance < 0.45 or completeness_proxy < 0.55) and self.subq_manager.no_new_evidence_steps >= 2

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
                if not symbols:
                    symbols = self._fallback_symbols_from_task(limit=5)

                # unresolved symbol cooldown：短期内避免反复检索同一无效符号
                symbols = [
                    sym for sym in symbols
                    if self.unresolved_symbol_cooldown.get(sym.lower(), -1) < step
                ]
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
                    unresolved_symbols = [
                        sym for sym, items in (retrieve.get("results", {}) or {}).items() if not items
                    ]
                    if unresolved_symbols:
                        for sym in unresolved_symbols:
                            self.unresolved_symbol_cooldown[sym.lower()] = step + 3

                    graph_hint = (
                        f"[GRAPH TOOL] grounded={retrieve.get('grounded', 0)} "
                        f"coverage={validate.get('grounding_coverage', 0.0)} "
                        f"exec={validate.get('executable_entry_rate', 0.0)}"
                    )
                    if unresolved_symbols:
                        graph_hint += "\n[UNRESOLVED_SYMBOLS] " + ", ".join(unresolved_symbols)
                    action_hints = self._build_graph_action_hints(retrieve)
                    if action_hints:
                        graph_hint += "\n[GRAPH NEXT ACTIONS]\n- " + "\n- ".join(action_hints)
                    obs_dict["observation"] += "\n" + graph_hint
                    obs_dict["output"] = obs_dict["observation"]

            self.subq_manager.update(
                step=step,
                action=obs_dict.get("action", ""),
                observation=obs_dict.get("observation", ""),
                graph_hint=graph_hint,
            )
            manager_replan = self.subq_manager.check_replan_needed(step)
            relation_replan = self._relation_replan_needed()
            if manager_replan or relation_replan:
                reasons = []
                if manager_replan and self.subq_manager.replan_events:
                    reasons.extend(self.subq_manager.replan_events[-1].get("reasons", []))
                if relation_replan:
                    reasons.append("relation_metric_imbalance")
                obs_dict["observation"] += (
                    "\n\n⚠️ [REPLAN SIGNAL] Quality indicates replanning is needed. "
                    f"Reasons={sorted(set(reasons))}."
                )
                obs_dict["output"] = obs_dict["observation"]
                task_hint = getattr(self, "root_task", "") or (self.messages[1]["content"] if len(self.messages) > 1 else "")
                payload = json.dumps({"task": task_hint}, ensure_ascii=False)
                self._pending_replan_suggestion = f"TOOL_CALL DECOMPOSE_WITH_GRAPH {payload}"
                obs_dict["observation"] += "\n[REPLAN ACTION] " + self._pending_replan_suggestion
                obs_dict["output"] = obs_dict["observation"]

            dashboard = self._build_sq_dashboard()
            obs_dict["observation"] += "\n" + dashboard
            obs_dict["output"] = obs_dict["observation"]
            logger.info("   " + dashboard)

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
