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
