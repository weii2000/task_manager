# Agent Eval

这个目录包含两层离线评估。Eval 单向依赖 `agent`，生产代码不得导入
`evals`。

- **Node Eval**：单次调用 Plan 或 Review，适合定位 Prompt、Schema 和决策质量。
- **Workflow Eval**：运行生产 `Flow`，覆盖暂停恢复、工具往返、重规划和确认。

## 运行

运行全部 Node 案例：

```bash
uv run python -m evals.node_runner
```

只运行指定 Node 案例：

```bash
uv run python -m evals.node_runner \
  --case plan_ambiguous_goal_clarifies \
  --case review_accepts_complete_plan
```

重复运行以观察稳定性：

```bash
uv run python -m evals.node_runner --repetitions 3
```

运行全部 Workflow 案例：

```bash
uv run python -m evals.workflow_runner
```

也可以显式选择一个 Workflow：

```bash
uv run python -m evals.workflow_runner \
  --case blocking_review_replans_then_confirms \
  --repetitions 3
```

默认结果分别写入被 Git 忽略的 `eval-results/node/` 和
`eval-results/workflow/`。Runner 会调用 `.env` 中配置的真实模型并产生
API 成本；普通 `pytest` 不会运行真实模型。

两个入口有意分开：修改单个节点时跑 Node Eval，修改状态转换、工具或 Flow
时跑 Workflow Eval。当前没有额外的统一调度器；CI 需要同时运行时直接顺序
执行两个命令即可。

## 指标

- `structured_output`：模型输出是否通过生产 Pydantic Schema 和 Node 校验。
- `action_correctness`：下一步动作是否属于案例允许的动作集合。
- `constraint_retention`：通过“频率、上限、时长”等概念组判断明确约束是否保留，不依赖固定完整句子。
- `acceptance_criteria_coverage`：具有验收标准的叶子任务比例；带子任务的
  分组任务不计入分母。
- `tool_selection`：需要读取事实时是否选择了指定工具。
- `review_finding_*`：Review 是否发现预设类别且达到最低严重度。
- `question_count`：澄清回复中的问号数量；它是观察性软指标，不决定案例通过。
- `maximum_task_count`：案例期望的任务数量上限；用于观察过度拆分，不作为硬失败。

两类报告使用相同的顶层顺序和 Summary 结构，包括平均延迟、p50、p95、
案例稳定性和各项指标。时间与结果文件名统一使用 UTC；JSON 中使用 ISO 8601
的 `Z` 后缀。查看本地时间时需要进行时区换算。报告中的
`current_time_utc` 是本次模型推理使用的固定参考时间。

案例通过要求全部硬检查通过；软指标只用于观察，不影响通过率。第一版不计算
主观综合分，也不使用
LLM-as-a-Judge。

Workflow Eval 将最终阶段、必要动作、最终计划质量和禁止编造日期作为硬指标；
完整 `decision_path`、精确工具调用次数和模型调用预算是软指标。工具返回值
来自案例 fixture，因此它是 Flow 级集成评估，不是包含 HTTP 与真实 MySQL
的系统 E2E。

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
- 模型 API 没有可靠的实时系统时钟。时间敏感案例必须显式提供日期；用户未
  提供日期或相对期限时，应检查模型没有自行编造绝对日期。生产 Prompt 会在
  `current_context.current_time_utc` 中提供当前 UTC 时间，用于解析明确的
  相对期限；Eval suite 使用固定值，避免案例随着真实日期变化而失效。
- 修改 Prompt、Decision Schema 或 Flow 时，先运行同一版本案例并保存基线。
- 新增案例后，为 Scorer 的新规则补充确定性单元测试。
