import sys
sys.path.insert(0, '/root/mini-swe-agent/src')
sys.path.insert(0, '/root/RepoQA-Decomposition/src')

from agents.repo_qa_agent_configurable import RepoQAAgentConfigurable, ExperimentConfig
from minisweagent.models import get_model
from minisweagent.environments.local import LocalEnvironment
import yaml
from pathlib import Path
from minisweagent import package_dir

# 创建配置：禁用图注入 + 禁止测试
config = ExperimentConfig()
config.enable_graph_injection = False
config.forbid_test_writing = True

model = get_model(input_model_name="gpt-4o-mini")
env = LocalEnvironment()

agent_config = yaml.safe_load((Path(package_dir) / "config" / "default.yaml").read_text())
agent = RepoQAAgentConfigurable(model, env, config, **agent_config["agent"])

task = """When LocalEnvironment.execute encounters a timeout, how does it become an ExecutionTimeoutError in DefaultAgent?
⚠️ All source code is in /root/mini-swe-agent/src, start there."""

result = agent.run(task, repo_path="/root/mini-swe-agent/src/minisweagent")
agent.print_trajectory()
