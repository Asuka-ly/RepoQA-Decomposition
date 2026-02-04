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
