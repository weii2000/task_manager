# Agent Eval

这个目录用于离线评估生产环境中的 Plan 和 Review 行为。Eval 单向依赖
`agent`，生产代码不得导入 `evals`。

## 运行

运行全部案例：

```bash
uv run python -m evals.runner
```

只运行指定案例：

```bash
uv run python -m evals.runner \
  --case plan_ambiguous_goal_clarifies \
  --case review_accepts_complete_plan
```

重复运行以观察稳定性：

```bash
uv run python -m evals.runner --repetitions 3
```

默认结果写入被 Git 忽略的 `eval-results/`。Runner 会调用 `.env` 中配置的
真实模型并产生 API 成本；普通 `pytest` 不会运行真实模型。

## 指标

- `structured_output`：模型输出是否通过生产 Pydantic Schema 和 Node 校验。
- `action_correctness`：下一步动作是否属于案例允许的动作集合。
- `constraint_retention`：通过“频率、上限、时长”等概念组判断明确约束是否
  保留，不依赖固定完整句子。
- `acceptance_criteria_coverage`：具有验收标准的任务比例。
- `tool_selection`：需要读取事实时是否选择了指定工具。
- `review_finding_*`：Review 是否发现预设类别且达到最低严重度。
- `question_count`：澄清回复中的问号数量；它是观察性软指标，不决定案例通过。
- `maximum_task_count`：案例期望的任务数量上限；用于观察过度拆分，不作为硬失败。

报告同时展示平均延迟、p50 和 p95。案例通过要求全部硬检查通过；软指标只
用于观察，不影响通过率。第一版不计算主观综合分，也不使用
LLM-as-a-Judge。

使用 `--repetitions` 时，报告中的 `Executions` 表示总执行次数，并额外按
`case_id` 输出稳定通过率；`Unique cases` 才是本次运行的不同案例数量。

生产 Provider 对格式校验失败最多纠正重试一次，因此 `structured_output`
表示重试后的最终成功率；首轮格式失败和重试恢复通过安全日志观察，日志不
记录原始模型响应。

## 维护规则

- 案例只使用人工构造的数据，不复制真实用户对话或长期记忆。
- 优先检查可客观判断的行为，不使用依赖固定措辞的脆弱断言。
- 一个案例尽量只验证一个主要失败模式。
- 长期记忆的直接采用与“记忆约束导致目标不可行”必须使用不同案例评估。
- 评估 Review 内容质量时，应在输入中提供已完成的项目查询结果；专门评估
  Tool 选择的案例除外。
- 修改 Prompt、Decision Schema 或 Flow 时，先运行同一版本案例并保存基线。
- 新增案例后，为 Scorer 的新规则补充确定性单元测试。
