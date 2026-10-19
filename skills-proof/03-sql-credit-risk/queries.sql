-- ============================================================================
-- MVP3 金融风控 SQL 查询集 · 15 个业务查询（queries.sql）
-- 数据源：GMSC（Give Me Some Credit）cs-training.csv，已由 setup.sql 导入
-- 运行方式：sqlite3 credit.db < queries.sql
-- 语法覆盖：基础聚合(3) / 多表 JOIN(2) / 窗口函数(5) / CTE(3) / 子查询(2)
-- 约定：字段命名小写下划线；SQL 关键字大写；每个查询带 /* 业务背景 */ 注释；
--       为控制输出量，所有查询均加 LIMIT 5。
-- ============================================================================

.headers ON
.mode column

-- ============================================================================
-- 第一部分：基础查询与聚合（3 个）
-- ============================================================================

/* ============================================================================
   Q1 | 语法：基础聚合（COUNT / SUM / AVG）
   业务背景：整体违约率是信贷组合的"北极星指标"，用于快速评估资产质量、
             设定定价基准与拨备水平。
   ============================================================================ */
SELECT
    COUNT(*)                               AS total_customers,
    SUM(serious_dlqin2yrs)                 AS default_customers,
    ROUND(AVG(serious_dlqin2yrs) * 100, 2) AS default_rate_pct
FROM credit_data
LIMIT 5;

/* ============================================================================
   Q2 | 语法：GROUP BY + CASE WHEN 分段聚合
   业务背景：不同年龄段的违约率差异是客群准入与差异化定价的重要依据，
             年轻客群与高龄客群往往需要差异化的风控策略。
   ============================================================================ */
SELECT
    CASE
        WHEN age < 30 THEN '1_<30'
        WHEN age < 45 THEN '2_30-45'
        WHEN age < 60 THEN '3_45-60'
        ELSE '4_>60'
    END                                    AS age_group,
    COUNT(*)                               AS customer_count,
    SUM(serious_dlqin2yrs)                 AS default_count,
    ROUND(AVG(serious_dlqin2yrs) * 100, 2) AS default_rate_pct,
    ROUND(AVG(age), 1)                     AS avg_age
FROM credit_data
GROUP BY age_group
ORDER BY default_rate_pct DESC
LIMIT 5;

/* ============================================================================
   Q3 | 语法：WHERE IS NULL 缺失值统计（子查询取总数）
   业务背景：收入字段缺失率直接影响收入类风控规则的覆盖率，
             建模前必须量化数据质量。
   ============================================================================ */
SELECT
    COUNT(*) AS income_missing_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM credit_data), 2) AS income_missing_pct
FROM credit_data
WHERE monthly_income IS NULL
LIMIT 5;

-- ============================================================================
-- 第二部分：多表 JOIN（2 个）
-- ============================================================================

/* ============================================================================
   Q4 | 语法：INNER JOIN（区间关联）+ GROUP BY
   业务背景：将客户按信用利用率映射到 score_dim 的模拟信用分分段，
             输出每个分数段的违约客户数与违约率，验证"低分段高风险"。
   ============================================================================ */
SELECT
    s.score_band,
    s.risk_level,
    COUNT(c.id)                            AS customer_count,
    SUM(c.serious_dlqin2yrs)               AS default_count,
    ROUND(AVG(c.serious_dlqin2yrs) * 100, 2) AS default_rate_pct
FROM credit_data c
INNER JOIN score_dim s
    ON c.revolving_utilization >= s.util_min
   AND c.revolving_utilization <  s.util_max
GROUP BY s.score_band, s.risk_level
ORDER BY s.score_min DESC
LIMIT 5;

/* ============================================================================
   Q5 | 语法：LEFT JOIN（维度表在左，保完整报表）
   业务背景：以 score_dim 为左表做 LEFT JOIN，即使某分数段没有客户也保留该行
             （数量为 0），保证报表维度完整，避免"有客户才展示"的信息丢失。
   ============================================================================ */
