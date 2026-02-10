"""RepoQA 基础 Agent - 提取公共逻辑"""
import sys
import re
from datetime import datetime
from pathlib import Path
import json

from minisweagent.agents.default import DefaultAgent
from src.filters import CommandFilter
from src.config import ExperimentConfig
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
                    "output": "Submission blocked: need broader code evidence and stronger sub-question completion before final submission.",
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
        """提交前门槛：避免过早提交，要求有覆盖度与可追溯证据。"""
        step_count = max(0, (len(getattr(self, "messages", [])) - 2) // 2)
        manager = getattr(self, "subq_manager", None)

        # strategic 模式下按子问题规模设置最小浏览文件数，普通模式至少 1 个
        total_subq = len(getattr(manager, "sub_questions", []) or []) if manager is not None else 0
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
            if satisfied + progressed < min(total, min_satisfied + 1):
                return False

            # 防止 1~2 步就尝试提交
            return step_count >= 3

        return step_count >= 2
    
    def _is_submit_signal(self, command: str) -> bool:
        """检测提交信号"""
        return re.search(r"echo\s+['\"]?COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT['\"]?", 
                        command.strip(), re.IGNORECASE) is not None
    
    def get_observation(self, response: dict) -> dict:
        """适配观察值处理 + 终止检测"""
        obs_dict = super().get_observation(response)
        
        # 键名适配
        raw_output = obs_dict.get('output') or obs_dict.get('observation') or ""
        obs_dict["observation"] = raw_output
        
        logger.info("="*40)
        logger.info(f"OBSERVATION RESULT:")
        logger.info(f"  action: {obs_dict.get('action', 'N/A')}")
        logger.info(f"  output_snippet: {raw_output[:200].replace(chr(10), ' ')}")
        logger.info(f"  returncode: {obs_dict.get('returncode', 'N/A')}")
        logger.info("="*40)
        
        # 使用父类的异常机制终止
        if self._task_completed:
            self._final_answer = self._extract_final_answer()
            logger.info(f"📝 Final answer extracted: {len(self._final_answer) if self._final_answer else 0} chars")
            # 抛出 TerminatingException
            from minisweagent.agents.default import TerminatingException
            raise TerminatingException(self._final_answer or "Task completed")
        
        # 统计查看的文件
        if "action" in obs_dict:
            if match := re.search(r'(cat|nl|head|tail|less|sed)\s+.*?(\S+\.py)', obs_dict["action"]):
                self.viewed_files.add(match.group(2))
        
        return obs_dict
        

    def _extract_final_answer(self) -> str:
        """精准答案提取逻辑：只看 Assistant 的话，排除指令干扰"""
        if not hasattr(self, 'messages'):
            return ""
        
        # 按照时间从新到旧遍历
        for msg in reversed(self.messages):
            # 🔴 关键修复：只处理助手发出的消息，忽略环境反馈和系统指令
            if msg.get('role') != 'assistant':
                continue
                
            content = msg.get('content', '')
            if not content:
                continue
    
            # 策略 A：寻找明确的标记 ## FINAL ANSWER
            match = re.search(
                r'##\s*FINAL\s*ANSWER\s*(.*)', 
                content, 
                re.DOTALL | re.IGNORECASE
            )
            
            if match:
                answer = match.group(1).strip()
                # 清理：移除可能附带在末尾的 bash 代码块（echo 命令）
                answer = re.sub(r'```bash.*?```', '', answer, flags=re.DOTALL).strip()
                # 只有当答案长度超过一定阈值时才返回（防止抓到占位符）
                if len(answer) > 20:
                    return answer
            
            # 策略 B：启发式抓取。如果模型没写标记，但这一轮它执行了提交信号且文本很长
            if "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" in content and len(content) > 100:
                # 提取 bash 块之前的文字作为答案
                answer = re.sub(r'```bash.*?```', '', content, flags=re.DOTALL).strip()
                # 移除 THOUGHT 等前缀
                answer = re.sub(r'^(THOUGHT|Thought|REASONING):\s*', '', answer, flags=re.IGNORECASE).strip()
                if len(answer) > 20:
                    return answer
    
        logger.warning("⚠️  No substantive answer found in Assistant messages.")
        return "ERROR: Agent finished but failed to provide a valid answer block."

    
    def _get_stats(self) -> dict:
        """统计信息"""
        if hasattr(self, 'messages'):
            steps = max(0, (len(self.messages) - 2) // 2)
        else:
            steps = len(getattr(self, 'history', []))
        
        stats = {
            'total_steps': steps,
            'viewed_files': len(self.viewed_files),
            'task_completed': self._task_completed,
            'answer_length': len(self._final_answer) if self._final_answer else 0
        }
        
        if self.cmd_filter:
            stats.update(self.cmd_filter.get_stats())
        
        return stats

    def _print_final_report(self):
        """打印执行摘要和最终答案"""
        logger.info("\n" + "="*40 + "\n🏁 Execution Summary\n" + "="*40)
        for k, v in self._get_stats().items():
            logger.info(f"  {k}: {v}")
        
        # 🟢 新增：在终端直接显示答案前 500 字
        if self._final_answer:
            display_text = self._final_answer[:500] + "..." if len(self._final_answer) > 500 else self._final_answer
            logger.info("\n📝 EXTRACTED ANSWER:\n" + "-"*20)
            logger.info(display_text)
            logger.info("-"*20)

    def _save_trajectory(self, output_dir: str = "experiments"):
        """保存完整轨迹（包含对话历史）"""
        if not self.start_time:
            return
        
        # 获取实验名称对应的目录
        output_path = Path(output_dir) / "comparison_reports" / "trajectories" / self.exp_config.name
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_full_log.json"
        
        # 🟢 记录完整数据
        data = {
            "metadata": {
                "config": self.exp_config.to_dict(),
                "timestamp": timestamp,
                "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.end_time else 0,
            },
            "statistics": self._get_stats(),
            "final_answer": self._final_answer,
            # ⚠️ 记录完整对话历史，用于后续复盘
            "history": self.messages 
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
