"""知识注入器 - 动态引导推理"""
import re
from typing import Optional

class GraphInjector:
    """在观察结果中注入图邻居信息"""
    
    def __init__(self, code_graph: Optional['CodeGraph'], enabled: bool = True):
        self.code_graph = code_graph
        self.enabled = enabled
        self.injection_count = 0

    def inject(self, command: str, observation: str) -> str:
        if not self.enabled or not self.code_graph:
            return observation
        
        # 仅针对读取代码的操作进行注入
        if not any(verb in command for verb in ['cat', 'grep', 'head', 'tail']):
            return observation

        # 提取命令中的潜在符号
        symbols = re.findall(r'\b[A-Z][a-zA-Z]+\b', command) + re.findall(r'\b[a-z_]{5,}\b', command)
        
        for symbol in set(symbols):
            results = self.code_graph.search_symbol(symbol, limit=1)
            if results:
                data = results[0]
                node_id = f"{data['file']}::{data['name']}"
                neighbors = self.code_graph.get_neighbors(node_id)
                
                if neighbors and (neighbors['calls'] or neighbors['called_by']):
                    hint = f"\n\n🔍 [GRAPH HINT] Context for '{symbol}':"
                    if neighbors['calls']:
                        hint += f"\n  → Calls: {', '.join(neighbors['calls'][:5])}"
                    if neighbors['called_by']:
                        hint += f"\n  ← Called by: {', '.join(neighbors['called_by'][:3])}"
                    hint += "\n  💡 These might be your next reasoning hops."
                    
                    self.injection_count += 1
                    return observation + hint
        
        return observation
