# RepoQA-Decomposition (repo-qa)

本项目是针对仓库级多跳问答（Multi-hop Repo-QA）的问题分解与引导系统。基于 [SWE-agent](https://arxiv.org/abs/2405.15793) 改进，集成了代码图静态分析和战略分解策略。

## 核心功能
- **并行全分 (Parallel Partition)**：识别仓库中的独立功能切面。
- **线性截断 (Linear Truncation)**：通过静态分析确定入口点，防止长链幻觉。
- **行为过滤器 (Command Filter)**：拦截 Agent 的无效测试行为（如 `sleep`）。
- **图知识注入 (Graph Injection)**：在观察结果中动态注入调用链信息。

## 快速开始
1. 运行配置脚本：`bash setup.sh`
   - 非交互模式：`bash setup.sh --yes`
   - 从指定密钥文件加载：`bash setup.sh --yes --env-file /path/to/secure.env`
2. 安装依赖：`pip install -r requirements.txt`
3. 配置 API：编辑 `.env` 文件。
4. 运行单次测试（默认走 SWE-QA 题目绑定）：`python scripts/run_single.py --question-file swe_qa_bench/swe_qa_0001.txt`
5. 运行消融实验：`python scripts/run_ablation.py --question-file q4_message_history_flow.txt`

可选网络参数（若环境必须走代理）：
- `python scripts/run_single.py --keep-proxy`
- `python scripts/run_ablation.py --keep-proxy`

离线模式（不调用外部 API）：
- `python scripts/run_single.py --offline --question-file q3_default_agent_action_flow.txt`
- `python scripts/run_ablation.py --offline --question-file q4_message_history_flow.txt`

轨迹质量检查：
- `python scripts/analyze_trajectory.py --config baseline`
- trajectory 会记录 `trajectory_schema_version` 与 `tool_calls`（工具调用轨迹）

批量测试（默认 SWE-QA；可回退 stage1）：
- `python scripts/run_batch.py --mode single --question-source swe_qa --all-questions`
- `python scripts/run_batch.py --mode both --question-source auto --all-questions`
- 仅跑 stage1: `python scripts/run_batch.py --mode ablation --question-source stage1 --all-questions`

离线冒烟实验（无外部 API）：
- `python scripts/run_offline_smoke.py`

SWE-QA-Bench 数据接入（用于后续实验/评估）：
- `python scripts/fetch_swe_qa_bench.py --max-questions 200`
- 复用已下载目录：`python scripts/fetch_swe_qa_bench.py --skip-clone --target-dir data/external/SWE-QA-Bench`
- 输出 `data/questions/swe_qa_bench/index.jsonl`，并保留每题 `repo/commit/instance_id` 绑定信息
- `run_single.py` 会按题目自动 clone+checkout 对应仓库提交（`--repo-path` 可手动覆盖）
- 运行示例：`python scripts/run_single.py --question-file swe_qa_bench/swe_qa_0001.txt`

完整在线测试手册（依赖安装/API 配置/批量测试/排查）：
- `docs/stage1_online_test_playbook.md`

可选网络参数（若环境必须走代理）：
- `python scripts/run_single.py --keep-proxy`
- `python scripts/run_ablation.py --keep-proxy`

离线模式（不调用外部 API）：
- `python scripts/run_single.py --offline --question-file q3_default_agent_action_flow.txt`
- `python scripts/run_ablation.py --offline --question-file q4_message_history_flow.txt`

轨迹质量检查：
- `python scripts/analyze_trajectory.py --config baseline`
- trajectory 会记录 `trajectory_schema_version` 与 `tool_calls`（工具调用轨迹）

批量测试（一次跑完 q1~q4）：
- `python scripts/run_batch.py --mode ablation --all-questions`
- `python scripts/run_batch.py --mode both --all-questions`

离线冒烟实验（无外部 API）：
- `python scripts/run_offline_smoke.py`

SWE-QA-Bench 数据接入（用于后续实验/评估）：
- `python scripts/fetch_swe_qa_bench.py --max-questions 200`
- 复用已下载目录：`python scripts/fetch_swe_qa_bench.py --skip-clone --target-dir data/external/SWE-QA-Bench`
- 默认会把题目抽取到 `data/questions/swe_qa_bench/`，并生成索引 `index.jsonl`
- 运行示例：`python scripts/run_single.py --question-file swe_qa_bench/swe_qa_0001.txt`

完整在线测试手册（依赖安装/API 配置/批量测试/排查）：
- `docs/stage1_online_test_playbook.md`

## 投稿计划
- COLM 2025 (Deadline: 3.27)
- NeurIPS 2025 (Deadline: 5月)


## Stage1 自我评审（当前版本）
- ✅ Question-Repo-Commit 绑定已贯通：fetch -> index -> run_single/run_batch。
- ✅ 提交门槛、子问题状态与最终答案提取在离线冒烟（strategic/vanilla）下均可稳定完成提交。
- ⚠️ 仍建议在线实验监控仓库缓存体积和 clone/fetch 失败重试策略（大规模 SWE-QA 批量时会更明显）。
