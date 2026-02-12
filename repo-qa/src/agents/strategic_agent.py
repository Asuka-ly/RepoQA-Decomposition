"""战略分解 Agent"""
from datetime import datetime

from src.agents.base import BaseRepoQAAgent
from src.decomposer import StrategicDecomposer
from src.decomposition_action import DecompositionAction
from src.graph import CodeGraph
from src.graph_tools import GraphTools
from src.injectors import GraphInjector
from src.subquestion_manager import SubQuestionManager
from src.utils import build_task_prompt, setup_logger

logger = setup_logger(__name__)


class StrategicRepoQAAgent(BaseRepoQAAgent):
    """使用战略分解的 Agent"""

    def __init__(self, model, env, config, **kwargs):
        super().__init__(model, env, config, **kwargs)
        self.code_graph = None
        self.decomposer = None
        self.injector = None
        self.subq_manager = SubQuestionManager()
        self.decomposition = None
    
    def run(self, task: str, repo_path: str = None):
        self.start_time = datetime.now()

        # 1. 构建代码图
        if self.exp_config.enable_graph and repo_path:
            self.code_graph = CodeGraph()
            self.code_graph.build(repo_path)

            if self.exp_config.enable_graph_injection:
                self.injector = GraphInjector(self.code_graph, enabled=True)

        # 2. 分解问题（Stage1 v2: 独立 Action）
        self.graph_tools = GraphTools(self.code_graph)
        self.decomposer = StrategicDecomposer(self.model, self.code_graph)
        decomposition = self.decomposer.decompose(task)
        self.decomposition = decomposition
        self.subq_manager.initialize(decomposition)
        
        # 3. 构造增强任务
        enhanced_task = build_task_prompt(task, repo_path, decomposition, self.exp_config)

        # 4. 调用父类 run()
        try:
            _, message = super().run(enhanced_task)
            return message
        finally:
            self.end_time = datetime.now()
            self._save_trajectory()
            self._print_final_report()

    def get_observation(self, response: dict) -> dict:
        """注入图提示 + 图工具调用"""
        obs_dict = super().get_observation(response)

        if self.injector and "action" in obs_dict:
            raw_output = obs_dict.get("observation", "")
            obs_dict["observation"] = self.injector.inject(obs_dict["action"], raw_output)
            obs_dict["output"] = obs_dict["observation"]

        if "action" in obs_dict:
            # 用于 RL 的在线状态更新
            step = max(0, (len(getattr(self, "messages", [])) - 2) // 2)
            self.subq_manager.update(
                step=step,
                action=obs_dict.get("action", ""),
                observation=obs_dict.get("observation", ""),
                graph_hint=obs_dict.get("observation", ""),
            )
            if self.subq_manager.check_replan_needed(step):
                obs_dict["observation"] += (
                    "\n\n⚠️ [REPLAN SIGNAL] Some sub-questions are blocked. "
                    "Refocus on unresolved symbols or switch entry candidates."
                )
                obs_dict["output"] = obs_dict["observation"]

        return obs_dict

    def _get_stats(self) -> dict:
        stats = super()._get_stats()
        if self.injector:
            stats['total_injections'] = self.injector.injection_count
        if self.subq_manager.sub_questions:
            stats['sub_questions_total'] = len(self.subq_manager.sub_questions)
            stats['sub_questions_satisfied'] = sum(
                1 for sq in self.subq_manager.sub_questions if sq.get('status') == 'satisfied'
            )
            stats['replan_events'] = len(self.subq_manager.replan_events)
        return stats
