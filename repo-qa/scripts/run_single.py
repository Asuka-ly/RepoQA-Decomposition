"""单问题运行脚本"""
import os
import sys
import yaml
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加路径
sys.path.insert(0, '/root/mini-swe-agent/src')
sys.path.insert(0, '/root/repo-qa')

from minisweagent.models import get_model
from minisweagent.environments.local import LocalEnvironment
from minisweagent import package_dir
from src.agent import RepoQAAgent
from src.config import ExperimentConfig

def main():
    # 1. 检查 API Key
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your-api-key-here":
        print("❌ Error: Please set OPENAI_API_KEY in .env file")
        return
    
    # 2. 加载配置
    print("📋 Loading configuration...")
    exp_config = ExperimentConfig.from_yaml("configs/baseline.yaml")
    
    # 3. 初始化模型与环境
    print("🤖 Initializing model and environment...")
    model = get_model(input_model_name="gpt-4o")
    env = LocalEnvironment()
    
    # 加载 mini-swe-agent 配置
    agent_config_path = Path(package_dir) / "config" / "default.yaml"
    agent_config = yaml.safe_load(agent_config_path.read_text())
    
    # 4. 创建 Agent
    print("🎯 Creating RepoQA Agent...")
    agent = RepoQAAgent(model, env, exp_config, **agent_config["agent"])
    
    # 5. 加载问题
    repo_path = "/root/mini-swe-agent/src/minisweagent"
    task_file = Path("data/questions/q2_config_loading.txt")
    
    if not task_file.exists():
        print(f"❌ Error: Task file not found: {task_file}")
        return
    
    with open(task_file, 'r') as f:
        task = f.read()
    
    print(f"\n{'='*60}")
    print(f"📝 Running task from: {task_file}")
    print(f"{'='*60}\n")
    
    # 6. 运行
    try:
        result = agent.run(task, repo_path)
        
        # 兼容性处理返回值
        if isinstance(result, (list, tuple)):
            status = result[0]
            output = result[1] if len(result) > 1 else ""
        else:
            status = "Completed"
            output = str(result)
            
        print(f"\n✓ Final Status: {status}")
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
