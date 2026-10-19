-- =============================================================
-- metrics.sql：欺诈检测的经营与成本指标口径（生产可复现）
-- 用途：把 docs/metrics.md 中的指标落成数仓 SQL，供日监控与季度成本校准使用
-- 依赖：dw.card_auth_txn（交易事实表）、dw.fraud_score_daily（评分回写）
-- 说明：演示版为 Hive/Spark SQL 语法；时序切分严禁随机（见 BRD F-03）
-- =============================================================

-- 1) 模型区分度：AUPRC / AUC（按表现期回填后按月跑，时序切分）
--    评估必须按事件时间切分，禁随机切分（同批次欺诈泄漏会使 AUPRC 虚高约 9.6%）
WITH scored AS (
    SELECT s.p_fraud, a.class AS y
    FROM dw.fraud_score_daily s
    JOIN dw.card_auth_txn a ON s.txn_id = a.txn_id
    WHERE s.model_version = '${model_version}'
      AND a.chargeback_status IS NOT NULL                         -- 表现期已到期
      AND a.auth_time >= '${test_window_start}'                   -- 时序测试窗
)
SELECT model_auc, model_auprc, base_rate,
       model_auprc / base_rate AS lift_vs_baseline
FROM staging.fraud_discrimination
WHERE bizmonth = '${bizmonth}';
-- 验收线：AUPRC ≥ 0.60、AUC ≥ 0.95、AUPRC 相对基准（欺诈率）有显著 lift

-- 2) 成本与阈值：期望总成本与最优阈值（分段常数精确求解）
--    C(θ) = FP(θ)×fp_cost + Σ_{漏判}(Amount + miss_fixed)
SELECT
    threshold,
    SUM(CASE WHEN flag = 1 AND y = 0 THEN ${fp_cost} ELSE 0 END)              -- 误杀成本
  + SUM(CASE WHEN flag = 0 AND y = 1 THEN amount + ${miss_fixed} ELSE 0 END)  -- 漏判成本
                                                                   AS total_cost,
    SUM(CASE WHEN flag = 1 AND y = 1 THEN 1 ELSE 0 END)            AS tp,
    SUM(CASE WHEN flag = 1 THEN 1 ELSE 0 END)                      AS flagged,
    SUM(CASE WHEN flag = 1 AND y = 1 THEN 1 ELSE 0 END)
        * 1.0 / NULLIF(SUM(CASE WHEN flag = 1 THEN 1 ELSE 0 END), 0) AS precision,
    SUM(CASE WHEN flag = 1 AND y = 1 THEN 1 ELSE 0 END)
        * 1.0 / NULLIF(SUM(y), 0)                                  AS recall
FROM staging.fraud_scored_labeled
GROUP BY threshold;
-- θ* = total_cost 最小的 threshold；基准：θ*=0.5388、拦截 0.11%、召回 74.7%、精确率 90.3%
-- 误杀成本敏感性：¥50→0.4568、¥120→0.5388、¥300→0.9986

-- 3) 规则引擎：精确率与召回（前置实时拦截）
SELECT rule_id, rule_expr,
       SUM(CASE WHEN y = 1 THEN 1 ELSE 0 END) * 1.0
           / NULLIF(COUNT(*), 0)                                   AS rule_precision,
       SUM(CASE WHEN y = 1 THEN 1 ELSE 0 END) * 1.0
           / NULLIF((SELECT SUM(y) FROM staging.fraud_scored_labeled), 0) AS rule_recall
FROM staging.fraud_rule_hits
GROUP BY rule_id, rule_expr
HAVING rule_precision >= 10 * ${base_rate};                        -- 精确率 ≥ 10 倍基准
-- 基准：V14/V4/V12 组合规则精确率 23.3%（基准 177 倍）、召回 73.3%

-- 4) 四指标监控（日跑，越线告警）
WITH recent AS (
    SELECT psi_score_bin, COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS recent_pct
    FROM dw.fraud_score_daily
    WHERE dt BETWEEN DATE_SUB('${bizdate}', 30) AND '${bizdate}'
    GROUP BY psi_score_bin
),
base AS (
    SELECT psi_score_bin, train_pct FROM staging.fraud_score_baseline
)
SELECT
    (SELECT SUM((r.recent_pct - b.train_pct) * LN(r.recent_pct / b.train_pct))
     FROM recent r JOIN base b ON r.psi_score_bin = b.psi_score_bin)          AS psi_score,
    precision_at_threshold,
    topk_precision,
    cost_per_1000_txn
FROM staging.fraud_monitoring_daily
WHERE dt = '${bizdate}';
-- 告警线：PSI > 0.25 / 精确率 < 0.15 / Top-500 精确率 < 0.10 / 每千笔成本环比 +50%
-- 基准值：PSI 0.0014、阈值精确率 0.9032、Top-500 精确率 0.128、每千笔成本 ¥75.7

-- 5) 人工抽检回流（校准成本矩阵 fp_cost / miss_fixed）
SELECT sample_id, manual_label, model_flag,
       CASE WHEN model_flag = 1 AND manual_label = 0 THEN '误杀' ELSE '其他' END AS sample_type
FROM staging.fraud_manual_audit
WHERE dt = '${bizdate}';
-- 用途：用抽检结果校准 fp_cost（真实客诉成本）与 miss_fixed（调查成本）→ 重算 θ*
