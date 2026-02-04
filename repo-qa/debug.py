"""调试：查看 Agent 到底收到了什么 Prompt"""
import sys
sys.path.insert(0, '/root/mini-swe-agent/src')
sys.path.insert(0, '/root/repo-qa')

import yaml
from pathlib import Path
from minisweagent.models import get_model
from minisweagent.environments.local import LocalEnvironment
from minisweagent import package_dir
from src.agent import RepoQAAgent
from src.config import ExperimentConfig

# 1. 初始化
exp_config = ExperimentConfig.from_yaml("configs/baseline.yaml")
model = get_model(input_model_name="gpt-4o-mini")
env = LocalEnvironment()

agent_config_path = Path(package_dir) / "config" / "default.yaml"
agent_config = yaml.safe_load(agent_config_path.read_text())

# 2. 查看 Agent 配置
print("="*60)
print("📋 Agent Configuration from mini-swe-agent:")
print("="*60)
print(yaml.dump(agent_config, indent=2))
print("\n")

# 3. 创建 Agent
agent = RepoQAAgent(model, env, exp_config, **agent_config["agent"])

# 4. 查看 Agent 的初始消息
print("="*60)
print("📨 Agent's Initial Messages:")
print("="*60)
if hasattr(agent, 'messages'):
    for i, msg in enumerate(agent.messages):
        print(f"\nMessage {i}:")
        print(f"  Role: {msg['role']}")
        print(f"  Content Preview: {msg['content'][:500]}")
        print("  ...")
elif hasattr(agent, 'history'):
    for i, msg in enumerate(agent.history):
        print(f"\nMessage {i}:")
        print(f"  Role: {msg.get('role', 'N/A')}")
        print(f"  Content Preview: {str(msg.get('content', ''))[:500]}")
        print("  ...")
else:
    print("No messages or history found yet")
