"""战略分解 Agent"""
from src.agents.base import BaseRepoQAAgent
from src.graph import CodeGraph
from src.decomposer import StrategicDecomposer
from src.injectors import GraphInjector
from src.utils import build_task_prompt, setup_logger

from datetime import datetime

logger = setup_logger(__name__)

class StrategicRepoQAAgent(BaseRepoQAAgent):
    """使用战略分解的 Agent"""
    
    def __init__(self, model, env, config, **kwargs):
        super().__init__(model, env, config, **kwargs)
        self.code_graph = None
        self.decomposer = None
        self.injector = None
    
    def run(self, task: str, repo_path: str = None):
        self.start_time = datetime.now()
        
        # 1. 构建代码图
        if self.exp_config.enable_graph and repo_path:
            self.code_graph = CodeGraph()
            self.code_graph.build(repo_path)
            
            if self.exp_config.enable_graph_injection:
                self.injector = GraphInjector(self.code_graph, enabled=True)
        
        # 2. 分解问题
        self.decomposer = StrategicDecomposer(self.model, self.code_graph)
        decomposition = self.decomposer.decompose(task)
        
        # 3. 构造增强任务
        enhanced_task = build_task_prompt(task, repo_path, decomposition, self.exp_config)
        
        # 4. 调用父类 run()
        try:
            exit_status, message = super().run(enhanced_task)
            return message
        finally:
            self.end_time = datetime.now()
            self._save_trajectory()
            self._print_final_report()
    
    def get_observation(self, response: dict) -> dict:
        """注入图提示"""
        obs_dict = super().get_observation(response)
        
        if self.injector and "action" in obs_dict:
            raw_output = obs_dict.get("observation", "")
            obs_dict["observation"] = self.injector.inject(obs_dict["action"], raw_output)
            obs_dict["output"] = obs_dict["observation"]
        
        return obs_dict
    
    def _get_stats(self) -> dict:
        stats = super()._get_stats()
        if self.injector:
            stats['total_injections'] = self.injector.injection_count
        return stats
