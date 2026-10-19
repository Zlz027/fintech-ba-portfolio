# SQL 技能证明：金融风控数据查询集

## 证明什么技能

独立完成数据库建表、数据导入，使用高阶 SQL（多表 JOIN、窗口函数、CTE、子查询）解决真实风控取数与指标计算问题。

## 项目结构

```text
skills-proof/03-sql/
├── cs-training.csv      # GMSC（Give Me Some Credit）原始数据，150,000 条客户记录
├── setup.sql            # 建表 + 数据导入脚本（可重复执行，幂等）
├── queries.sql          # 15 个业务查询（基础聚合 / JOIN / 窗口函数 / CTE / 子查询）
├── credit.db            # 已构建好的 SQLite 数据库（删掉它即可按下方步骤重建）
├── images/              # 关键查询的终端运行结果截图
│   ├── join_score_band.png
│   ├── window_function_rownumber.png
│   ├── window_function_cumulative.png
│   ├── window_function_ntile.png
│   ├── cte_nested.png
│   ├── render_terminal.py   # 终端风格截图渲染器（工具脚本）
│   └── shots.py             # 5 张截图的生成脚本（工具脚本）
├── README.md
└── .gitignore             # 推送 GitHub 时忽略可再生的 credit.db
```

## 数据说明

GMSC（Give Me Some Credit）是 Kaggle 经典信贷违约预测竞赛数据集，150,000 条客户记录，预测目标为两年内是否发生严重拖欠（`SeriousDlqin2yrs`）。整体违约率约 6.68%，属于典型的非平衡样本。

| 字段（snake_case） | 原版 Kaggle 字段 | 含义 |
|---|---|---|
| `serious_dlqin2yrs` | SeriousDlqin2yrs | 两年内严重违约（1=是，目标变量） |
| `revolving_utilization` | RevolvingUtilizationOfUnsecuredLines | 信用利用率（总额度使用比例） |
| `age` | age | 年龄 |
| `number_of_time_30_59_days_past_due_not_worse` | NumberOfTime30-59DaysPastDueNotWorse | 逾期 30-59 天次数 |
| `debt_ratio` | DebtRatio | 债务收入比 |
| `monthly_income` | MonthlyIncome | 月收入（缺失 29,731 条，19.74%） |
| `number_of_open_credit_lines_and_loans` | NumberOfOpenCreditLinesAndLoans | 未结清信用账户/贷款数 |
| `number_of_times_90_days_late` | NumberOfTimes90DaysLate | 逾期 90 天以上次数 |
| `number_real_estate_loans_or_lines` | NumberRealEstateLoansOrLines | 房地产贷款/额度数量 |
| `number_of_time_60_89_days_past_due_not_worse` | NumberOfTime60-89DaysPastDueNotWorse | 逾期 60-89 天次数 |
| `number_of_dependents` | NumberOfDependents | 供养人数（缺失 3,924 条，2.61%） |

> 设计说明：GMSC 只有单张 CSV，为满足"多表 JOIN"的业务场景，`setup.sql` 在主表 `credit_data` 之外人为构建了维度表 `score_dim`（信用分分段 × 风险等级）。由于 GMSC 不含信用评分字段，按风控行业常识"信用利用率越低 → 模拟信用分越高"建立映射，用于演示维度表关联与完整报表输出。

> 缺失值说明：本目录数据源的缺失值以字符串 `NA` 序列化（R 导出），`setup.sql` 第 4 节已将 `''` / `'NA'` 统一规范为 SQL `NULL`，因此 `IS NULL` 统计与聚合计算均正确（月收入缺失 29,731 条 / 19.82%，供养人数缺失 3,924 条 / 2.61%）。

## 数据质量备注（风控视角）

原始数据存在以下已知异常，**分析时需注意、但未做任何清洗**（保持数据原貌，符合审计留痕要求）：

| 异常类型 | 规模 | 影响 |
|---|---|---|
| `revolving_utilization` > 1（利用率超 100%，最大 50,708） | 3,321 条 / 2.21% | 拉高 Q9 各年龄组平均利用率（如 `<30` 组均值 4.38） |
| `debt_ratio` > 100（最大 329,664） | 24,380 条 / 16.25% | 扭曲 Q10 最高分位组，导致违约率非单调（Q10 注释已说明） |
| `age` = 0 | 1 条 | 落入 `<30` 分组，不影响分组结论 |
| 逾期次数为 96 / 98（特殊编码，非真实次数） | 269 条 / 0.18% | 造成 Q13/Q14 中 `total_past_due` 最大达 294 |
| `monthly_income` = 0 | 1,634 条 / 1.09% | 收入为 0 与缺失（NULL）业务含义不同，未合并处理 |

生产环境建议：分位/排名类指标先做异常值截断（winsorize），逾期次数先剔除 96/98 编码。

## 如何运行

1. 确保本地安装了 SQLite（3.32+，支持 `.import --csv --skip`；本套 SQL 在 SQLite 3.45.1 上验证通过）。
2. 将 `cs-training.csv` 放入当前目录（本仓库已包含）。
3. 执行建表与导入：

   ```bash
   sqlite3 credit.db < setup.sql
   ```

4. 执行查询：

   ```bash
   sqlite3 credit.db < queries.sql
   ```

查看数据库内容（可选）：

```bash
sqlite3 credit.db "SELECT COUNT(*) FROM credit_data;"   # 预期 150000
sqlite3 credit.db ".tables"                              # credit_data  score_dim
```

> 导入说明：`setup.sql` 末尾自带导入自检（总行数 / 违约客户数 / 收入缺失数 / 供养人缺失数），运行后可直接核对。若重复执行，脚本会先 DROP 再重建，保证幂等。

## 常见问题 FAQ

