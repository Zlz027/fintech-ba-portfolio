-- ============================================================================
-- 02_多表连接.sql · 方法论流程第 2 步：多表 JOIN（Q4-Q5）
-- 数据源：GMSC（Give Me Some Credit）cs-training.csv，150,000 行，已由 setup.sql 导入
-- 运行方式：sqlite3 credit.db < 02_多表连接.sql
-- 语法覆盖：INNER JOIN（区间关联）、LEFT JOIN（维度表在左保完整报表）
-- 环境：SQLite 3.45.1 实测通过；预期输出为列模式渲染（.headers ON + .mode column）
-- 阅读顺序：主表关联维度表，把客户映射到信用分分段，验证“低分段高风险”
-- ============================================================================

.headers ON
.mode column

/* ============================================================================
   Q4 | 语法：INNER JOIN（区间关联）+ GROUP BY
   业务背景：将客户按信用利用率映射到 score_dim 的模拟信用分分段，
             输出每个分数段的违约客户数与违约率，验证"低分段高风险"。

   预期输出（150,000 行真实数据实测，列模式渲染）：
   score_band  risk_level  customer_count  default_count  default_rate_pct
   ----------  ----------  --------------  -------------  ----------------
   801-900     低           81709           1647           2.02
   701-800     中低          19844           871            4.39
   601-700     中           13216           1005           7.6
   501-600     中高          10098           1205           11.93
   0-500       高           25133           5298           21.08

   性能说明：INNER JOIN 区间关联：主表全表扫描，每行与 score_dim 的 5 个区间做嵌套循环比对，再按 2 列分组；150,000 行实测 83 毫秒。区间关联无法走索引，数据量到百万级时建议预计算 score_band 字段落表。
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

   预期输出（150,000 行真实数据实测，列模式渲染）：
   score_band  risk_level  customer_count  default_count  default_rate_pct
   ----------  ----------  --------------  -------------  ----------------
   801-900     低           81709           1647           2.02
   701-800     中低          19844           871            4.39
   601-700     中           13216           1005           7.6
   501-600     中高          10098           1205           11.93
   0-500       高           25133           5298           21.08

   性能说明：LEFT JOIN 与 Q4 计算量相同（维度表仅 5 行，嵌套循环廉价），区别只在语义上保留无客户分段；150,000 行实测 83 毫秒。
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
