# RepoQA-Decomposition (repo-qa)

面向仓库级多跳问答的 Stage1 实验工程。当前默认执行路径：**SWE-QA 题目绑定 repo+commit**。

## 快速开始（主路径）
```bash
bash setup.sh --yes
pip install -r requirements.txt
python scripts/fetch_swe_qa_bench.py --max-questions 200
python scripts/run_single.py --question-file swe_qa_bench/swe_qa_0001.txt
python scripts/run_batch.py --mode single --question-source swe_qa --all-questions
```

## 回退路径（stage1 本地题库）
```bash
python scripts/run_batch.py --mode single --question-source stage1 --all-questions
```

## 三个核心脚本
- `scripts/fetch_swe_qa_bench.py`：拉取 SWE-QA，并在 `data/questions/swe_qa_bench/index.jsonl` 写入 `repo/commit/instance_id` 绑定。
- `scripts/run_single.py`：按题目索引动态 clone+checkout 对应仓库提交，再执行单题。
- `scripts/run_batch.py`：批量执行入口，支持 `--question-source swe_qa|stage1|auto`。

## 当前边界与已知风险
- 默认推荐 SWE-QA 路径；stage1 仅用于回归或离线兜底。
- 大规模批量时需关注仓库缓存体积、clone/fetch 重试与网络稳定性。
- 若在线 API 不稳定，可先执行 `python scripts/run_offline_smoke.py` 验证核心链路。

## 文档导航
- 单页任务书：`docs/stage1_task_brief.md`
- 交接说明：`docs/stage1_v2_handoff.md`
- 在线操作与排障：`docs/stage1_online_test_playbook.md`