**Q1：报错 `no such table: credit_data`？**
先执行 `sqlite3 credit.db < setup.sql`，再执行 `queries.sql`——查询脚本依赖 setup.sql 建好的表。

**Q2：报错 `.import` 相关语法错误？**
`.import --csv --skip` 需要 SQLite 3.32+，窗口函数需要 3.25+。用 `sqlite3 --version` 检查，过旧请升级（macOS 系统自带版本通常偏旧，可用 Homebrew 安装新版）。

**Q3：`queries.sql` 开头的 `.headers ON` / `.mode column` 是什么？**
这是 sqlite3 CLI 的 dot-command，用于美化输出。它**只能在 sqlite3 命令行中运行**；如果用 Python 的 `sqlite3` 模块 `executescript()` 执行，请先删除这两行。

**Q4：`credit.db` 需要提交到 Git 吗？**
不需要。它是可再生成品（删掉后按 README 两步即可重建），建议加入 `.gitignore`。

**Q5：数据里为什么有利用率 8497、逾期 294 次这种值？**
原始数据即如此，详见「数据质量备注」。本查询集坚持原样呈现，不做静默清洗。

## 查询说明（15 个）

| # | 分类 | 语法点 | 业务问题 |
|---|---|---|---|
| Q1 | 基础聚合 | COUNT / SUM / AVG | 整体客户数、违约客户数与整体违约率（资产质量北极星指标） |
| Q2 | 基础聚合 | GROUP BY + CASE WHEN | 各年龄段客户数与违约率（客群准入与差异化定价依据） |
| Q3 | 基础聚合 | WHERE IS NULL + 标量子查询 | MonthlyIncome 缺失数量及占比（数据质量量化） |
| Q4 | 多表 JOIN | INNER JOIN（区间关联） | 各模拟信用分段（score_dim）的违约客户数与违约率 |
| Q5 | 多表 JOIN | LEFT JOIN（维度表在左） | 完整分数段报表：无客户的分段也展示（数量为 0） |
| Q6 | 窗口函数 | ROW_NUMBER() OVER (PARTITION BY … ORDER BY …) | 各年龄段内按信用利用率的内部排名（头部风险客户定位） |
| Q7 | 窗口函数 | RANK() OVER (ORDER BY …) | 客户月收入降序排名（高收入客群识别，并列同名次） |
| Q8 | 窗口函数 | SUM() OVER () + 累计窗口 | 各年龄段违约人数占比与累计占比（帕累托定位核心风险人群） |
| Q9 | 窗口函数 | LAG() OVER (ORDER BY …) | 相邻年龄段平均信用利用率环比差值（杠杆趋势） |
| Q10 | 窗口函数 | NTILE(4) OVER (ORDER BY …) | 债务收入比四分位组的违约率（观察高杠杆人群风险特征） |
| Q11 | CTE | 单层 WITH + CASE WHEN 打标签 | 高负债标签客群 vs 非高负债客群违约率对比 |
| Q12 | CTE | CTE 嵌套（分段指标 → 整体基准 → 筛选） | 筛选违约率高于整体平均的高风险年龄段 |
| Q13 | CTE | CTE + RANK() 窗口函数 | 同年龄段内客户逾期总次数排名（催收优先级） |
| Q14 | 子查询 | IN 子查询 + 标量子查询（AVG 比对） | 逾期次数高于全体平均且落入高风险分段客户的监控名单 |
| Q15 | 子查询 | EXISTS 相关子查询 | 月收入高于同年龄段平均收入的客户（交叉营销名单） |

## 查询结果截图

关键查询的终端运行结果见 `images/` 目录：

- `window_function_rownumber.png` — Q6 ROW_NUMBER() 年龄段内信用利用率排名
- `window_function_cumulative.png` — Q8 SUM() OVER 违约人数累计占比
- `cte_nested.png` — Q12 CTE 嵌套筛选高风险年龄段
- `window_function_ntile.png` — Q10 NTILE(4) 债务比四分位违约率
- `join_score_band.png` — Q4 INNER JOIN 分数段违约率

## 代码规范

- 命名：表名、字段名统一小写下划线（`credit_data`、`score_dim`、`serious_dlqin2yrs`）；
- SQL 关键字大写，缩进对齐；
- 每个查询前以 `/* 业务背景：… */` 注明业务用途；
- 测试查询统一加 `LIMIT 5`，避免全量输出；
- 全部为 SQLite 兼容语法（无 MySQL 特有函数/语法）。

## 扩展方向（面试可展开）

- **每段 Top N**：Q6 目前受 `LIMIT 5` 约束只展示一个年龄段的前 5 名；生产取数可在外层加 `WHERE utilization_rank_in_age <= 5` 得到每个年龄段的 Top 5。
- **真实评分替换**：`score_dim` 是按行业常识构造的模拟维度；接入真实评分卡后，将 `util_min/util_max` 替换为评分区间即可无缝复用 Q4/Q5/Q14。
- **性能**：15 万行演示数据无需索引；百万级以上建议对 `age`、`revolving_utilization` 等过滤/关联字段建索引，并用 `EXPLAIN QUERY PLAN` 验证。
- **多期数据**：GMSC 为单期横截面数据，无时间维度；若有多期数据，LAG 即可升级为真正的环比/同比指标（如违约率月度环比）。

## 一句话结论

这份 SQL 脚本不仅能取数，更是一个风控业务的"指标计算工具箱"。

## 面试话术

"这份查询集包含 15 个查询，覆盖了风控业务中最常用的取数逻辑。比如这个 SUM() OVER 窗口函数，我用来计算不同年龄段的累计违约占比，帮助业务快速定位核心风险人群；这个 CTE 嵌套，我用来筛选出违约率显著高于整体平均的特定客群。所有代码在 SQLite 上可以直接跑通。"
