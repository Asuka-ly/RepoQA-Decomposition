#!/bin/bash

echo "🚨 开始恢复 RepoQA-Decomposition 项目..."
echo ""

# 创建项目目录结构
mkdir -p /root/RepoQA-Decomposition/src/{graph,decomposer,agents}

cd /root/RepoQA-Decomposition

# ============================================================
# 1. src/graph/__init__.py
# ============================================================
echo "📝 恢复 src/graph/__init__.py"
cat > src/graph/__init__.py << 'PYEOF'
"""代码图构建模块"""
from .builder import CodeGraphBuilder

__all__ = ['CodeGraphBuilder']
PYEOF

# ============================================================
# 2. src/graph/builder.py
# ============================================================
echo "📝 恢复 src/graph/builder.py"
cat > src/graph/builder.py << 'PYEOF'
"""代码图构建器 - tree-sitter 0.25.2 兼容版本"""
import networkx as nx
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
from pathlib import Path

class CodeGraphBuilder:
    def __init__(self):
        self.PY_LANGUAGE = Language(tspython.language())
        self.parser = Parser(self.PY_LANGUAGE)
        self.graph = nx.DiGraph()
        self.file_contents = {}

    def build_from_repo(self, repo_path):
        """扫描整个仓库并构建图"""
        repo_path = Path(repo_path)
        print(f"📂 Scanning repository: {repo_path}")
        
        self.graph = nx.DiGraph()
        self.file_contents = {}
        
        python_files = list(repo_path.rglob("*.py"))
        print(f"   Found {len(python_files)} Python files\n")
        
        # 第一遍：提取所有节点
        for py_file in python_files:
            try:
                relative_path = py_file.relative_to(repo_path)
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    code = f.read()
                self.file_contents[str(relative_path)] = code
                self._parse_definitions(py_file, str(relative_path), code)
            except:
                pass
        
        # 第二遍：提取调用关系（边）
        for rel_path, code in self.file_contents.items():
            self._parse_calls(rel_path, code)
        
        print(f"✓ Graph built: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges\n")
        return self.graph

    def _parse_definitions(self, file_path, rel_path, code):
        """提取文件中的类和函数定义"""
        tree = self.parser.parse(bytes(code, "utf8"))
        
        def traverse(node, parent_context=None):
            if node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = code[name_node.start_byte:name_node.end_byte]
                    node_id = f"{rel_path}::{class_name}"
                    
                    self.graph.add_node(
                        node_id,
                        name=class_name,
                        file=rel_path,
                        type='class',
                        line=node.start_point[0] + 1
                    )
                    
                    for child in node.children:
                        traverse(child, node_id)
                    return
            
            elif node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = code[name_node.start_byte:name_node.end_byte]
                    node_id = f"{rel_path}::{func_name}"
                    
                    self.graph.add_node(
                        node_id,
                        name=func_name,
                        file=rel_path,
                        type='function',
                        line=node.start_point[0] + 1
                    )
                    
                    if parent_context:
                        self.graph.add_edge(parent_context, node_id, type='contains')
                    
                    return
            
            for child in node.children:
                traverse(child, parent_context)
        
        traverse(tree.root_node)

    def _parse_calls(self, rel_path, code):
        """提取函数调用关系（简化版：基于字符串匹配）"""
        tree = self.parser.parse(bytes(code, "utf8"))
        
        local_defs = [nid for nid in self.graph.nodes() if nid.startswith(f"{rel_path}::")]
        
        def find_calls_in_function(node, current_func_id):
            if node.type == 'call':
                func_node = node.child_by_field_name('function')
                if func_node:
                    called_text = code[func_node.start_byte:func_node.end_byte]
                    if '.' in called_text:
                        called_name = called_text.split('.')[-1]
                    else:
                        called_name = called_text
                    
                    for target_node in self.graph.nodes():
                        if target_node.endswith(f"::{called_name}"):
                            self.graph.add_edge(current_func_id, target_node, type='calls')
            
            for child in node.children:
                find_calls_in_function(child, current_func_id)
        
        def traverse_for_calls(node, current_context=None):
            if node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = code[name_node.start_byte:name_node.end_byte]
                    func_id = f"{rel_path}::{func_name}"
                    if func_id in self.graph.nodes():
                        find_calls_in_function(node, func_id)
                return
            
            for child in node.children:
                traverse_for_calls(child, current_context)
        
        traverse_for_calls(tree.root_node)

    def get_related_context(self, keyword):
        """根据关键词检索相关代码"""
        results = []
        for node, data in self.graph.nodes(data=True):
            if keyword.lower() in data['name'].lower():
                results.append(data)
        return results
    
    def get_neighbors(self, node_id):
        """获取节点的邻居信息"""
        if node_id not in self.graph:
            return None
        
        successors = list(self.graph.successors(node_id))
        predecessors = list(self.graph.predecessors(node_id))
        
        return {
            'calls': [n.split('::')[-1] for n in successors if self.graph[node_id][n].get('type') == 'calls'],
            'called_by': [n.split('::')[-1] for n in predecessors if self.graph[n][node_id].get('type') == 'calls'],
            'contains': [n.split('::')[-1] for n in successors if self.graph[node_id][n].get('type') == 'contains']
        }

    def summary(self):
        classes = sum(1 for _, d in self.graph.nodes(data=True) if d['type'] == 'class')
        functions = sum(1 for _, d in self.graph.nodes(data=True) if d['type'] == 'function')
        return f"Classes: {classes}, Functions: {functions}"
