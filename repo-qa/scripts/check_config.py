"""配置检查工具 - 验证环境是否正确配置"""
import sys
from pathlib import Path

# 添加 repo-qa 到路径
repo_qa_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_qa_root))

from src.utils import PATH_CONFIG
import os

def main():
    print("\n" + "="*60)
    print("🔍 RepoQA Configuration Check")
    print("="*60 + "\n")
    
    # 1. 路径检查
    print("📂 Path Validation:")
    path_ok = PATH_CONFIG.validate()
    print()
    
    # 2. API Key 检查
    print("🔑 API Key Validation:")
    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE")
    
    if api_key and api_key != "your-api-key-here":
        print(f"✓ OPENAI_API_KEY is set (length: {len(api_key)})")
    else:
        print("✗ OPENAI_API_KEY is NOT set or invalid")
        path_ok = False
    
    if api_base:
        print(f"✓ OPENAI_API_BASE: {api_base}")
    else:
        print("  (Using default OpenAI endpoint)")
    print()
    
    # 3. Python 环境检查
    print("🐍 Python Environment:")
    try:
        import minisweagent
        print(f"✓ mini-swe-agent: {minisweagent.__version__}")
    except ImportError as e:
        print(f"✗ mini-swe-agent NOT found: {e}")
        path_ok = False
    
    try:
        import tree_sitter
        try:
            import importlib.metadata
            ts_version = importlib.metadata.version("tree-sitter")
            print(f"✓ tree-sitter: {ts_version}")
        except:
            print("✓ tree-sitter: installed")
    except ImportError:
        print("✗ tree-sitter NOT found")
        path_ok = False
    
    try:
        import networkx
        print(f"✓ networkx: {networkx.__version__}")
    except ImportError:
        print("✗ networkx NOT found")
        path_ok = False
    
    print()
    
    # 4. 配置文件检查
    print("📋 Config Files:")
    config_dir = PATH_CONFIG.repo_qa_root / "configs"
    if config_dir.exists():
        configs = list(config_dir.glob("*.yaml"))
        for cfg in configs:
            print(f"✓ {cfg.name}")
    else:
        print("✗ configs/ directory not found")
        path_ok = False
    
    print()
    
    # 5. 测试数据检查
    print("📝 Test Data:")
    questions_dir = PATH_CONFIG.repo_qa_root / "data" / "questions"
    if questions_dir.exists():
        questions = list(questions_dir.glob("*.txt"))
        for q in questions:
            print(f"✓ {q.name}")
    else:
        print("✗ data/questions/ directory not found")
    
    print()
    
    # 最终结果
    print("="*60)
    if path_ok:
        print("✅ All checks passed! Ready to run experiments.")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
