-- ============================================================================
-- 01_基础聚合.sql · 方法论流程第 1 步：基础查询与聚合（Q1-Q3）
-- 数据源：GMSC（Give Me Some Credit）cs-training.csv，150,000 行，已由 setup.sql 导入
-- 运行方式：sqlite3 credit.db < 01_基础聚合.sql
-- 语法覆盖：COUNT / SUM / AVG、GROUP BY + CASE WHEN 分段聚合、WHERE IS NULL + 标量子查询
-- 环境：SQLite 3.45.1 实测通过；预期输出为列模式渲染（.headers ON + .mode column）
-- 阅读顺序：先看整体（北极星指标），再分段（客群结构），最后查数据质量（缺失量化）——分析的起点
-- ============================================================================

.headers ON
.mode column

/* ============================================================================
   Q1 | 语法：基础聚合（COUNT / SUM / AVG）
   业务背景：整体违约率是信贷组合的"北极星指标"，用于快速评估资产质量、
             设定定价基准与拨备水平。

   预期输出（150,000 行真实数据实测，列模式渲染）：
   total_customers  default_customers  default_rate_pct
   ---------------  -----------------  ----------------
   150000           10026              6.68

   性能说明：单表全量聚合，无 WHERE/JOIN，顺序扫描一次即得；150,000 行实测 7.8 毫秒。无需索引，SQLite 单线程可扛。
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

   预期输出（150,000 行真实数据实测，列模式渲染）：
   age_group  customer_count  default_count  default_rate_pct  avg_age
   ---------  --------------  -------------  ----------------  -------
   1_<30      8821            1035           11.73             26.3
   2_30-45    38982           3700           9.49              37.8
   3_45-60    53879           3791           7.04              51.9
   4_>60      48318           1500           3.1               69.3

   性能说明：GROUP BY 分组聚合 + ORDER BY 排序（仅 4 个分组），计算量集中在一次全表扫描；150,000 行实测 43 毫秒。
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

   预期输出（150,000 行真实数据实测，列模式渲染）：
   income_missing_count  income_missing_pct
   --------------------  ------------------
   29731                 19.82

   性能说明：主查询按月收入 IS NULL 过滤（全表扫描），标量子查询再扫一次全表取总数——共约 2 次全表扫描；150,000 行实测 6.4 毫秒。生产环境可把总数改为常量或物化，省掉第二次扫描。
   ============================================================================ */
SELECT
    COUNT(*) AS income_missing_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM credit_data), 2) AS income_missing_pct
FROM credit_data
WHERE monthly_income IS NULL
LIMIT 5;
