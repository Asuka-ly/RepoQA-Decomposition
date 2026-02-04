#!/usr/bin/env python
"""一键运行所有单元测试"""
import subprocess
import sys
from pathlib import Path

def run_tests():
    """运行所有测试"""
    print("🧪 Running RepoQA Unit Tests")
    print("=" * 60)
    print()
    
    # 切换到项目根目录
    project_root = Path(__file__).parent.parent
    
    # 设置 PYTHONPATH
    import os
    os.environ['PYTHONPATH'] = str(project_root)
    
    # 运行 pytest
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--color=yes",
    ]
    
    try:
        result = subprocess.run(cmd, cwd=project_root)
        
        print()
        print("=" * 60)
        if result.returncode == 0:
            print("✅ All tests passed!")
        else:
            print("❌ Some tests failed. See details above.")
            sys.exit(1)
    
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