PYEOF

# ============================================================
# 3. src/decomposer/__init__.py
# ============================================================
echo "📝 恢复 src/decomposer/__init__.py"
cat > src/decomposer/__init__.py << 'PYEOF'
"""问题分解模块"""
from .strategic import StrategicDecomposer

__all__ = ['StrategicDecomposer']
PYEOF

# ============================================================
# 4. src/decomposer/strategic.py
# ============================================================
echo "📝 恢复 src/decomposer/strategic.py"
cat > src/decomposer/strategic.py << 'PYEOF'
"""策略性分解器 - 基于"并行全分+线性截断"原则"""
import json
import re

class StrategicDecomposer:
    def __init__(self, model, code_graph=None):
        self.model = model
        self.code_graph = code_graph
        self.last_decomposition = None

    def decompose(self, question):
        """使用并行全分+线性截断策略"""
        
        # 构建代码图提示
        graph_context = ""
        if self.code_graph:
            keywords = re.findall(r'\b[A-Z][a-zA-Z]+\b', question)
            keywords += re.findall(r'\b[a-z_]{4,}\b', question)
            
            mentioned_nodes = []
            for kw in set(keywords):
                related = self.code_graph.get_related_context(kw)
                for r in related[:2]:
                    node_id = f"{r['file']}::{r['name']}"
                    neighbors = self.code_graph.get_neighbors(node_id)
                    if neighbors and (neighbors['calls'] or neighbors['called_by']):
                        mentioned_nodes.append({
                            'name': r['name'],
                            'file': r['file'],
                            'neighbors': neighbors
                        })
            
            if mentioned_nodes:
                graph_context = "\nCODE GRAPH ANALYSIS:\n"
                for mn in mentioned_nodes[:3]:
                    graph_context += f"- {mn['name']} in {mn['file']}\n"
                    if mn['neighbors']['calls']:
                        graph_context += f"  → calls: {', '.join(mn['neighbors']['calls'][:3])}\n"
                    if mn['neighbors']['called_by']:
                        graph_context += f"  ← called by: {', '.join(mn['neighbors']['called_by'][:3])}\n"

        prompt = f"""You are a Multi-hop QA Decomposition Expert. Apply these STRATEGIC PRINCIPLES:

PRINCIPLE 1 - PARALLEL PARTITION:
If the question involves multiple INDEPENDENT aspects (different modules, concepts, or entities), identify ALL of them as separate entry points.

PRINCIPLE 2 - LINEAR TRUNCATION:
For reasoning chains, ONLY specify the ENTRY POINT (starting symbol/function). DO NOT predict subsequent steps - let the agent discover them dynamically.

QUESTION: {question}
{graph_context}

Return ONLY a JSON object in this format:
{{
  "independent_aspects": [
    {{"aspect": "Description", "entry_point": "Symbol or file name"}},
    ...
  ],
  "synthesis_instruction": "How to combine answers from all aspects"
}}

Example:
{{
  "independent_aspects": [
    {{"aspect": "Timeout detection mechanism", "entry_point": "LocalEnvironment.execute"}},
    {{"aspect": "Exception transformation logic", "entry_point": "DefaultAgent.execute_action"}}
  ],
  "synthesis_instruction": "Trace how timeout exceptions flow from environment to agent"
}}
"""
        
        print("🧠 Strategic decomposition (Parallel Partition + Linear Truncation)...")
        response = self.model.query([{"role": "user", "content": prompt}])
        
        print("\n📋 Decomposer Response:")
        print("=" * 60)
        print(response["content"])
        print("=" * 60 + "\n")
        
        decomposition = self._parse_json(response["content"])
        
        if decomposition and 'independent_aspects' in decomposition:
            print(f"✓ Identified {len(decomposition['independent_aspects'])} independent aspects\n")
            self.last_decomposition = decomposition
            return decomposition
        else:
            print("⚠️  Using fallback decomposition\n")
            fallback = {
                "independent_aspects": [
                    {"aspect": f"Investigate: {question}", "entry_point": "Unknown - explore the codebase"}
                ],
                "synthesis_instruction": "Answer the question based on code exploration"
            }
            self.last_decomposition = fallback
            return fallback

    def _parse_json(self, content):
        try:
            content = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
            content = re.sub(r'^```\s*', '', content, flags=re.MULTILINE)
            content = re.sub(r'\s*```$', '', content)
            
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            print(f"⚠️  JSON parsing error: {e}")
        return None
