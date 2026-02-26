# Stage 1 现状评估与改造计划（RepoQA-Decomposition）

> 面向：blt（Stage 1 owner）  
> 目标：把当前“图增强的任务分解”推进到“图驱动的问题分解 + 可更新的推理控制”

---

## 1. 当前完成度评估（按研究主线）

### 1.1 框架与工程化：**已完成 75%（可复现）**

已有能力：
- 形成了 `vanilla` vs `strategic` 双 Agent 对照框架，且都能保存 trajectory。  
- 具备静态图构建（定义 + 调用边）、初始分解器、Prompt 工厂、命令过滤器。  
- 有单例运行和消融脚本，已有实验产物目录。

主要缺口：
- 缺少统一“评估入口脚本”去规模化跑 SWE-QA（你的 P0）。
- 缺少面向 RL 的轨迹规范（schema + 清洗规则 + 质量标签）。

### 1.2 “并行全分 + 线性截断”：**已完成 50%（有雏形）**

已有能力：
- Decomposer 输出 aspects，包含 `entry_point/symbols/priority`。  
- Prompt 中已要求“先读代码再回答”。

主要缺口：
- 现在的 aspect 语言仍偏“任务描述”，不是显式可验证“子问题（Question Form）”。
- `entry_point` 主要是 LLM 生成，不够“图约束化”。
- 还没有“分解质量自检”（可回答性、互斥性、覆盖性）。

### 1.3 图引导动态推理：**已完成 30%（当前更像后验提示）**

已有能力：
- GraphInjector 在读文件后给出邻居提示（calls/called_by）。

主要缺口（核心）：
- 图信息目前是“被动注入”，不是“决策约束”。
- Decomposer 与 Graph 的关系是弱耦合（graph context 可有可无）。
- 没有 update 机制：hint 命中后不会改变 aspect 状态与下一步策略。

### 1.4 只读安全：**已完成 40%（软约束为主）**

已有能力：
- Prompt + command filter + 系统反馈的软限制。

主要缺口：
- 尚未做“物理只读”（mount 或环境层的 write deny）。
- 目前仍可能有绕过风险（例如通过未列举命令组合写入）。

---

## 2. 你老师的 4 个问题：重要性排序与直接结论

### 最高优先级（必须先做）
1. **Q1 图融合不足（最关键）**  
   - 这是你方法论的“创新性主轴”；如果图只是提示增强，论文贡献会被审稿人判成 prompt engineering。  
   - 需要把图从“知识增强”升级成“分解生成约束 + 过程更新信号”。

2. **Q3 设计重点：如何 update（第二关键）**  
   - 没有 update，动态推理不可证；只剩“一次性 decomposition + 常规 ReAct”。  
   - 必须把每个 aspect 变成可更新状态机（open/in_progress/satisfied/blocked）。

### 中优先级（紧随其后）
3. **Q2 分解结果像任务不是问题（第三关键）**  
   - 这是评测可比性问题。子问题不显式，就无法衡量“分解是否正确”。  
   - 需要把 aspect 统一成 “Question + Evidence Requirement + Exit Criterion”。

4. **Q4 步数策略（第四关键）**  
   - 这是效率和稳定性问题，重要但可在前3项框架确定后再细化。  
   - 建议采用“模型尺寸感知 + 阶段预算”的折中方案，而非绝对逐步强约束。

---

## 3. 关键改造：从“图增强”变为“图驱动”

## 3.1 把 Decomposer 输出改成“显式子问题对象”

把当前：
- description / entry_point / symbols / priority

升级为：
- `sub_question`：一句可回答的问题（必须含问号）
- `hypothesis`：待验证假设（可被证伪）
- `entry_candidates`：图检索得到的 Top-k 入口
- `required_evidence`：至少 2 条证据类型（定义位置、调用路径、条件分支）
- `exit_criterion`：何时判定该子问题完成
- `status`：open/in_progress/satisfied/blocked

