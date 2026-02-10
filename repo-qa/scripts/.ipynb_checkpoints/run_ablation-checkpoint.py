"""消融实验脚本 - 完整版"""
import os
import sys
from pathlib import Path
import yaml
import json
from datetime import datetime

# ===== 网络修复（关键！）=====
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("all_proxy", None)

import litellm
litellm.ssl_verify = False

# ===== 路径配置 =====
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.utils import PATH_CONFIG
from src.agents import StrategicRepoQAAgent, VanillaRepoQAAgent
from src.config import ExperimentConfig

from minisweagent.models import get_model
from minisweagent.environments.local import LocalEnvironment
from minisweagent import package_dir

def run_single_experiment(agent_class, config_name, task, repo_path):
    """运行单个实验"""
    print("\n" + "🔬"*30)
    print(f"   Running: {config_name}")
    print("🔬"*30 + "\n")
    
    # 加载配置
    config_path = PATH_CONFIG.repo_qa_root / "configs" / f"{config_name}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    
    exp_config = ExperimentConfig.from_yaml(str(config_path))
    
    # 初始化模型
    model_name = getattr(exp_config, 'model_name', 'gpt-5-mini')
    if not model_name.startswith(('openai/', 'anthropic/', 'azure/')):
        model_name = f"openai/{model_name}"
    
    print(f"🤖 Initializing model: {model_name}")
    
    model = get_model(input_model_name=model_name)
    env = LocalEnvironment()
    
    # 加载 agent 配置
    agent_config_path = Path(package_dir) / "config" / "default.yaml"
    agent_config = yaml.safe_load(agent_config_path.read_text())
    
    # 创建 Agent
    agent = agent_class(model, env, exp_config, **agent_config["agent"])
    
    # 运行
    start = datetime.now()
    try:
        result = agent.run(task, repo_path)
        duration = (datetime.now() - start).total_seconds()
        
        # 收集结果
        stats = agent._get_stats()
        stats['config_name'] = config_name
        stats['duration'] = duration
        stats['status'] = result[0] if isinstance(result, tuple) else "Completed"
        
        return stats
    except Exception as e:
        duration = (datetime.now() - start).total_seconds()
        return {
            'config_name': config_name,
            'total_steps': 0,
            'viewed_files': 0,
            'duration': duration,
            'status': f"Failed: {str(e)[:50]}"
        }
    
    finally:
        # ===== 清理实验现场（关键！）=====
        cleanup_experiment_artifacts(repo_path)

def cleanup_experiment_artifacts(repo_path: str):
    """清理 Agent 在目标仓库中留下的文件"""
    import subprocess
    
    # 定义可能的"垃圾文件"模式
    artifact_patterns = [
        "*.txt",  # 例如 YAML_config_flow.txt
        "summary.*",
        "config_*.txt",
        "analysis_*.txt",
        "FINAL_ANSWER*",
    ]
    
    for pattern in artifact_patterns:
        try:
            # 查找并删除匹配的文件
            cmd = f"find {repo_path} -maxdepth 1 -type f -name '{pattern}' -delete"
            subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
        except:
            pass
    
    print(f"🧹 Cleaned up experiment artifacts in {repo_path}")


def main():
    # 测试问题
    task_file = PATH_CONFIG.repo_qa_root / "data" / "questions" / "q2_config_loading.txt"
    with open(task_file) as f:
        task = f.read()
    
    repo_path = PATH_CONFIG.get_test_repo_path()
    
    # 实验配置
    experiments = [
        (StrategicRepoQAAgent, "baseline", "✅ With Decomposition + Graph"),
        (VanillaRepoQAAgent, "vanilla", "❌ Without Decomposition"),
    ]
    
    results = []
    
    for agent_class, config_name, description in experiments:
        print(f"\n{'='*60}")
        print(f"🧪 Experiment: {description}")
        print(f"{'='*60}")
        
        try:
            stats = run_single_experiment(agent_class, config_name, task, repo_path)
            results.append(stats)
            
            print(f"\n📊 Results:")
            print(f"  - Steps: {stats['total_steps']}")
            print(f"  - Files Viewed: {stats['viewed_files']}")
            print(f"  - Duration: {stats['duration']:.1f}s")
            print(f"  - Status: {stats['status']}")
            if 'total_injections' in stats:
                print(f"  - Graph Injections: {stats['total_injections']}")
            
        except Exception as e:
            print(f"\n❌ Failed: {e}")
            import traceback
            traceback.print_exc()
    
    # 保存对比结果
    output_dir = PATH_CONFIG.repo_qa_root / "experiments" / "comparison_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"ablation_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*60}")
    print("📊 ABLATION STUDY SUMMARY")
    print(f"{'='*60}")
    print(f"{'Config':<30} {'Steps':<10} {'Files':<10} {'Duration':<10}")
    print("-"*60)
    for r in results:
        print(f"{r['config_name']:<30} {r['total_steps']:<10} {r['viewed_files']:<10} {r['duration']:<10.1f}")
    
    print(f"\n✅ Results saved to: {output_file}")

if __name__ == "__main__":
    main()