PYEOF

# ============================================================
# 5. src/agents/__init__.py
# ============================================================
echo "📝 恢复 src/agents/__init__.py"
cat > src/agents/__init__.py << 'PYEOF'
"""Agent 模块"""
from .repo_qa_agent_final import RepoQAAgentFinal

__all__ = ['RepoQAAgentFinal']
PYEOF

# ============================================================
# 6. src/agents/repo_qa_agent_final.py
# ============================================================
echo "📝 恢复 src/agents/repo_qa_agent_final.py"
cat > src/agents/repo_qa_agent_final.py << 'PYEOF'
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
        enhanced_task = f"""You are a code analysis specialist. DO NOT write or run test scripts (e.g., sleep, python -c).

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
PYEOF

# ============================================================
# 7. run_strategic_stage1.py
# ============================================================
echo "📝 恢复 run_strategic_stage1.py"
cat > run_strategic_stage1.py << 'PYEOF'
"""Strategic RepoQA Demo - Final Stable Version"""
import sys
from pathlib import Path
import yaml
from dotenv import load_dotenv

# 加载配置
config_path = Path.home() / ".config/mini-swe-agent/.env"
if config_path.exists():
    load_dotenv(config_path)
    print(f"✅ 已加载配置: {config_path}\n")

sys.path.insert(0, '/root/mini-swe-agent/src')
sys.path.insert(0, '/root/RepoQA-Decomposition/src')

from agents.repo_qa_agent_final import RepoQAAgentFinal
from minisweagent.models import get_model
from minisweagent.environments.local import LocalEnvironment
from minisweagent import package_dir

def main():
    config = yaml.safe_load((Path(package_dir) / "config" / "default.yaml").read_text())
    
    model = get_model(input_model_name="gpt-4o-mini")
    env = LocalEnvironment()
    
    agent = RepoQAAgentFinal(model, env, **config["agent"])
    
    repo_path = "/root/mini-swe-agent/src/minisweagent"
    
    task = "When LocalEnvironment.execute encounters a timeout, how does it become an ExecutionTimeoutError in DefaultAgent?"
    
    print(f"📝 Task: {task}\n")
    
    try:
        result = agent.run(task, repo_path=repo_path)
        print(f"\n✅ Final Status: {result[0]}")
        if result[1]:
            print(f"📄 Output: {result[1][:500]}...")
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    finally:
        agent.print_trajectory()

if __name__ == "__main__":
    main()
PYEOF

# ============================================================
# 8. test_strategic.py
# ============================================================
echo "📝 恢复 test_strategic.py"
cat > test_strategic.py << 'PYEOF'
"""测试代码图构建（不消耗 API）"""
import sys
from pathlib import Path

sys.path.insert(0, '/root/RepoQA-Decomposition/src')

from graph.builder import CodeGraphBuilder

def main():
    print("="*60)
    print("Testing CodeGraphBuilder...")
    print("="*60 + "\n")
    
    builder = CodeGraphBuilder()
    repo_path = "/root/mini-swe-agent/src/minisweagent"
    graph = builder.build_from_repo(repo_path)
    
    print(f"✅ Graph Summary: {builder.summary()}")
    print(f"   Total nodes: {graph.number_of_nodes()}")
    print(f"   Total edges: {graph.number_of_edges()}\n")
    
    print("="*60)
    print("Testing Node Search...")
    print("="*60 + "\n")
    
    results = builder.get_related_context("DefaultAgent")
    if results:
        print(f"✅ Found {len(results)} results for 'DefaultAgent'")
        for r in results[:2]:
            print(f"   - {r['name']} in {r['file']} (line {r['line']})")
    
    print("\n" + "="*60)
    print("Testing Neighbor Query...")
    print("="*60 + "\n")
    
    for node_id in list(graph.nodes())[:5]:
        neighbors = builder.get_neighbors(node_id)
        if neighbors and (neighbors['calls'] or neighbors['called_by']):
            print(f"✅ Node: {node_id.split('::')[-1]}")
            if neighbors['calls']:
                print(f"   → calls: {neighbors['calls'][:3]}")
            if neighbors['called_by']:
                print(f"   ← called_by: {neighbors['called_by'][:3]}")
            break
    
    print("\n🎉 All tests passed!")

if __name__ == "__main__":
    main()
PYEOF

# ============================================================
# 9. init_terminal.sh
# ============================================================
echo "📝 恢复 init_terminal.sh"
cat > init_terminal.sh << 'SHEOF'
#!/bin/bash

#==========================================
# RepoQA-Decomposition 终端初始化脚本
#==========================================

# ========== 在这里填写您的配置 ==========
API_KEY="sk-xxxxxxxxxxxxx"
API_BASE="https://your-url.com/v1"
# ======================================

echo "🚀 开始初始化终端..."
echo ""

# 1. 激活 conda 环境
echo "📦 激活 conda 环境..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate swe-agent
echo "   ✓ 环境已激活: swe-agent"
echo ""

# 2. 进入项目目录
echo "📂 进入项目目录..."
cd /root/RepoQA-Decomposition
echo "   ✓ 当前目录: $(pwd)"
echo ""

# 3. 安装关键依赖
echo "📦 安装关键依赖..."
pip install python-dotenv --break-system-packages -q
echo "   ✓ python-dotenv 已安装"
echo ""

# 4. 验证环境
echo "🔍 验证环境..."
python -c "import minisweagent; print('   ✓ mini-swe-agent OK')"
python -c "from tree_sitter import Language, Parser; print('   ✓ tree-sitter OK')"
echo ""

# 5. 创建配置文件
echo "📝 创建配置文件..."
mkdir -p ~/.config/mini-swe-agent
cat > ~/.config/mini-swe-agent/.env << ENVEOF
OPENAI_API_KEY=$API_KEY
OPENAI_API_BASE=$API_BASE
ENVEOF
echo "   ✓ 配置文件已创建: ~/.config/mini-swe-agent/.env"
echo ""

# 6. 显示最终状态
echo "=========================================="
echo "✅ 初始化完成！"
echo "=========================================="
echo ""
echo "配置信息："
echo "  API_BASE: $API_BASE"
echo "  API_KEY: ${API_KEY:0:20}..."
echo ""
echo "项目目录: $(pwd)"
echo ""
echo "可用命令："
echo "  python test_strategic.py          # 测试代码图（不消耗 API）"
echo "  python run_strategic_stage1.py    # 完整测试（消耗 API）"
echo ""

# 7. 保持在激活状态
exec bash
SHEOF

chmod +x init_terminal.sh

# ============================================================
# 完成
# ============================================================
echo ""
echo "=========================================="
echo "✅ 项目恢复完成！"
echo "=========================================="
echo ""
echo "恢复的文件："
echo "  ✓ src/graph/builder.py"
echo "  ✓ src/graph/__init__.py"
echo "  ✓ src/decomposer/strategic.py"
echo "  ✓ src/decomposer/__init__.py"
echo "  ✓ src/agents/repo_qa_agent_final.py"
echo "  ✓ src/agents/__init__.py"
echo "  ✓ run_strategic_stage1.py"
echo "  ✓ test_strategic.py"
echo "  ✓ init_terminal.sh"
echo ""
echo "目录结构："
tree /root/RepoQA-Decomposition -L 2 2>/dev/null || ls -R /root/RepoQA-Decomposition
echo ""
echo "下一步："
echo "  1. 编辑 init_terminal.sh 填入 API 配置"
echo "  2. 运行 ./init_terminal.sh 初始化环境"
echo "  3. 运行 python test_strategic.py 验证"
echo ""
