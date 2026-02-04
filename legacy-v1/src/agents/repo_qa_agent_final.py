"""RepoQA Agent - Final Stable Version"""
import sys
from pathlib import Path

sys.path.insert(0, '/root/mini-swe-agent/src')
sys.path.insert(0, str(Path(__file__).parent.parent))

from minisweagent.agents.default import DefaultAgent
from decomposer.strategic import StrategicDecomposer
from graph.builder import CodeGraphBuilder

class RepoQAAgentFinal(DefaultAgent):
    def __init__(self, model, env, **kwargs):
        super().__init__(model, env, **kwargs)
        self.code_graph = None
        self.graph_builder = CodeGraphBuilder()
        self.decomposer = None
        self.target_repo_path = None

    def run(self, task: str, repo_path: str = None):
        print("\n" + "="*60)
        print("🎯 RepoQA Agent - Final Stable Mode")
        print("="*60 + "\n")
        
        # 1. 构建代码图
        if repo_path:
            self.target_repo_path = repo_path
            self.graph_builder.build_from_repo(repo_path)
            self.code_graph = self.graph_builder
        
        # 2. 初始化分解器
        self.decomposer = StrategicDecomposer(self.model, self.code_graph)
        
        # 3. 执行分解
        decomposition = self.decomposer.decompose(task)
        
        # 4. 构造任务描述
        enhanced_task = f"""You are a code analysis specialist. Your task is to READ and ANALYZE code, NOT to execute or test it.

⚠️ CRITICAL RULES:
- DO NOT run any commands like: sleep, python -c, bash -c, timeout
- DO NOT write test files
- ONLY use: cd, ls, cat, grep, find, head, tail

TARGET REPOSITORY: {self.target_repo_path}

Your mission is to ANALYZE the source code flow based on these aspects:
"""
        
        for i, aspect in enumerate(decomposition['independent_aspects'], 1):
            enhanced_task += f"\nASPECT {i}: {aspect['aspect']}\n"
            enhanced_task += f"  ENTRY POINT: {aspect['entry_point']}\n"
        
        enhanced_task += f"\nGOAL: {decomposition.get('synthesis_instruction', 'Combine findings')}\n"
        enhanced_task += f"\nORIGINAL QUESTION: {task}\n"
        enhanced_task += """
INSTRUCTIONS:
1. cd to the target repository first.
2. Use cat, grep, find to READ and UNDERSTAND the logic.
3. DO NOT use the submit command until you have an explanation.
4. Final step: use 'echo' to provide your analysis results.
"""
        
        # 5. 执行
        return super().run(enhanced_task)

    def get_observation(self, response: dict) -> dict:
        """重写观察获取，注入图知识"""
        observation_dict = super().get_observation(response)
        
        # 图知识注入
        if self.code_graph and "action" in observation_dict:
            cmd = observation_dict["action"]
            
            for node_id, data in self.code_graph.graph.nodes(data=True):
                node_name = data['name']
                if len(node_name) > 4 and node_name in cmd:
                    neighbors = self.code_graph.get_neighbors(node_id)
                    if neighbors and (neighbors['calls'] or neighbors['called_by']):
                        hint = "\n\n🔍 [GRAPH HINT]"
                        if neighbors['calls']:
                            hint += f"\n  → '{node_name}' calls: {', '.join(neighbors['calls'][:5])}"
                        if neighbors['called_by']:
                            hint += f"\n  ← '{node_name}' is called by: {', '.join(neighbors['called_by'][:3])}"
                        hint += "\n  💡 Consider exploring these for the next hop."
                        self.messages[-1]["content"] += hint
                        print(f"💉 Injected knowledge for: {node_name}")
                        break
        
        return observation_dict

    def print_trajectory(self):
        print("\n" + "📜 "*20)
        print("   AGENT TRAJECTORY")
        print("📜 "*20 + "\n")
        for i, msg in enumerate(self.messages):
            role = msg['role'].upper()
            content = msg['content'][:500] + "..." if len(msg['content']) > 500 else msg['content']
            print(f"--- Message {i} [{role}] ---")
            print(content)
            print("-" * 40)
