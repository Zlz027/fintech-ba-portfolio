-- =============================================================
-- metrics.sql：信用风险与定价的经营指标口径（生产可复现）
-- 用途：把 docs/metrics.md 中的指标落成数仓 SQL，供月度经营看板与监控使用
-- 依赖：dw.credit_application_snapshot（申请宽表）、dw.credit_score_daily（评分回写）
-- 说明：演示版为 Hive/Spark SQL 语法；分位/PSI 在数仓侧计算，与 Notebook 口径一致
-- =============================================================

-- 1) 模型区分度：AUC / KS（按表现期回填后按月跑）
--    AUC = 随机取一好一坏，坏样本得分更高的概率（Mann-Whitney U 形式）
WITH scored AS (
    SELECT s.pd, s.score, a.y
    FROM dw.credit_score_daily s
    JOIN dw.credit_application_snapshot a ON s.applicant_id = a.applicant_id
    WHERE s.model_version = '${model_version}'
      AND a.serious_dlqin_2yrs IS NOT NULL
),
ranked AS (
    SELECT pd, y,
           ROW_NUMBER() OVER (ORDER BY pd)                                AS rk,
           SUM(CASE WHEN y = 0 THEN 1 ELSE 0 END) OVER ()                 AS n_good,
           SUM(CASE WHEN y = 1 THEN 1 ELSE 0 END) OVER ()                 AS n_bad,
           SUM(CASE WHEN y = 1 THEN rk_proxy ELSE 0 END) OVER ()          AS bad_rank_sum
    FROM scored
)
-- AUC = (bad_rank_sum − n_bad×(n_bad+1)/2) / (n_good × n_bad)
SELECT
    model_auc,
    -- KS：好/坏样本 PD 累积分布的最大间距
    ks_stat
FROM staging.model_discrimination
WHERE bizmonth = '${bizmonth}';
-- 验收线：AUC ≥ 0.78、KS ≥ 0.35、Gini = 2×AUC−1 ≥ 0.56

-- 2) 稳定性：评分 PSI（近期分布 vs 训练基准分布）
--    基准分布固定为训练集快照；PSI = Σ (actual% − expected%) × ln(actual% / expected%)
WITH recent AS (
    SELECT score_bin, COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS recent_pct
    FROM dw.credit_score_daily
    WHERE dt BETWEEN DATE_SUB('${bizdate}', 30) AND '${bizdate}'
    GROUP BY score_bin
),
base AS (
    SELECT score_bin, train_pct
    FROM staging.score_baseline_distribution
    WHERE model_version = '${model_version}'
)
SELECT
    r.score_bin, b.train_pct, r.recent_pct,
    (r.recent_pct - b.train_pct) * LN(r.recent_pct / b.train_pct)      AS psi_contrib
FROM recent r JOIN base b ON r.score_bin = b.score_bin;
-- 告警线：SUM(psi_contrib) > 0.25 → 触发重训评审工单

-- 3) 业务层：分档实际坏账率 vs 预测 PD（校准回测）
SELECT
    score_decile,
    AVG(pd)                                   AS predicted_pd,      -- 预测均值
    SUM(y) * 1.0 / COUNT(*)                   AS realized_bad_rate, -- 实际坏账率
    SUM(y) * 1.0 / COUNT(*) / AVG(pd) - 1     AS deviation          -- 偏离度
FROM staging.scored_with_label
GROUP BY score_decile;
-- 告警线：|deviation| > 20% → 人工复核高 PD 段

-- 4) 财务层：全组合利润率（批准客群预期年损益 / 全部申请人 EAD）
--    r* = (PD×LGD + funding + opex) / (1 − PD)；定价硬约束 rate ≤ 24% 且 rate ≤ wtp
SELECT
    bizmonth,
    SUM(CASE WHEN approved = 1
             THEN (suggested_rate - breakeven_rate) * ead * (1 - pd)   -- 批准客群预期利差
             ELSE 0 END)
        / SUM(ead)                                                     AS portfolio_margin,
    AVG(CASE WHEN approved = 1 THEN 1.0 ELSE 0 END)                    AS approval_rate,
    SUM(CASE WHEN approved = 1 AND suggested_rate < breakeven_rate
             THEN 1 ELSE 0 END)                                        AS underpriced_cnt  -- 应为 0
FROM staging.credit_pricing_output
GROUP BY bizmonth;
-- 红线：underpriced_cnt > 0（出现亏损定价）→ 当日回滚定价引擎版本

-- 5) 通过率与成交率（策略迭代用）
SELECT bizmonth,
       SUM(approved) * 1.0 / COUNT(*)                                  AS approve_rate,
       SUM(deal) * 1.0 / COUNT(*)                                      AS deal_rate,
       SUM(CASE WHEN deal = 1 THEN y ELSE 0 END) * 1.0
           / NULLIF(SUM(deal), 0)                                      AS deal_bad_rate
FROM staging.credit_decision_log
GROUP BY bizmonth;
