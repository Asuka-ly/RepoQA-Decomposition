"""Strategic RepoQA Demo - Final Stable Version"""
import sys
from pathlib import Path
import yaml
from dotenv import load_dotenv

# 加载配置
config_path = Path.home() / ".config/mini-swe-agent/.env"
if config_path.exists():
    load_dotenv(config_path)
    print(f"✅ 已加载配置: {config_path}\n")

sys.path.insert(0, '/root/mini-swe-agent/src')
sys.path.insert(0, '/root/RepoQA-Decomposition/src')

from agents.repo_qa_agent_final import RepoQAAgentFinal
from minisweagent.models import get_model
from minisweagent.environments.local import LocalEnvironment
from minisweagent import package_dir

def main():
    config = yaml.safe_load((Path(package_dir) / "config" / "default.yaml").read_text())
    
    model = get_model(input_model_name="gpt-5.1-mini")
    env = LocalEnvironment()
    
    agent = RepoQAAgentFinal(model, env, **config["agent"])
    
    repo_path = "/root/mini-swe-agent/src/minisweagent"
    
    task = "When running mini-swe-agent, how do LocalEnvironment (local command execution) and DockerEnvironment (container command execution) implement the execute method respectively, and how does DefaultAgent uniformly handle the execution results returned by these two environments? Note: All core source code is in /root/mini-swe-agent/src, please cd to this directory first and then explore."
    
    print(f"📝 Task: {task}\n")
    
    try:
        result = agent.run(task, repo_path=repo_path)
        print(f"\n✅ Final Status: {result[0]}")
        if result[1]:
            print(f"📄 Output: {result[1][:500]}...")
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    finally:
        agent.print_trajectory()

if __name__ == "__main__":
    main()