SELECT
    s.score_band,
    s.risk_level,
    COUNT(c.id)                            AS customer_count,
    COALESCE(SUM(c.serious_dlqin2yrs), 0)  AS default_count,
    ROUND(COALESCE(AVG(c.serious_dlqin2yrs), 0) * 100, 2) AS default_rate_pct
FROM score_dim s
LEFT JOIN credit_data c
    ON c.revolving_utilization >= s.util_min
   AND c.revolving_utilization <  s.util_max
GROUP BY s.score_band, s.risk_level
ORDER BY s.score_min DESC
LIMIT 5;

-- ============================================================================
-- 第三部分：窗口函数（5 个）
-- ============================================================================

/* ============================================================================
   Q6 | 语法：ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ... DESC)
   业务背景：按信用利用率降序，在每个年龄段内部打客户排名，
             用于快速定位各年龄客群中杠杆最高的"头部风险客户"。
   ============================================================================ */
SELECT
    id,
    age_group,
    revolving_utilization,
    ROW_NUMBER() OVER (
        PARTITION BY age_group
        ORDER BY revolving_utilization DESC
    ) AS utilization_rank_in_age
FROM (
    SELECT
        id,
        CASE
            WHEN age < 30 THEN '1_<30'
            WHEN age < 45 THEN '2_30-45'
            WHEN age < 60 THEN '3_45-60'
            ELSE '4_>60'
        END AS age_group,
        revolving_utilization
    FROM credit_data
) t
ORDER BY age_group, utilization_rank_in_age
LIMIT 5;

/* ============================================================================
   Q7 | 语法：RANK() OVER (ORDER BY ... DESC)（并列同名次）
   业务背景：按客户月收入降序排名，识别高收入客群（VIP 名单 / 交叉营销）；
             RANK 在收入相并列时给出相同名次，符合业务对"并列"的认知。
   ============================================================================ */
SELECT
    id,
    age,
    monthly_income,
    RANK() OVER (ORDER BY monthly_income DESC) AS income_rank
FROM credit_data
WHERE monthly_income IS NOT NULL
ORDER BY income_rank
LIMIT 5;

/* ============================================================================
   Q8 | 语法：SUM() OVER () 总计 + SUM() OVER (ORDER BY ...) 累计
   业务背景：按违约人数对各年龄段排序并计算累计占比（帕累托分析），
             帮助业务快速定位贡献主要违约的核心风险人群。
   ============================================================================ */
SELECT
    age_group,
    default_count,
    ROUND(default_count * 100.0 / SUM(default_count) OVER (), 2) AS share_pct,
    ROUND(
        SUM(default_count) OVER (
            ORDER BY default_count DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) * 100.0 / SUM(default_count) OVER (), 2
    ) AS cumulative_share_pct
FROM (
    SELECT
        CASE
            WHEN age < 30 THEN '1_<30'
            WHEN age < 45 THEN '2_30-45'
            WHEN age < 60 THEN '3_45-60'
            ELSE '4_>60'
        END AS age_group,
        SUM(serious_dlqin2yrs) AS default_count
    FROM credit_data
    GROUP BY age_group
) t
ORDER BY default_count DESC
LIMIT 5;

/* ============================================================================
   Q9 | 语法：LAG() OVER (ORDER BY ...) 取上一行值
   业务背景：计算相邻年龄段的平均信用利用率环比差值，
             观察杠杆使用水平随年龄变化的趋势（如中年客群杠杆最高）。
   ============================================================================ */
SELECT
    age_group,
    ROUND(avg_utilization, 4) AS avg_utilization,
    ROUND(LAG(avg_utilization) OVER (ORDER BY age_group), 4) AS prev_age_avg_utilization,
    ROUND(avg_utilization - LAG(avg_utilization) OVER (ORDER BY age_group), 4) AS delta_vs_prev
FROM (
    SELECT
        CASE
            WHEN age < 30 THEN '1_<30'
            WHEN age < 45 THEN '2_30-45'
            WHEN age < 60 THEN '3_45-60'
            ELSE '4_>60'
        END AS age_group,
        AVG(revolving_utilization) AS avg_utilization
    FROM credit_data
    GROUP BY age_group
) t
ORDER BY age_group
LIMIT 5;

