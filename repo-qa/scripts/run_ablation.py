"""消融实验脚本"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, '/root/mini-swe-agent/src')
sys.path.insert(0, '/root/repo-qa')

from scripts.run_single import main as run_single
from src.config import ExperimentConfig

def run_ablation():
    """运行消融实验"""
    
    # 检查 API Key
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your-api-key-here":
        print("❌ Error: Please set OPENAI_API_KEY in .env file")
        return
    
    configs = ["baseline", "no_graph", "no_filter"]
    
    print("🔬 Starting Ablation Study")
    print("=" * 60)
    print(f"Configurations to test: {', '.join(configs)}")
    print("=" * 60)
    
    for config_name in configs:
        print(f"\n{'='*60}")
        print(f"🧪 Running: {config_name}")
        print(f"{'='*60}\n")
        
        # TODO: 这里需要修改 run_single 为可配置
        # 目前先跳过，留给后续完善
        print(f"⚠️  Skipping {config_name} (需要实现批量运行逻辑)")
    
    print("\n✅ Ablation study complete!")

if __name__ == "__main__":
    run_ablation()
