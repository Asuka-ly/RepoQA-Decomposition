"""RepoQA Agent - 基础版（之前成功运行过的）"""
import sys
from pathlib import Path
sys.path.insert(0, '/root/mini-swe-agent/src')
sys.path.insert(0, str(Path(__file__).parent.parent))

from minisweagent.agents.default import DefaultAgent
from decomposer.strategic import StrategicDecomposer
from graph.builder import CodeGraphBuilder

class RepoQAAgent(DefaultAgent):
    def __init__(self, model, env, **kwargs):
        super().__init__(model, env, **kwargs)
        self.code_graph = None
        self.graph_builder = CodeGraphBuilder()
        self.target_repo_path = None

    def run(self, task: str, repo_path: str = None):
        if repo_path:
            self.target_repo_path = repo_path
            self.graph_builder.build_from_repo(repo_path)
            self.code_graph = self.graph_builder
        
        self.decomposer = StrategicDecomposer(self.model, self.code_graph)
        decomposition = self.decomposer.decompose(task)
        
        # 构造任务 - 核心修改：更强的禁止测试约束
        enhanced_task = "MULTI-HOP CODE ANALYSIS TASK (READ ONLY, NO TESTING)\n\n"
        for i, aspect in enumerate(decomposition['independent_aspects'], 1):
            enhanced_task += f"ASPECT {i}: {aspect['aspect']}\n"
            enhanced_task += f"  Entry Point: {aspect['entry_point']}\n\n"
        enhanced_task += f"GOAL: {decomposition.get('synthesis_instruction', '')}\n\n"
        enhanced_task += f"QUESTION: {task}\n"
        
        return super().run(enhanced_task)

    def get_observation(self, response: dict) -> dict:
        observation_dict = super().get_observation(response)
        if self.code_graph and "action" in observation_dict:
            cmd = observation_dict["action"]
            for node_id, data in self.code_graph.graph.nodes(data=True):
                node_name = data['name']
                if len(node_name) > 4 and node_name in cmd:
                    neighbors = self.code_graph.get_neighbors(node_id)
                    if neighbors and (neighbors['calls'] or neighbors['called_by']):
                        hint = f"\n\n🔍 [GRAPH HINT] '{node_name}' → {', '.join(neighbors['calls'][:5])}"
                        self.messages[-1]["content"] += hint
                        break
        return observation_dict

    def print_trajectory(self):
        for i, msg in enumerate(self.messages):
            role = msg['role'].upper()
            print(f"--- Message {i} [{role}] ---\n{msg['content'][:300]}...\n")
