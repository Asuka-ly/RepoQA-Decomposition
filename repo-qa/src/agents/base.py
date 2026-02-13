"""RepoQA 基础 Agent - 提取公共逻辑"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from minisweagent.agents.default import DefaultAgent
from src.config import ExperimentConfig
from src.filters import CommandFilter
from src.utils import setup_logger

logger = setup_logger(__name__)


class TaskCompletedException(Exception):
    """任务完成异常 - 用于优雅退出循环"""

    def __init__(self, final_answer: str = ""):
        self.final_answer = final_answer
        super().__init__("Task completed by agent")


class BaseRepoQAAgent(DefaultAgent):
    """基础 Agent，只包含环境劫持和统计逻辑"""

    def __init__(self, model, env, config: ExperimentConfig, **kwargs):
        super().__init__(model, env, **kwargs)
        self.exp_config = config
        self.cmd_filter = CommandFilter(enabled=config.enable_command_filter)

        # 任务完成标志
        self._task_completed = False
        self._final_answer = None

        # 统计变量
        self.viewed_files = set()
        self.start_time = None
        self.end_time = None

        # 环境劫持
        logger.info("🔧 Installing command filter via env.execute hijacking...")
        original_execute = env.execute

        def filtered_execute(command: str, cwd: str = "", *, timeout: int | None = None):
            logger.info(f"🛡️  FILTER CHECK: {command}")

            # 检测提交信号
            if self._is_submit_signal(command):
                if not self._is_standalone_submit_command(command):
                    logger.warning("🚫 SUBMISSION REJECTED: submit marker must be standalone")
                    return {
                        "output": "Submission blocked: run `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` as a standalone command.",
                        "returncode": 0,
                    }

                if self._can_submit():
                    logger.info("✅ TASK SUBMISSION DETECTED")
                    self._task_completed = True
                    return {
                        "output": "✅ Task submission confirmed.",
                        "returncode": 0,
                    }
                logger.warning("🚫 SUBMISSION REJECTED: insufficient evidence")
                return {
                    "output": "Submission blocked: need traceable code evidence and stronger progress before final submission.",
                    "returncode": 0,
                }

            # 补偿方案 B：对“全库脚本扫描”做软拦截（带改写建议）
            if self._should_soft_block_broad_scan(command):
                logger.info("↪️ BROAD SCAN REWRITTEN: command rewritten into focused lookup")
                plan = self._build_broad_scan_rewrite_plan(command)
                suggested = plan.get("commands", [])
                if suggested:
                    first_cmd = suggested[0]
                    rewritten = original_execute(first_cmd, cwd, timeout=timeout)
                    rewritten_output = rewritten.get("output", "") if isinstance(rewritten, dict) else ""
                    return {
                        "output": (
                            "[AUTO REWRITE] Broad scan was rewritten into a focused command.\n"
                            f"Original: {command}\n"
                            f"Rewritten: {first_cmd}\n"
                            f"{rewritten_output}"
                        ),
                        "returncode": rewritten.get("returncode", 0) if isinstance(rewritten, dict) else 0,
                    }
                return {
                    "output": plan.get("hint", "Broad-scan command blocked."),
                    "returncode": 0,
                }

            # 命令过滤
            should_block, reason = self.cmd_filter.should_block(command)
            if should_block:
                logger.warning(f"🚫 BLOCKED: {command}")
                return {"output": f"Command blocked: {reason}", "returncode": 0}

            logger.info(f"✅ Allowing: {command}")
            return original_execute(command, cwd, timeout=timeout)

        env.execute = filtered_execute
        logger.info("✓ Filter installed successfully")

    def _is_broad_scan_command(self, command: str) -> bool:
        """识别高噪声全库脚本扫描命令（while/for/xargs/管道+find）。"""
        cmd = (command or "").lower()
        markers = ["while ", "for ", "xargs", "|", ";", "&& find ", "find .", "find ./"]
        # 仅当同时出现“枚举文件 + 批处理”时判定为 broad-scan，降低误伤
        has_enumeration = any(k in cmd for k in ["find ", "rg --files", "ls -r", "fd "])
        has_batch = any(m in cmd for m in markers)
        return has_enumeration and has_batch

    def _should_soft_block_broad_scan(self, command: str) -> bool:
        """补偿方案 A/B：早期预算内禁止宽扫描；证据停滞后允许升级。"""
        if not getattr(self.exp_config, "enable_scan_compensation", True):
            return False
        if not self._is_broad_scan_command(command):
            return False

        step_count = max(0, (len(getattr(self, "messages", [])) - 2) // 2)
        early_budget = int(getattr(self.exp_config, "early_exploration_budget_steps", 2))
        allow_after = int(getattr(self.exp_config, "allow_broad_scan_after_stagnation", 3))

        manager = getattr(self, "subq_manager", None)
        stagnation = int(getattr(manager, "no_new_evidence_steps", 0)) if manager is not None else 0

        # 预算期内默认拦截；若证据已明显停滞，则放行升级探索
        return step_count <= early_budget and stagnation < allow_after

    def _build_broad_scan_rewrite_plan(self, command: str) -> dict:
        """补偿方案：把宽扫描重写为图引导的聚焦读取步骤。"""
        hints = [
            "Broad-scan command blocked for now.",
            "Rewrite plan: (1) use GRAPH_RETRIEVE symbols, (2) rg on 1~3 files, (3) nl/sed around lines.",
        ]
        commands: list[str] = []

        symbols = []
        q = self.messages[1]["content"] if len(getattr(self, "messages", [])) > 1 else ""
        symbols.extend(re.findall(r"\b[A-Z][a-zA-Z]{2,}\b|\b[a-z_]{4,}\b", q))
        symbols = [x for i, x in enumerate(symbols) if x and x not in symbols[:i]][:3]

        graph_tools = getattr(self, "graph_tools", None)
        if graph_tools and symbols:
            try:
                retrieve = graph_tools.graph_retrieve(symbols)
                results = retrieve.get("results", {}) if isinstance(retrieve, dict) else {}
                for sym, items in results.items():
                    if not isinstance(items, list):
                        continue
                    for item in items[:1]:
                        fp = item.get("file")
                        ln = item.get("line")
                        if not fp:
                            continue
                        cmd1 = f'rg -n "{sym}" {fp}'
                        commands.append(cmd1)
                        if ln:
                            cmd2 = f"nl -ba {fp} | sed -n '{max(1, int(ln)-20)},{int(ln)+40}p'"
                            commands.append(cmd2)
                        if len(commands) >= 3:
                            break
                    if len(commands) >= 3:
                        break
                if commands:
                    hints.append("Suggested commands:")
                    hints.extend([f"- {t}" for t in commands])
            except Exception:
                pass

        if not commands:
            commands = [
                'rg -n "<symbol>" <candidate_file.py>',
                "nl -ba <candidate_file.py> | sed -n 'start,endp'",
            ]
            hints.append("Suggested commands:")
            hints.extend([f"- {t}" for t in commands])

        return {"hint": "\n".join(hints), "commands": commands}

    def _build_broad_scan_rewrite_hint(self, command: str) -> str:
        """兼容旧接口：仅返回文本提示。"""
        return self._build_broad_scan_rewrite_plan(command).get("hint", "")

    def _extract_evidence_refs(self, text: str) -> set[str]:
        """提取 file.py:line 或 file.py:nl 形式证据。"""
        refs = set(re.findall(r"\b[\w/.-]+\.py:(?:\d+|nl)\b", text or ""))
        return refs

    def _collected_evidence_count(self) -> int:
        """基于历史 observation 统计已收集的证据引用数量。"""
        refs = set()
        for msg in getattr(self, "messages", []):
            if msg.get("role") in {"user", "assistant"}:
                refs.update(self._extract_evidence_refs(msg.get("content", "")))
        return len(refs)

    def _assistant_evidence_count(self) -> int:
        """仅统计 assistant 消息中的证据引用数（更严格的提交约束）。"""
        refs = set()
        for msg in getattr(self, "messages", []):
            if msg.get("role") == "assistant":
                refs.update(self._extract_evidence_refs(msg.get("content", "")))
        return len(refs)

    def _can_submit(self) -> bool:
        """提交前门槛：避免过早提交，要求有覆盖度与可追溯证据。"""
        step_count = max(0, (len(getattr(self, "messages", [])) - 2) // 2)
        manager = getattr(self, "subq_manager", None)

        total_subq = len(getattr(manager, "sub_questions", []) or []) if manager is not None else 0
        collected_evidence = self._collected_evidence_count()
        assistant_evidence = self._assistant_evidence_count()
        cfg = getattr(self, "exp_config", None)
        min_total_evidence = int(getattr(cfg, "min_submit_total_evidence", 2))
        min_assistant_evidence = int(getattr(cfg, "min_submit_assistant_evidence", 2))
        min_steps = int(getattr(cfg, "min_submit_steps", 4))

        # strategic 模式下按子问题规模设置最小浏览文件数；vanilla 至少读 1 个 .py
        min_viewed = 2 if total_subq >= 3 else 1
        if len(self.viewed_files) < min_viewed:
            return False

        # strategic 模式下，至少完成一半子问题（且多子问题时至少 2 个），并有证据引用
        if manager is not None and getattr(manager, "sub_questions", None):
            subq = manager.sub_questions
            total = len(subq)
            satisfied = sum(1 for x in subq if x.get("status") == "satisfied")
            progressed = sum(1 for x in subq if float(x.get("progress", 0.0)) >= 0.6)
            evidence_refs = sum(len(x.get("evidence_found", [])) for x in subq)

            min_satisfied = 1 if total <= 2 else max(2, (total + 1) // 2)
            if satisfied < min_satisfied:
                return False
            if evidence_refs < min_satisfied:
                return False
            if collected_evidence < max(min_satisfied, min_total_evidence):
                return False
            if assistant_evidence < max(min_satisfied, min_assistant_evidence):
                return False
            if satisfied + progressed < min(total, min_satisfied + 1):
                return False

            return step_count >= min_steps

        # vanilla 模式：仍要求至少有一条可追溯证据，减少“长篇空答”提交
        if collected_evidence < 1:
            return False
        if assistant_evidence < 1:
            return False
        return step_count >= min_steps

    def _is_submit_signal(self, command: str) -> bool:
        """检测提交信号（允许命令中出现提交标记，但不代表可提交）。"""
        return (
            re.search(
                r"echo\s+['\"]?COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT['\"]?",
                command.strip(),
                re.IGNORECASE,
            )
            is not None
        )

    def _is_standalone_submit_command(self, command: str) -> bool:
        """提交命令必须独立执行，禁止与读代码命令串联。"""
        cmd = (command or "").strip()
        return (
            re.fullmatch(
                r"echo\s+['\"]?COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT['\"]?",
                cmd,
                flags=re.IGNORECASE,
            )
            is not None
        )

    def get_observation(self, response: dict) -> dict:
        """适配观察值处理 + 终止检测"""
        obs_dict = super().get_observation(response)

        # 键名适配
        raw_output = obs_dict.get("output") or obs_dict.get("observation") or ""
        obs_dict["observation"] = raw_output

        step = max(0, (len(getattr(self, "messages", [])) - 2) // 2)
        action_preview = (obs_dict.get("action", "N/A") or "N/A")[:88]
        output_preview = (raw_output or "").replace(chr(10), " ")[:140]
        logger.info(f"📍S{step:02d} | rc={obs_dict.get('returncode', 'N/A')} | action={action_preview}")
        logger.info(f"   ↳ {output_preview}")

        # 使用父类的异常机制终止
        if self._task_completed:
            self._final_answer = self._extract_final_answer()
            logger.info(f"📝 Final answer extracted: {len(self._final_answer) if self._final_answer else 0} chars")
            from minisweagent.agents.default import TerminatingException

            raise TerminatingException(self._final_answer or "Task completed")

        # 统计查看的文件
        if "action" in obs_dict:
            if match := re.search(r"(cat|nl|head|tail|less|sed)\s+.*?(\S+\.py)", obs_dict["action"]):
                self.viewed_files.add(match.group(2))

        return obs_dict

    def _build_summary_from_history(self) -> str:
        """当未提取到 FINAL ANSWER 时，从历史对话合成标准答案。"""
        refs = []
        for msg in getattr(self, "messages", []):
            if msg.get("role") in {"assistant", "user"}:
                refs.extend(sorted(self._extract_evidence_refs(msg.get("content", ""))))

        unique_refs = sorted(set(refs))[:12]
        manager = getattr(self, "subq_manager", None)
        subq_lines = []
        if manager is not None:
            for sq in (getattr(manager, "sub_questions", []) or [])[:8]:
                subq_lines.append(
                    f"- {sq.get('id', 'SQ?')} [{sq.get('status', 'open')}]: {sq.get('sub_question', '')}"
                )

        evidence_part = ", ".join(unique_refs) if unique_refs else "(no parseable file.py:line evidence found)"
        lines = [
            "[SUMMARY] Consolidated answer from the available execution trace.",
            f"[KEY CODE LOCATIONS] {evidence_part}",
            "[SUB-QUESTION COVERAGE]",
        ]
        lines.extend(subq_lines if subq_lines else ["- Vanilla flow or no initialized sub-questions."])
        lines.append("[NOTE] This answer was synthesized from history (typically at max steps or when FINAL ANSWER is missing).")
        return "\n".join(lines)

    def _format_final_answer(self, answer: str) -> str:
        """把模型答案统一成“回答 + 详细分析”格式。"""
        clean = (answer or "").strip()
        if not clean:
            return clean

        # 清理常见尾句，避免把“提交动作说明”混入最终答案
        clean = re.sub(r"\bI will now submit.*$", "", clean, flags=re.IGNORECASE | re.DOTALL).strip()

        # 若已是标准结构，直接返回
        if "Answer:" in clean and "Detailed analysis:" in clean:
            return clean

        # 自动提取简答：取第一段前 220 字
        first_para = clean.split("\n\n", 1)[0].strip()
        if len(first_para) > 220:
            first_para = first_para[:220].rsplit(" ", 1)[0] + "..."

        return (
            f"Answer:\n{first_para}\n\n"
            f"Detailed analysis:\n{clean}"
        )

    def _extract_final_answer(self) -> str:
        """优先提取 FINAL ANSWER；失败时从历史自动汇总。"""
        if not hasattr(self, "messages"):
            return ""

        for msg in reversed(self.messages):
            if msg.get("role") != "assistant":
                continue

            content = msg.get("content", "")
            if not content:
                continue

            match = re.search(r"##\s*FINAL\s*ANSWER\s*(.*)", content, re.DOTALL | re.IGNORECASE)
            if match:
                answer = match.group(1).strip()
                answer = re.sub(r"```bash.*?```", "", answer, flags=re.DOTALL).strip()
                if len(answer) > 20:
                    return self._format_final_answer(answer)

            if "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" in content and len(content) > 100:
                answer = re.sub(r"```bash.*?```", "", content, flags=re.DOTALL).strip()
                answer = re.sub(r"^(THOUGHT|Thought|REASONING):\s*", "", answer, flags=re.IGNORECASE).strip()
                if len(answer) > 20:
                    return self._format_final_answer(answer)

        logger.warning("⚠️  No substantive answer found in Assistant messages; fallback to history synthesis.")
        return self._format_final_answer(self._build_summary_from_history())

    def _ensure_final_answer(self):
        """在异常终止/最大步数情况下，确保 final_answer 存在。"""
        if not self._final_answer:
            self._final_answer = self._extract_final_answer()

    def _get_stats(self) -> dict:
        """统计信息"""
        if hasattr(self, "messages"):
            steps = max(0, (len(self.messages) - 2) // 2)
        else:
            steps = len(getattr(self, "history", []))

        stats = {
            "total_steps": steps,
            "viewed_files": len(self.viewed_files),
            "task_completed": self._task_completed,
            "answer_length": len(self._final_answer) if self._final_answer else 0,
        }

        if self.cmd_filter:
            stats.update(self.cmd_filter.get_stats())

        return stats

    def _print_final_report(self):
        """打印执行摘要和最终答案"""
        logger.info("\n" + "=" * 40 + "\n🏁 Execution Summary\n" + "=" * 40)
        for k, v in self._get_stats().items():
            logger.info(f"  {k}: {v}")

        if hasattr(self, "subq_manager") and getattr(self, "subq_manager", None) is not None:
            subq = getattr(self.subq_manager, "sub_questions", []) or []
            satisfied = sum(1 for x in subq if x.get("status") == "satisfied")
            blocked = sum(1 for x in subq if x.get("status") == "blocked")
            logger.info(f"  subq_progress: {satisfied}/{len(subq)} satisfied, blocked={blocked}")

        if self._final_answer:
            display_text = self._final_answer[:500] + "..." if len(self._final_answer) > 500 else self._final_answer
            logger.info("\n📝 EXTRACTED ANSWER:\n" + "-" * 20)
            logger.info(display_text)
            logger.info("-" * 20)

    def _save_trajectory(self, output_dir: str = "experiments"):
        """保存完整轨迹（包含对话历史）"""
        if not self.start_time:
            return

        self._ensure_final_answer()

        output_path = Path(output_dir) / "comparison_reports" / "trajectories" / self.exp_config.name
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_full_log.json"

        data = {
            "trajectory_schema_version": "stage1_v2.3",
            "metadata": {
                "config": self.exp_config.to_dict(),
                "timestamp": timestamp,
                "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.end_time else 0,
            },
            "statistics": self._get_stats(),
            "final_answer": self._final_answer,
            "history": self.messages,
        }

        if hasattr(self, "decomposition") and getattr(self, "decomposition") is not None:
            data["decomposition_action"] = {
                "decomposition": self.decomposition,
                "quality": getattr(self, "decomposition_quality", None),
                "workflow_trace": getattr(self, "decomposition_workflow_trace", []),
            }

        if hasattr(self, "subq_manager") and getattr(self, "subq_manager") is not None:
            try:
                data["subquestion_trace"] = self.subq_manager.snapshot()
            except Exception:
                pass

        # P0/P1：写入统一工具调用轨迹（若可用）
        if hasattr(self, "tool_registry") and getattr(self, "tool_registry", None) is not None:
            try:
                data["tool_calls"] = self.tool_registry.get_calls()
            except Exception:
                pass

        with open(output_path / filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"💾 Full trajectory saved to: {output_path / filename}")
