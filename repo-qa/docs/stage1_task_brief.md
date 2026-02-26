# Stage1 单页任务书（TL;DR）

## 项目目标（3行）
- 以 **SWE-QA 题目绑定的 repo+commit** 作为 Stage1 默认执行路径。
- 保持 `fetch -> index -> run_single/run_batch` 一致，避免“题目与代码仓错配”。
- 在最小测试闭环下保证可复现、可交接、可快速排障。

## 当前状态
**已完成**
- `fetch_swe_qa_bench.py` 已写入 `repo/commit/instance_id` 到索引。
- `run_single.py` 会按题目绑定动态 clone + checkout（支持 `--repo-path` 覆盖）。
- `run_batch.py` 支持 `--question-source swe_qa|stage1|auto`。
- offline smoke 在当前 submit gate 下可稳定结束（strategic/vanilla）。

**未完成/持续观察**
- 大规模批量时仓库缓存增长与 clone/fetch 重试策略仍需观察。
- 在线 API 稳定性和代理环境差异仍可能影响吞吐。

## 今日优先级 Top3
1. 统一文档语义：默认 SWE-QA，stage1 仅回退。
2. 保持“README + 本文档”即可启动主流程。
3. 维持最小测试闭环常绿（batch/binding/offline smoke）。

## 最小运行命令（SWE-QA 主路径）
```bash
cd repo-qa
bash setup.sh --yes
pip install -r requirements.txt
python scripts/fetch_swe_qa_bench.py --max-questions 200
python scripts/run_single.py --question-file swe_qa_bench/swe_qa_0001.txt
python scripts/run_batch.py --mode single --question-source swe_qa --all-questions
```

## 验收标准（3条）
- 只看 `docs/stage1_task_brief.md + readme.md`，可完成 SWE-QA 主流程。
- `run_batch`/`run_single` 命令示例全部使用 `--question-source` 语义。
- 最小测试与 offline smoke 可通过。

## 风险与回滚点
- **风险**：网络/API 抖动导致在线实验失败；仓库下载失败导致绑定链路中断。
- **回滚点**：在线失败时立即切 `--offline`，并用 `--question-source stage1` 做本地回归。
