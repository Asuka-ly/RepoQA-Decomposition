# RepoQA-Decomposition (repo-qa)

本项目是针对仓库级多跳问答（Multi-hop Repo-QA）的问题分解与引导系统。基于 [SWE-agent](https://arxiv.org/abs/2405.15793) 改进，集成了代码图静态分析和战略分解策略。

## 核心功能
- **并行全分 (Parallel Partition)**：识别仓库中的独立功能切面。
- **线性截断 (Linear Truncation)**：通过静态分析确定入口点，防止长链幻觉。
- **行为过滤器 (Command Filter)**：拦截 Agent 的无效测试行为（如 `sleep`）。
- **图知识注入 (Graph Injection)**：在观察结果中动态注入调用链信息。

## 快速开始
1. 运行配置脚本：`bash setup.sh`
2. 安装依赖：`pip install -r requirements.txt`
3. 配置 API：编辑 `.env` 文件。
4. 运行单次测试：`python scripts/run_single.py`
5. 运行消融实验：`python scripts/run_ablation.py`

## 投稿计划
- COLM 2025 (Deadline: 3.27)
- NeurIPS 2025 (Deadline: 5月)
