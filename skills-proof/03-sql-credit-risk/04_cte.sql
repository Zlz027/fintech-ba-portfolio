-- ============================================================================
-- 04_cte.sql · 方法论流程第 4 步：CTE 公用表表达式（WITH 子句）（Q11-Q13）
-- 数据源：GMSC（Give Me Some Credit）cs-training.csv，150,000 行，已由 setup.sql 导入
-- 运行方式：sqlite3 credit.db < 04_cte.sql
-- 语法覆盖：单层 WITH + CASE 打标签、CTE 嵌套（分段指标 → 整体基准 → 筛选）、CTE + 窗口函数
-- 环境：SQLite 3.45.1 实测通过；预期输出为列模式渲染（.headers ON + .mode column）
-- 阅读顺序：把复杂查询拆成命名步骤，可读性优于嵌套子查询——生产 SQL 的默认写法
-- ============================================================================

.headers ON
.mode column

/* ============================================================================
   Q11 | 语法：CTE 基础应用（单层 WITH + CASE WHEN 打标签）
   业务背景：先给客户打"高负债"标签（债务收入比 > 0.5），
              再按标签统计违约率，验证高负债客群的风险溢价。

   预期输出（150,000 行真实数据实测，列模式渲染）：
   debt_label  customer_count  default_count  default_rate_pct
   ----------  --------------  -------------  ----------------
   高负债         56292           4371           7.76
   非高负债        93708           5655           6.03

   性能说明：CTE 物化全表并打标签，外层按 2 个标签分组聚合，一次扫描；150,000 行实测 35 毫秒。
   ============================================================================ */
WITH customer_debt_label AS (
    SELECT
        id,
        serious_dlqin2yrs,
        CASE WHEN debt_ratio > 0.5 THEN '高负债' ELSE '非高负债' END AS debt_label
    FROM credit_data
)
SELECT
    debt_label,
    COUNT(*)                               AS customer_count,
    SUM(serious_dlqin2yrs)                 AS default_count,
    ROUND(AVG(serious_dlqin2yrs) * 100, 2) AS default_rate_pct
FROM customer_debt_label
GROUP BY debt_label
ORDER BY default_rate_pct DESC
LIMIT 5;

/* ============================================================================
   Q12 | 语法：CTE 嵌套（CTE1 算分段指标 -> CTE2 引入整体基准 -> CTE3 筛选）
   业务背景：先算各年龄段违约率，再与整体平均违约率比较，
             筛选出违约率显著高于整体平均的高风险年龄段，实现风险客群定位。

   预期输出（150,000 行真实数据实测，列模式渲染）：
   age_group  customer_count  default_rate_pct  overall_rate_pct
   ---------  --------------  ----------------  ----------------
   1_<30      8821            11.73             6.68
   2_30-45    38982           9.49              6.68
   3_45-60    53879           7.04              6.68

   性能说明：三层 CTE：分段统计（4 行）→ 整体基准（1 行）→ CROSS JOIN 筛选；overall_stats 仅 1 行，交叉代价可忽略；150,000 行实测 42 毫秒。
   ============================================================================ */
WITH age_group_stats AS (
    SELECT
        CASE
            WHEN age < 30 THEN '1_<30'
            WHEN age < 45 THEN '2_30-45'
            WHEN age < 60 THEN '3_45-60'
            ELSE '4_>60'
        END AS age_group,
        COUNT(*)                 AS customer_count,
        AVG(serious_dlqin2yrs)   AS default_rate
    FROM credit_data
    GROUP BY age_group
),
overall_stats AS (
    SELECT AVG(serious_dlqin2yrs) AS overall_default_rate
    FROM credit_data
),
high_risk_age_groups AS (
    SELECT
        s.age_group,
        s.customer_count,
        s.default_rate
    FROM age_group_stats s
    CROSS JOIN overall_stats o
    WHERE s.default_rate > o.overall_default_rate
)
SELECT
    age_group,
    customer_count,
    ROUND(default_rate * 100, 2) AS default_rate_pct,
    (SELECT ROUND(overall_default_rate * 100, 2) FROM overall_stats) AS overall_rate_pct
FROM high_risk_age_groups
ORDER BY default_rate_pct DESC
LIMIT 5;

/* ============================================================================
   Q13 | 语法：CTE + 窗口函数（CTE 先加工字段，外层做分组内排名）
   业务背景：先汇总每个客户的三段逾期总次数，再计算其在同年龄段内的
             逾期排名，用于贷后监控中识别高危个体、安排催收优先级。

   预期输出（150,000 行真实数据实测，列模式渲染）：
   id    age_group  total_past_due  past_due_rank_in_age
   ----  ---------  --------------  --------------------
   1734  1_<30      294             1
   2287  1_<30      294             1
   4418  1_<30      294             1
   4706  1_<30      294             1
   7033  1_<30      294             1

   性能说明：CTE 物化 15 万行（含三段逾期求和），外层 RANK 按 age_group 分区 + total_past_due 降序排序；150,000 行实测 192 毫秒。与 Q6 同理，成本在分区排序。
   ============================================================================ */
WITH customer_past_due AS (
    SELECT
        id,
        age,
        CASE
            WHEN age < 30 THEN '1_<30'
            WHEN age < 45 THEN '2_30-45'
            WHEN age < 60 THEN '3_45-60'
            ELSE '4_>60'
        END AS age_group,
        number_of_time_30_59_days_past_due_not_worse
            + number_of_time_60_89_days_past_due_not_worse
            + number_of_times_90_days_late AS total_past_due
    FROM credit_data
)
SELECT
    id,
    age_group,
    total_past_due,
    RANK() OVER (
        PARTITION BY age_group
        ORDER BY total_past_due DESC
    ) AS past_due_rank_in_age
FROM customer_past_due
ORDER BY age_group, past_due_rank_in_age
LIMIT 5;
