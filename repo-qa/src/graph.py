"""代码图构建器 - 静态分析核心"""
import networkx as nx
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
from pathlib import Path
from typing import List, Dict, Optional

class CodeGraph:
    """仓库级代码图：节点(类/函数)，边(调用/包含)"""
    
    def __init__(self):
        self.PY_LANGUAGE = Language(tspython.language())
        self.parser = Parser(self.PY_LANGUAGE)
        self.graph = nx.DiGraph()
        self.file_contents = {}

    @staticmethod
    def _make_node_id(rel_path: str, qname: str) -> str:
        return f"{rel_path}::{qname}"

    def build(self, repo_path: str):
        """扫描仓库并构建图"""
        repo_path = Path(repo_path)
        self.graph = nx.DiGraph()
        self.file_contents = {}
        
        python_files = list(repo_path.rglob("*.py"))
        
        # 第一遍：提取所有定义（节点）
        for py_file in python_files:
            try:
                relative_path = py_file.relative_to(repo_path)
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    code = f.read()
                self.file_contents[str(relative_path)] = code
                self._parse_definitions(str(relative_path), code)
            except Exception:
                pass
        
        # 第二遍：提取调用关系（边）
        for rel_path, code in self.file_contents.items():
            self._parse_calls(rel_path, code)
            
        return self.graph

    def _parse_definitions(self, rel_path: str, code: str):
        tree = self.parser.parse(bytes(code, "utf8"))
        
        def traverse(node, parent_context=None, current_class: Optional[str] = None):
            if node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = code[name_node.start_byte:name_node.end_byte]
                    node_id = self._make_node_id(rel_path, class_name)
                    self.graph.add_node(
                        node_id,
                        name=class_name,
                        qname=class_name,
                        file=rel_path,
                        type='class',
                        line=node.start_point[0] + 1,
                        class_name=class_name,
                    )
                    for child in node.children:
                        traverse(child, node_id, class_name)
                    return
            elif node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = code[name_node.start_byte:name_node.end_byte]
                    qname = f"{current_class}.{func_name}" if current_class else func_name
                    node_id = self._make_node_id(rel_path, qname)
                    self.graph.add_node(
                        node_id,
                        name=func_name,
                        qname=qname,
                        file=rel_path,
                        type='function',
                        line=node.start_point[0] + 1,
                        class_name=current_class,
                    )
                    if parent_context:
                        self.graph.add_edge(parent_context, node_id, type='contains')
                    return
            for child in node.children:
                traverse(child, parent_context, current_class)
        
        traverse(tree.root_node)

    def _parse_calls(self, rel_path: str, code: str):
        tree = self.parser.parse(bytes(code, "utf8"))

        def resolve_target(current_func_id: str, called_name: str) -> Optional[str]:
            """尽量减少同名函数误连边：类上下文优先 > 同文件 > 全局唯一。"""
            if current_func_id not in self.graph:
                return None

            current = self.graph.nodes[current_func_id]
            current_class = current.get("class_name")

            # 1) 类上下文优先
            if current_class:
                target_id = self._make_node_id(rel_path, f"{current_class}.{called_name}")
                if target_id in self.graph:
                    return target_id

            # 2) 同文件模块级函数
            same_file_target = self._make_node_id(rel_path, called_name)
            if same_file_target in self.graph:
                return same_file_target

            # 3) 全局候选（仅在唯一时连接）
            candidates = []
            for target, data in self.graph.nodes(data=True):
                if data.get("type") != "function":
                    continue
                if data.get("name") == called_name:
                    candidates.append(target)
            if len(candidates) == 1:
                return candidates[0]
            return None
        
        def find_calls(node, current_func_id):
            if node.type == 'call':
                func_node = node.child_by_field_name('function')
                if func_node:
                    called_text = code[func_node.start_byte:func_node.end_byte]
                    called_name = called_text.split('.')[-1]
                    target = resolve_target(current_func_id, called_name)
                    if target:
                        self.graph.add_edge(current_func_id, target, type='calls')
            for child in node.children:
                find_calls(child, current_func_id)

        def traverse(node, current_class: Optional[str] = None):
            if node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                class_name = code[name_node.start_byte:name_node.end_byte] if name_node else None
                for child in node.children:
                    traverse(child, class_name or current_class)
                return
            if node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = code[name_node.start_byte:name_node.end_byte]
                    qname = f"{current_class}.{func_name}" if current_class else func_name
                    func_id = self._make_node_id(rel_path, qname)
                    if func_id in self.graph.nodes():
                        find_calls(node, func_id)
                return
            for child in node.children:
                traverse(child, current_class)
        
        traverse(tree.root_node)

    def search_symbol(self, keyword: str, limit: int = 5) -> List[Dict]:
        """搜索匹配关键词的符号"""
        results = []
        for node, data in self.graph.nodes(data=True):
            name = data.get('name', '')
            qname = data.get('qname', name)
            if keyword.lower() in name.lower() or keyword.lower() in qname.lower():
                results.append(data)
        return results[:limit]

    def get_neighbors(self, node_id: str) -> Optional[Dict]:
        """获取节点的邻居关系"""
        if node_id not in self.graph: return None
        successors = list(self.graph.successors(node_id))
        predecessors = list(self.graph.predecessors(node_id))

        def label(n: str) -> str:
            data = self.graph.nodes.get(n, {})
            return data.get('qname') or n.split('::')[-1]

        return {
            'calls': [label(n) for n in successors if self.graph[node_id][n].get('type') == 'calls'],
            'called_by': [label(n) for n in predecessors if self.graph[n][node_id].get('type') == 'calls'],
            'contains': [label(n) for n in successors if self.graph[node_id][n].get('type') == 'contains']
        }
