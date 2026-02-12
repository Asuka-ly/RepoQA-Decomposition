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
                if self._can_submit():
                    logger.info("✅ TASK SUBMISSION DETECTED")
                    self._task_completed = True
                    return {
                        "output": "✅ Task submission confirmed.",
                        "returncode": 0
                    }
                logger.warning("🚫 SUBMISSION REJECTED: insufficient evidence")
                return {
                    "output": "Submission blocked: gather more code evidence (need >=1 viewed .py file and non-trivial progress).",
                    "returncode": 0
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

    def _can_submit(self) -> bool:
        """提交前门槛，降低过早提交噪声。"""
        # 至少要读过一个 .py 文件
        if len(self.viewed_files) < 1:
            return False

        # 若是 strategic agent，要求 subq 至少有进度或完成
        if hasattr(self, "subq_manager") and getattr(self, "subq_manager") is not None:
            subq = getattr(self, "subq_manager").sub_questions
            if subq:
                progressed = any(float(x.get("progress", 0.0)) >= 0.2 or x.get("status") == "satisfied" for x in subq)
                return progressed

        return True
    
    def _is_submit_signal(self, command: str) -> bool:
        """检测提交信号"""
        return (
            re.search(
                r"echo\s+['\"]?COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT['\"]?",
                command.strip(),
                re.IGNORECASE,
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
        logger.info("=" * 60)
        logger.info(f"📍 STEP {step} | Observation")
        logger.info(f"  action: {obs_dict.get('action', 'N/A')}")
        logger.info(f"  output: {raw_output[:180].replace(chr(10), ' ')}")
        logger.info(f"  returncode: {obs_dict.get('returncode', 'N/A')}")
        logger.info("=" * 60)

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
                    return answer

            if "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" in content and len(content) > 100:
                answer = re.sub(r"```bash.*?```", "", content, flags=re.DOTALL).strip()
                answer = re.sub(r"^(THOUGHT|Thought|REASONING):\s*", "", answer, flags=re.IGNORECASE).strip()
                if len(answer) > 20:
                    return answer

        logger.warning("⚠️  No substantive answer found in Assistant messages; fallback to history synthesis.")
        return self._build_summary_from_history()

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
            logger.info(f"  subq_progress: {satisfied}/{len(subq)} satisfied")

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
            "metadata": {
                "config": self.exp_config.to_dict(),
                "timestamp": timestamp,
                "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.end_time else 0,
            },
            "statistics": self._get_stats(),
            "final_answer": self._final_answer,
            "history": self.messages,
        }

        # 可选：保存子问题状态轨迹（供后续 RL 使用）
        if hasattr(self, "subq_manager") and getattr(self, "subq_manager") is not None:
            try:
                data["subquestion_trace"] = self.subq_manager.snapshot()
            except Exception:
                pass
        
        with open(output_path / filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Full trajectory saved to: {output_path / filename}")
