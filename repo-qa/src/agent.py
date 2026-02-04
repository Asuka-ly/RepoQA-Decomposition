"""RepoQA Agent - 正确劫持版"""
import sys
import json
import re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/root/mini-swe-agent/src')
from minisweagent.agents.default import DefaultAgent

from src.graph import CodeGraph
from src.decomposer import StrategicDecomposer
from src.filters import CommandFilter
from src.injectors import GraphInjector
from src.config import ExperimentConfig
from src.utils import setup_logger, build_task_prompt

logger = setup_logger(__name__)

class RepoQAAgent(DefaultAgent):
    def __init__(self, model, env, config: ExperimentConfig, **kwargs):
        super().__init__(model, env, **kwargs)
        
        self.exp_config = config
        self.cmd_filter = CommandFilter(enabled=config.enable_command_filter)
        
        # ============================================================
        # 环境劫持：参数和返回值完全匹配 LocalEnvironment.execute
        # ============================================================
        logger.info("🔧 Installing command filter via env.execute hijacking...")
        
        # 保存原始方法
        original_execute = env.execute
        
        # 定义包装器（签名必须完全匹配）
        def filtered_execute(command: str, cwd: str = "", *, timeout: int | None = None):
            """拦截层：在真正执行前检查"""
            logger.info(f"🛡️  FILTER CHECK: {command}")
            
            should_block, reason = self.cmd_filter.should_block(command)
            
            if should_block:
                logger.warning(f"🚫 BLOCKED: {command}")
                logger.warning(f"   Reason: {reason}")
                    
                # 修改：让建议更具体，更像"正常输出"而非错误
                suggestion = self.cmd_filter.get_suggestion(command, reason)
                
                # 关键修改：returncode 改为 0，让 Agent 认为"命令成功了，但结果是个提示"
                return {
                    "output": (
                        f"Command '{command}' is not allowed in this analysis task.\n"
                        f"{suggestion}\n\n"
                        "Please proceed with reading the code using 'ls', 'cat', or 'grep'."
                    ),
                    "returncode": 0  # 改为 0，避免 Agent 认为任务失败
                }
            
            # 允许执行
            logger.info(f"✅ Allowing: {command}")
            return original_execute(command, cwd, timeout=timeout)
        
        # 替换方法
        env.execute = filtered_execute
        logger.info("✓ Filter installed successfully")
        # ============================================================
        
        self.repo_path = None
        self.code_graph = None
        self.decomposer = None
        self.injector = None
        self.viewed_files = set()
        self.start_time = None
        self.end_time = None

    def run(self, task: str, repo_path: str = None):
        self.start_time = datetime.now()
        self.repo_path = repo_path
        
        if self.exp_config.enable_graph and repo_path:
            self.code_graph = CodeGraph()
            self.code_graph.build(repo_path)
            if self.exp_config.enable_graph_injection:
                self.injector = GraphInjector(self.code_graph, enabled=True)
        
        self.decomposer = StrategicDecomposer(self.model, self.code_graph)
        decomposition = self.decomposer.decompose(task)
        
        enhanced_task = build_task_prompt(task, repo_path, decomposition, self.exp_config)
        
        try:
            return super().run(enhanced_task)
        finally:
            self.end_time = datetime.now()
            self._save_trajectory()
            self._print_final_report()

    def get_observation(self, response: dict) -> dict:
        """获取观察（拦截已在 env.execute 完成）"""
        obs_dict = super().get_observation(response)

         # 调试：打印每一步的观察结果
        logger.info("="*40)
        logger.info(f"OBSERVATION RESULT:")
        logger.info(f"  action: {obs_dict.get('action', 'N/A')}")
        logger.info(f"  observation: {obs_dict.get('observation', '')[:200]}")
        logger.info(f"  returncode: {obs_dict.get('returncode', 'N/A')}")
        logger.info("="*40)
    
        
        if "action" in obs_dict:
            act = obs_dict["action"]
            if match := re.search(r'cat\s+(\S+)', act):
                self.viewed_files.add(match.group(1))
            
            if self.injector:
                original_obs = obs_dict.get("observation", "")
                obs_dict["observation"] = self.injector.inject(act, original_obs)
        
        return obs_dict

    def _save_trajectory(self):
        if not self.start_time: return
        output_dir = Path("data/trajectories")
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{self.exp_config.name}.json"
        
        history_data = getattr(self, 'history', [])
        data = {
            "config": self.exp_config.to_dict(),
            "repo_path": self.repo_path,
            "decomposition": self.decomposer.last_result if self.decomposer else None,
            "history": history_data,
            "statistics": self._get_stats(),
            "duration_seconds": (self.end_time - self.start_time).total_seconds()
        }
        with open(output_dir / filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def _get_stats(self) -> dict:
        history = getattr(self, 'history', [])
        stats = {'total_steps': len(history), 'viewed_files': len(self.viewed_files)}
        if self.cmd_filter: stats.update(self.cmd_filter.get_stats())
        if self.injector: stats['total_injections'] = self.injector.injection_count
        return stats
        
    def _print_final_report(self):
        logger.info("\n" + "="*40 + "\n🏁 Execution Summary\n" + "="*40)
        for k, v in self._get_stats().items(): logger.info(f"  {k}: {v}")
