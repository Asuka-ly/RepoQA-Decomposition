"""代码图构建器测试"""
import pytest
from pathlib import Path
from src.graph import CodeGraph

def test_graph_build():
    """测试图构建基础功能"""
    graph = CodeGraph()
    
    # 使用 mini-swe-agent 作为测试仓库
    repo_path = "/root/mini-swe-agent/src/minisweagent"
    
    if not Path(repo_path).exists():
        pytest.skip("Test repository not found")
    
    graph.build(repo_path)
    
    # 验证图不为空
    assert graph.graph.number_of_nodes() > 0
    assert graph.graph.number_of_edges() > 0
    
    print(f"✓ Graph built: {graph.graph.number_of_nodes()} nodes, "
          f"{graph.graph.number_of_edges()} edges")

def test_search_symbol():
    """测试符号搜索"""
    graph = CodeGraph()
    repo_path = "/root/mini-swe-agent/src/minisweagent"
    
    if not Path(repo_path).exists():
        pytest.skip("Test repository not found")
    
    graph.build(repo_path)
    
    # 搜索已知符号
    results = graph.search_symbol("DefaultAgent", limit=5)
    
    assert len(results) > 0
    assert results[0]['name'] == "DefaultAgent"
    assert results[0]['type'] in ['class', 'function']
    
    print(f"✓ Found {len(results)} results for 'DefaultAgent'")

def test_get_neighbors():
    """测试邻居关系查询"""
    graph = CodeGraph()
    repo_path = "/root/mini-swe-agent/src/minisweagent"
    
    if not Path(repo_path).exists():
        pytest.skip("Test repository not found")
    
    graph.build(repo_path)
    
    # 查找 DefaultAgent
    results = graph.search_symbol("DefaultAgent", limit=1)
    
    if results:
        node_id = f"{results[0]['file']}::{results[0]['name']}"
        neighbors = graph.get_neighbors(node_id)
        
        assert neighbors is not None
        assert isinstance(neighbors, dict)
        assert 'calls' in neighbors
        assert 'called_by' in neighbors
        assert 'contains' in neighbors
        
        print(f"✓ DefaultAgent neighbors: {neighbors}")
    else:
        pytest.skip("DefaultAgent not found in graph")

def test_empty_repo():
    """测试空仓库不会崩溃"""
    graph = CodeGraph()
    
    # 创建临时空目录
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        graph.build(tmpdir)
        assert graph.graph.number_of_nodes() == 0