这样你就能把“任务分解”变成“问题分解”，并支持后续 update。

## 3.2 图约束前置到分解阶段（不是只在 observation 后注入）

建议新增两段强约束：
1. **Graph-grounded proposal**：每个子问题必须绑定至少一个图节点（node_id）。
2. **Graph consistency check**：若子问题提到符号在图里找不到，标记 `unresolved_symbol`，降低 priority 或转 fallback question。

效果：
- 让 decomposition 对图“有依赖”而不是“可选参考”。

## 3.3 引入 Aspect State Machine（回答 Q3: update）

每轮 action/observation 后做轻量更新：
- 命中 `required_evidence` +1
- 命中目标符号邻域 +1
- 出现冲突证据（与 hypothesis 相反）→ 标记 revise_needed
- 连续 N 步无增益 → blocked

触发器：
- `revise_needed` 或 `blocked` 时，调用 `decomposer.replan(partial_state, graph_delta)`。

这就是“图引导的动态推理”的最小可发表版本（MVP）。

---

## 4. Prompt/Tool 设计改造（回答 Q2）

## 4.1 Prompt 从“执行任务”切为“回答子问题”

把“ASPECT i: investigate ...”改成：
- `SubQ-i`: 明确问题
- `Needed Evidence`: 证据类型
- `Done when`: 退出条件

并在系统约束中要求：
- 任何结论必须绑定到一个 sub_question id。
- 最终答案按 sub_question 聚合后再 synthesis。

## 4.2 下一阶段改成工具调用接口（你老师要求）

建议抽 3 个可调用 tool：
- `plan_subquestions(question, graph_summary)`
- `update_subquestion_state(subq_state, new_observation, graph_hint)`
- `synthesize_answer(subq_states)`

优势：
- 轨迹结构化，天然适配 RL 的状态-动作-奖励接口。

---

## 5. 步数策略（回答 Q4）

不要简单要求“严格一步一步”；改为**预算化分配**：
- `global_budget`（总步数）
- `per_subq_soft_budget`
- `replan_reserved_budget`（保留重规划预算）

建议默认：
- 小窗口模型：高频总结，低 per-step 负载（例如 24~32 steps）。
- 大窗口模型：允许更长链，但每 5~6 步强制“证据压缩”。

并定义 early-stop 规则：
- 所有 sub_question 达到 exit_criterion 即提前提交；
- 若剩余预算不足且未完成，优先提交“高置信子集 + 未决项”。

---

## 6. 与你 ToDo 对齐的执行顺序（两周内）

### Sprint A（3~4 天，先打研究主线）
1. 改 Decomposer schema 为 `sub_question object`。  
2. 在 Agent 循环中加入 `aspect update` 与 `replan` 触发。  
3. Prompt 改为 SubQ 驱动并绑定证据与退出条件。

### Sprint B（3~4 天，跑规模实验）
4. 补 `batch_run_swe_qa.py`，先跑 50 题。  
5. 增加指标：
   - decomposition validity（格式+可回答性）
   - graph-grounding rate
   - update trigger rate / replan success rate
   - answer EM/F1（或任务定义指标）

### Sprint C（2~3 天，给 RL 交付资产）
6. 轨迹清洗与标准化导出（state/action/reward-ready JSONL）。  
7. 给每条轨迹打弱标签：证据充分度、是否过早提交、是否幻觉。

### 并行安全线（可穿插）
8. 环境层只读隔离 PoC（至少先在本地 docker mount `:ro` 方案验证）。

---

## 7. 你现在最该先做的三件事（精简版）

1. **先把 aspect 改成显式 sub-question + exit criterion（今天可开工）**。  
2. **实现每轮 update + 条件 replan（明后天）**。  
3. **立刻开始 50 题 batch 基线，边改边回归（不要等全做完）**。

这三件做完，你的 Stage 1 就不只是“可运行”，而是有论文主张可验证的实验闭环。

