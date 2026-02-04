"""消融实验：对比不同配置的效果"""
import sys
from pathlib import Path
import yaml
import json
from datetime import datetime

sys.path.insert(0, '/root/mini-swe-agent/src')
sys.path.insert(0, '/root/RepoQA-Decomposition/src')

from agents.repo_qa_agent_configurable import RepoQAAgentConfigurable, ExperimentConfig
from minisweagent.models import get_model
from minisweagent.environments.local import LocalEnvironment
from minisweagent import package_dir

def run_experiment(task, repo_path, config_name, exp_config):
    """运行单个实验"""
    print("\n" + "🔬"*30)
    print(f"   Experiment: {config_name}")
    print("🔬"*30 + "\n")
    
    config_path = Path(package_dir) / "config" / "default.yaml"
    config = yaml.safe_load(config_path.read_text())
    
    model = get_model(input_model_name="gpt-4o-mini")
    env = LocalEnvironment()
    
    agent = RepoQAAgentConfigurable(model, env, exp_config, **config["agent"])
    
    start_time = datetime.now()
    result = agent.run(task, repo_path=repo_path)
    end_time = datetime.now()
    
    # 收集统计信息
    stats = {
        "config_name": config_name,
        "total_messages": len(agent.messages),
        "final_status": result[0],
        "duration_seconds": (end_time - start_time).total_seconds(),
        "graph_injections": sum(1 for msg in agent.messages if "[GRAPH HINT]" in msg.get('content', '')),
        "config": {
            "graph_injection": exp_config.enable_graph_injection,
            "forbid_test": exp_config.forbid_test_writing,
            "synthesis_hint": exp_config.enable_synthesis_hint,
        }
    }
    
    return stats, agent

def main():
    repo_path = "/root/mini-swe-agent/src/minisweagent"
    
    task = """When LocalEnvironment.execute encounters a timeout, how does it become an ExecutionTimeoutError in DefaultAgent?

⚠️ IMPORTANT:
- All source code is in /root/mini-swe-agent/src
- Start with: cd /root/mini-swe-agent/src && explore
"""
    
    # 定义实验配置
    experiments = [
        ("Baseline (All ON)", ExperimentConfig()),  # 默认：全部开启
        
        ("No Graph Injection", lambda: (cfg := ExperimentConfig(), setattr(cfg, 'enable_graph_injection', False), cfg)[2]()),
        
        ("Forbid Test Writing", lambda: (cfg := ExperimentConfig(), setattr(cfg, 'forbid_test_writing', True), cfg)[2]()),
        
        ("Full Guided", lambda: (cfg := ExperimentConfig(), 
                                 setattr(cfg, 'forbid_test_writing', True),
                                 setattr(cfg, 'enable_synthesis_hint', True), 
                                 cfg)[2]()),
        
        ("Minimal (No Injection, No Guide)", lambda: (cfg := ExperimentConfig(), 
                                                      setattr(cfg, 'enable_graph_injection', False),
                                                      setattr(cfg, 'forbid_test_writing', False),
                                                      setattr(cfg, 'enable_synthesis_hint', False),
                                                      cfg)[2]()),
    ]
    
    results = []
    
    for config_name, config_factory in experiments:
        config = config_factory if isinstance(config_factory, ExperimentConfig) else config_factory()
        
        try:
            stats, agent = run_experiment(task, repo_path, config_name, config)
            results.append(stats)
            
            print(f"\n📊 {config_name} Stats:")
            print(f"  - Total Messages: {stats['total_messages']}")
            print(f"  - Graph Injections: {stats['graph_injections']}")
            print(f"  - Duration: {stats['duration_seconds']:.1f}s")
            print(f"  - Final Status: {stats['final_status']}")
            
        except KeyboardInterrupt:
            print("\n⚠️  Experiment interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Experiment failed: {e}")
            import traceback
            traceback.print_exc()
    
    # 保存结果
    output_file = f"ablation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to: {output_file}")
    
    # 打印对比表格
    print("\n" + "="*80)
    print("📊 ABLATION STUDY SUMMARY")
    print("="*80)
    print(f"{'Config':<30} {'Messages':<12} {'Injections':<12} {'Duration':<10} {'Status':<15}")
    print("-"*80)
    for r in results:
        print(f"{r['config_name']:<30} {r['total_messages']:<12} {r['graph_injections']:<12} {r['duration_seconds']:<10.1f} {r['final_status']:<15}")

if __name__ == "__main__":
    main()
