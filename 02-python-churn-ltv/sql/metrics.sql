-- =============================================================
-- metrics.sql：客户流失与留存经济性的经营指标口径（生产可复现）
-- 用途：把 docs/metrics.md 中的指标落成数仓 SQL，供挽留决策与月度监控使用
-- 依赖：dw.customer_contract_snapshot（客户宽表）、dw.churn_score_daily（评分回写）
-- 说明：演示版为 Hive/Spark SQL 语法；PSI/分位在数仓侧计算，与 Notebook 口径一致
-- =============================================================

-- 1) 模型区分度：AUC / KS（观察期末标签回填后按月跑）
WITH scored AS (
    SELECT s.churn_prob, a.Churn AS y
    FROM dw.churn_score_daily s
    JOIN dw.customer_contract_snapshot a ON s.customerID = a.customer_id
    WHERE s.model_version = '${model_version}'
      AND a.dt = '${label_date}'
),
ranked AS (
    SELECT churn_prob, y,
           ROW_NUMBER() OVER (ORDER BY churn_prob)                        AS rk,
           SUM(CASE WHEN y = 0 THEN 1 ELSE 0 END) OVER ()                 AS n_retain,
           SUM(CASE WHEN y = 1 THEN 1 ELSE 0 END) OVER ()                 AS n_churn
    FROM scored
)
-- AUC = (churn 的秩和 − n_churn×(n_churn+1)/2) / (n_retain × n_churn)
SELECT model_auc, ks_stat, pr_auc
FROM staging.churn_discrimination
WHERE bizmonth = '${bizmonth}';
-- 验收线：AUC ≥ 0.75、KS ≥ 0.35、各 cohort AUC ≥ 0.75

-- 2) 稳定性：评分 PSI（近期分布 vs 训练基准分布）
WITH recent AS (
    SELECT score_bin, COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS recent_pct
    FROM dw.churn_score_daily
    WHERE dt BETWEEN DATE_SUB('${bizdate}', 30) AND '${bizdate}'
    GROUP BY score_bin
),
base AS (
    SELECT score_bin, train_pct
    FROM staging.churn_score_baseline
    WHERE model_version = '${model_version}'
)
SELECT r.score_bin, b.train_pct, r.recent_pct,
       (r.recent_pct - b.train_pct) * LN(r.recent_pct / b.train_pct)    AS psi_contrib
FROM recent r JOIN base b ON r.score_bin = b.score_bin;
-- 告警线：SUM(psi_contrib) > 0.25 → 触发重训评审工单

-- 3) 价值与风险：折现 LTV 与收入风险敞口（RaR）
--    LTV_horizon = Σ_m MonthlyCharges × 毛利率 × S(tenure+m) / (1+r)^m
--    简化展示口径：以 cohort 留存表 cohort_survival 查表，避免函数内插
SELECT
    c.customerID,
    c.MonthlyCharges,
    s.churn_prob,
    -- 36 个月折现 LTV（毛利率 0.60、折现率 r 与财务统一）
    (SELECT SUM(c.MonthlyCharges * 0.60 * cs.surv_prob / POWER(1 + ${discount_rate}, cs.m))
     FROM cohort_survival cs
     WHERE cs.tenure_base = c.tenure AND cs.m BETWEEN 1 AND 36)         AS ltv,
    -- 未来 12 个月期望收入流失
    c.MonthlyCharges * s.churn_prob * 12                               AS rar,
    -- 期望保住收益（uplift 由 A/B 实验校准）
    s.churn_prob * ${uplift} * ltv                                     AS expected_save
FROM dw.customer_contract_snapshot c
JOIN dw.churn_score_daily s ON c.customer_id = s.customerID;

-- 4) 挽留经济性：按 churn_prob × LTV 降序累计，找净利润拐点 N*
WITH ranked AS (
    SELECT customerID,
           churn_prob * ${uplift} * ltv                                AS expected_save,
           ${contact_cost}                                             AS contact_cost,
           ROW_NUMBER() OVER (ORDER BY churn_prob * ltv DESC)          AS rk
    FROM staging.churn_expected_save
)
SELECT rk,
       SUM(expected_save) OVER (ORDER BY rk)                           AS cum_gain,
       SUM(contact_cost)  OVER (ORDER BY rk)                           AS cum_cost,
       SUM(expected_save - contact_cost) OVER (ORDER BY rk)            AS cum_net,
       SUM(expected_save) OVER (ORDER BY rk)
           / NULLIF(SUM(contact_cost) OVER (ORDER BY rk), 0)           AS gross_roi
FROM ranked;
-- N* = cum_net 最大的 rk；基准（uplift=30%）：N*=550、净收益 ¥62,468、毛 ROI 2.62
-- 红线：ROI < 1.0 → 暂停大规模触达，回到小规模 A/B

-- 5) 分层捕获率（高风险层是否捕获 ≥ 60% 实际流失）
SELECT risk_tier,
       SUM(y) * 1.0 / SUM(SUM(y)) OVER ()                              AS churn_capture,
       AVG(churn_prob)                                                 AS avg_pred,
       SUM(y) * 1.0 / COUNT(*)                                         AS realized_churn
FROM staging.churn_scored_with_label
GROUP BY risk_tier;
