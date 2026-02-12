"""单问题运行脚本 - 适配新架构"""
import os
import sys
import argparse
from pathlib import Path
import yaml

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
from minisweagent.models.test_models import DeterministicModel
from minisweagent.environments.local import LocalEnvironment
from minisweagent import package_dir

def _configure_network(keep_proxy: bool):
    """网络配置：默认清除代理；必要时可保留。"""
    if not keep_proxy:
        for key in [
            "http_proxy", "https_proxy", "all_proxy",
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE",
        ]:
            os.environ.pop(key, None)


def parse_args():
    parser = argparse.ArgumentParser(description="Run single RepoQA experiment")
    parser.add_argument("--keep-proxy", action="store_true", help="Do not clear proxy env vars")
    parser.add_argument("--config", default="baseline", help="Config name in repo-qa/configs")
    parser.add_argument("--question-file", default="q2_config_loading.txt", help="Question filename in data/questions")
    parser.add_argument("--repo-path", default=None, help="Override target repository path")
    parser.add_argument("--offline", action="store_true", help="Use deterministic offline model (no external API)")
    return parser.parse_args()


def _offline_outputs(repo_path: str):
    decomp_json = (
        '{"sub_questions":[{"id":"SQ1","sub_question":"How does DefaultAgent parse and execute actions?",'
        '"hypothesis":"parse_action validates bash action before execute",'
        '"entry_candidates":["agents/default.py::DefaultAgent.parse_action"],'
        '"symbols":["DefaultAgent","parse_action"],'
        '"required_evidence":["definition location","call path"],'
        '"exit_criterion":"2 grounded evidence items","status":"open","priority":1}],'
        '"synthesis":"Combine parser and run loop","estimated_hops":2,"unresolved_symbols":[]}'
    )
    return [
        decomp_json,
        f'Find DefaultAgent\n```bash\ncd {repo_path} && rg "class DefaultAgent" agents/default.py\n```',
        f'Find parse_action line\n```bash\ncd {repo_path} && rg -n "def parse_action" agents/default.py\n```',
        f"Read parse_action with lines\n```bash\ncd {repo_path} && nl -ba agents/default.py | sed -n '120,180p'\n```",
        f"Read run loop with lines\n```bash\ncd {repo_path} && nl -ba agents/default.py | sed -n '180,250p'\n```",
        (
            "## FINAL ANSWER\n"
            "`DefaultAgent.parse_action` is defined in `agents/default.py` and its line location is confirmed via `rg -n`; "
            "the execution/observation handling is in `agents/default.py:131`, and parsing is in `agents/default.py:116`."
            "\n```bash\necho COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n```"
        ),
    ]



def main():
    args = parse_args()
    _configure_network(keep_proxy=args.keep_proxy)

    print("\n" + "="*60)
    print("🔍 Validating environment...")
    print("="*60 + "\n")
    
    if not PATH_CONFIG.validate():
        print("\n❌ Path validation failed!")
        return
    
    if not args.offline:
        # 检查 API Key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your-api-key-here":
            print("❌ Error: Please set OPENAI_API_KEY in .env file")
            return
        print(f"✓ API Key loaded (length: {len(api_key)})")
    else:
        print("✓ Offline mode enabled: deterministic model")
    
    # 加载配置
    config_path = PATH_CONFIG.repo_qa_root / "configs" / f"{args.config}.yaml"
    print(f"\n📋 Loading config from: {config_path}")
    if not config_path.exists():
        print(f"❌ Error: Config file not found: {config_path}")
        return
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
    
    repo_path = args.repo_path or PATH_CONFIG.get_test_repo_path()
    if args.offline:
        model = DeterministicModel(outputs=_offline_outputs(repo_path))
    else:
        model = get_model(input_model_name=model_name)
    env = LocalEnvironment()
    
    # 加载 mini-swe-agent 配置
    agent_config_path = Path(package_dir) / "config" / "default.yaml"
    agent_config = yaml.safe_load(agent_config_path.read_text())
    
    # 创建 Agent
    print("🎯 Creating RepoQA Agent...")
    agent = StrategicRepoQAAgent(model, env, exp_config, **agent_config["agent"])
    
    # 加载测试问题
    repo_path = args.repo_path or PATH_CONFIG.get_test_repo_path()
    task_file = PATH_CONFIG.repo_qa_root / "data" / "questions" / args.question_file
    
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
