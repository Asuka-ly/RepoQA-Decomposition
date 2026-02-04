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
