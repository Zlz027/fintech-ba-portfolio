-- =============================================================
-- extract.sql：欺诈检测交易特征宽表（准实时，T+0）
-- 用途：从数仓拉取授权交易流水 + 设备/行为特征，字段与
--       notebooks/fraud_threshold_optimization.ipynb 对齐
-- 说明：演示版为 Hive/Spark SQL 语法；生产环境 Time 用毫秒时间戳，
--       按事件时间做训练/测试切分（严禁随机切分，见 BRD F-03）
-- =============================================================

-- 1) 交易事实表（按授权时间排序，Time 为秒级偏移）
WITH txn AS (
    SELECT
        txn_id,
        card_id,
        -- 时间：事件时间戳（毫秒），建模时转秒并归一化
        (auth_time - to_unix_timestamp('${bizdate}')) / 1000        AS time,
        amount,
        -- 标签：拒付/争议确认（T+90 天回填，表现期）
        CASE WHEN chargeback_status = 'confirmed' THEN 1 ELSE 0 END  AS class,
        -- V1-V28：PCA 脱敏特征（生产环境对应原始行为/设备变量，
        -- 由特征平台每日重算，字段口径冻结在 dw.feature_dict）
        v1, v2, v3, v4, v5, v6, v7, v8, v9, v10,
        v11, v12, v13, v14, v15, v16, v17, v18, v19, v20,
        v21, v22, v23, v24, v25, v26, v27, v28
    FROM dw.card_auth_txn
    WHERE dt = '${bizdate}'
      AND auth_result = 'approved'
      AND chargeback_status IS NOT NULL       -- 表现期已到期
),

-- 2) 金额稳健化：对数压缩（欺诈金额长尾，直接入模会被极值主导）
amt_log AS (
    SELECT txn_id, txn.* EXCEPT (txn_id, amount),
           log1p(amount) AS amount_log
    FROM txn
),

-- 3) 成本矩阵参数（财务部季度校准，入库留痕）
cost_param AS (
    SELECT 120.0 AS fp_cost,    -- 误杀：人工审核 ¥30 + 客户体验/流失 ¥90
           50.0  AS miss_fixed  -- 漏判固定部分：运营/调查成本（漏判另计欺诈金额全额）
)

-- 4) 建模宽表
SELECT a.*, c.fp_cost, c.miss_fixed
FROM amt_log a CROSS JOIN cost_param c
;

-- 5) 模型评分与阈值结果回写（供实时决策引擎拉取）
-- INSERT OVERWRITE TABLE dw.fraud_score_daily PARTITION (dt = '${bizdate}')
-- SELECT txn_id, card_id, p_fraud, flag, threshold_version, model_version
-- FROM staging.fraud_score_output
-- WHERE flag = 1;   -- 仅拦截名单进决策引擎

-- 6) 监控：最优阈值下的四个核心指标（日跑，越线告警）
-- SELECT dt,
--        psi_score,                      -- 评分分布 PSI（>0.25 告警）
--        precision_at_threshold,         -- 拦截精确率（<0.15 告警）
--        topk_precision,                 -- Top-500 精确率（<0.10 告警）
--        cost_per_1000_txn               -- 每千笔期望成本（环比 +50% 告警）
-- FROM staging.fraud_monitoring_daily;
