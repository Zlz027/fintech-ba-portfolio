-- ============================================================================
-- 05_子查询.sql · 方法论流程第 5 步：子查询（Q14-Q15）
-- 数据源：GMSC（Give Me Some Credit）cs-training.csv，150,000 行，已由 setup.sql 导入
-- 运行方式：sqlite3 credit.db < 05_子查询.sql
-- 语法覆盖：IN 子查询 + 标量子查询（AVG 比对）、EXISTS 相关子查询
-- 环境：SQLite 3.45.1 实测通过；预期输出为列模式渲染（.headers ON + .mode column）
-- 阅读顺序：WHERE 中嵌 SELECT：先算基准再逐行比对，监控名单与优质客户名单的取数口径
-- ============================================================================

.headers ON
.mode column

/* ============================================================================
   Q14 | 语法：IN 子查询 + 标量子查询（WHERE 中嵌 SELECT AVG）
   业务背景：贷后重点监控名单——圈出"三段逾期总次数高于全体平均"
             且信用利用率落入高风险分数段（risk_level='高'）的客户，
             作为催收与降额的优先对象。

   预期输出（150,000 行真实数据实测，列模式渲染）：
   id    age  revolving_utilization  total_past_due
   ----  ---  ---------------------  --------------
   1734  27   0.9999999              294
   2287  22   0.9999999              294
   3885  38   0.9999999              294
   4418  21   0.9999999              294
   4706  21   0.9999999              294

   性能说明：IN 子查询被 SQLite 物化为高风险客户 ID 列表（约 2.5 万个），外层按 rowid 逐条回表，而非两次全表扫描；标量子查询只算一次全体平均；150,000 行实测 33 毫秒——比“两次全表扫描”的直觉快得多，执行计划可用 EXPLAIN QUERY PLAN 验证。监控名单类取数建议落调度表而非即席查询。
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

   预期输出（150,000 行真实数据实测，列模式渲染）：
   id      age  age_group  monthly_income  age_group_avg_income
   ------  ---  ---------  --------------  --------------------
   73764   52   3_45-60    3008750.0       7613.58
   137141  68   4_>60      1794060.0       6746.86
   111366  44   2_30-45    1560100.0       6159.65
   50641   44   2_30-45    1072500.0       6159.65
   122544  55   3_45-60    835040.0        7613.58

   性能说明：EXISTS 相关子查询：外层每行都要在 age_group_income（CTE 物化，仅 4 行）中查找同年龄段均值——15 万行 × 4 行小表比对；150,000 行实测 59 毫秒。SQLite 对物化 CTE 每次引用重算，数据量更大时可把年龄段均值落成临时表并建索引。
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
