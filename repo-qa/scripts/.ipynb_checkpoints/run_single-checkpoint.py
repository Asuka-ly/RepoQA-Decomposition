"""单问题运行脚本 - 适配新架构"""
import os
import sys
from pathlib import Path
import yaml

# ===== 网络修复：清除 Autodl 代理 =====
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("all_proxy", None)

# 禁用 SSL 验证（应对代理问题）
import litellm
litellm.ssl_verify = False

# ===== 路径配置 =====
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.utils import PATH_CONFIG

# ===== 导入新架构的 Agent =====
from src.agents import StrategicRepoQAAgent  # 使用带分解的版本
from src.config import ExperimentConfig

from minisweagent.models import get_model
from minisweagent.environments.local import LocalEnvironment
from minisweagent import package_dir

def main():
    print("\n" + "="*60)
    print("🔍 Validating environment...")
    print("="*60 + "\n")
    
    if not PATH_CONFIG.validate():
        print("\n❌ Path validation failed!")
        return
    
    # 检查 API Key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-api-key-here":
        print("❌ Error: Please set OPENAI_API_KEY in .env file")
        return
    
    print(f"✓ API Key loaded (length: {len(api_key)})")
    
    # 加载配置
    config_path = PATH_CONFIG.repo_qa_root / "configs" / "baseline.yaml"
    print(f"\n📋 Loading config from: {config_path}")
    exp_config = ExperimentConfig.from_yaml(str(config_path))
    print(f"✓ Config loaded: {exp_config.name}")
    
    # 初始化模型
    print("\n🤖 Initializing model and environment...")
    model_name = getattr(exp_config, 'model_name', 'gpt-4o')
    
    # 强制添加 openai/ 前缀
    if not model_name.startswith(('openai/', 'anthropic/', 'azure/')):
        model_name = f"openai/{model_name}"
    
    print(f"🤖 Initializing model: {model_name}")
    
    api_base = os.getenv("OPENAI_API_BASE")
    if api_base:
        print(f"   Using API Base: {api_base}")
        os.environ["OPENAI_API_BASE"] = api_base
    
    model = get_model(input_model_name=model_name)
    env = LocalEnvironment()
    
    # 加载 mini-swe-agent 配置
    agent_config_path = Path(package_dir) / "config" / "default.yaml"
    agent_config = yaml.safe_load(agent_config_path.read_text())
    
    # 创建 Agent
    print("🎯 Creating RepoQA Agent...")
    agent = StrategicRepoQAAgent(model, env, exp_config, **agent_config["agent"])
    
    # 加载测试问题
    repo_path = PATH_CONFIG.get_test_repo_path()
    task_file = PATH_CONFIG.repo_qa_root / "data" / "questions" / "q2_config_loading.txt"
    
    if not task_file.exists():
        print(f"❌ Error: Task file not found: {task_file}")
        return
    
    with open(task_file, 'r') as f:
        task = f.read()
    
    print(f"\n{'='*60}")
    print(f"📝 Running task from: {task_file.name}")
    print(f"🎯 Target repo: {repo_path}")
    print(f"{'='*60}\n")
    
    # 运行
    try:
        result = agent.run(task, repo_path)
        
        if isinstance(result, (list, tuple)):
            status = result[0]
        else:
            status = "Completed"
        
        print(f"\n✓ Final Status: {status}")
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