/* ============================================================================
   Q10 | 语法：NTILE(4) OVER (ORDER BY ...) 四分位分组
   业务背景：按债务收入比分四位数组，计算每组平均违约率，
             验证"高杠杆人群违约风险显著更高"，为额度与利率策略提供依据。
   数据备注：DebtRatio 存在 24,380 条（16.25%）大于 100 的极端异常值
             （最大 329,664），最高分位组被异常样本主导，违约率呈非单调，
             生产环境应先做异常值截断（如 winsorize）再分位。
   ============================================================================ */
WITH debt_quartile AS (
    SELECT
        id,
        serious_dlqin2yrs,
        NTILE(4) OVER (ORDER BY debt_ratio) AS quartile
    FROM credit_data
)
SELECT
    quartile                             AS debt_ratio_quartile,
    COUNT(*)                             AS customer_count,
    ROUND(AVG(serious_dlqin2yrs) * 100, 2) AS default_rate_pct
FROM debt_quartile
GROUP BY quartile
ORDER BY quartile
LIMIT 5;

-- ============================================================================
-- 第四部分：CTE（WITH 子句）（3 个）
-- ============================================================================

/* ============================================================================
   Q11 | 语法：CTE 基础应用（单层 WITH + CASE WHEN 打标签）
   业务背景：先给客户打"高负债"标签（债务收入比 > 0.5），
              再按标签统计违约率，验证高负债客群的风险溢价。
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

-- ============================================================================
-- 第五部分：子查询（2 个）
-- ============================================================================

/* ============================================================================
   Q14 | 语法：IN 子查询 + 标量子查询（WHERE 中嵌 SELECT AVG）
   业务背景：贷后重点监控名单——圈出"三段逾期总次数高于全体平均"
             且信用利用率落入高风险分数段（risk_level='高'）的客户，
             作为催收与降额的优先对象。
   ============================================================================ */
SELECT
    c.id,
    c.age,
    c.revolving_utilization,
    c.number_of_time_30_59_days_past_due_not_worse
        + c.number_of_time_60_89_days_past_due_not_worse
        + c.number_of_times_90_days_late AS total_past_due
FROM credit_data c
WHERE c.number_of_time_30_59_days_past_due_not_worse
          + c.number_of_time_60_89_days_past_due_not_worse
          + c.number_of_times_90_days_late
      > (SELECT AVG(number_of_time_30_59_days_past_due_not_worse
                    + number_of_time_60_89_days_past_due_not_worse
                    + number_of_times_90_days_late)
         FROM credit_data)
  AND c.id IN (
        SELECT c2.id
        FROM credit_data c2
        INNER JOIN score_dim s
            ON c2.revolving_utilization >= s.util_min
           AND c2.revolving_utilization <  s.util_max
        WHERE s.risk_level = '高'
  )
ORDER BY total_past_due DESC
LIMIT 5;

/* ============================================================================
   Q15 | 语法：EXISTS 相关子查询（子查询引用外层列做关联过滤）
   业务背景：找出月收入高于同年龄段平均收入的客户，
              识别同龄客群中的高收入优质客户，用于交叉营销与提额名单。
   ============================================================================ */
WITH customer_age_group AS (
    SELECT
        id,
        age,
        monthly_income,
        CASE
            WHEN age < 30 THEN '1_<30'
            WHEN age < 45 THEN '2_30-45'
            WHEN age < 60 THEN '3_45-60'
            ELSE '4_>60'
        END AS age_group
    FROM credit_data
    WHERE monthly_income IS NOT NULL
),
age_group_income AS (
    SELECT
        age_group,
        AVG(monthly_income) AS avg_income
    FROM customer_age_group
    GROUP BY age_group
)
SELECT
    c.id,
    c.age,
    c.age_group,
    c.monthly_income,
    ROUND((SELECT g.avg_income
           FROM age_group_income g
           WHERE g.age_group = c.age_group), 2) AS age_group_avg_income
FROM customer_age_group c
WHERE EXISTS (
    SELECT 1
    FROM age_group_income g
    WHERE g.age_group = c.age_group
      AND c.monthly_income > g.avg_income
)
ORDER BY c.monthly_income DESC
LIMIT 5;
