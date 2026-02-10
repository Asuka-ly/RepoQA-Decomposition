"""纯 mini-swe-agent Agent（无分解）- 控制变量版本"""
from src.agents.base import BaseRepoQAAgent
from src.utils import setup_logger, build_task_prompt

from datetime import datetime 

logger = setup_logger(__name__)

class VanillaRepoQAAgent(BaseRepoQAAgent):
    """不使用分解的对照组"""
    
    def run(self, task: str, repo_path: str = None):
        self.start_time = datetime.now()
        
        # 构建标准化任务（无分解）
        vanilla_task = build_task_prompt(task, repo_path, None, self.exp_config)
        
        try:
            exit_status, message = super().run(vanilla_task)
            return message
        finally:
            self.end_time = datetime.now()
            self._save_trajectory()
            self._print_final_report()
