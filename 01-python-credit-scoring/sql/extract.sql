-- =============================================================
-- extract.sql：信用风险建模宽表（T+1 日更）
-- 用途：从数仓拉取申请人征信宽表，字段与 notebooks/credit_risk_pricing.ipynb 对齐
-- 说明：演示版为 Hive/Spark SQL 语法；生产环境按申请时间戳做 OOT 切分
-- =============================================================

-- 1) 申请人征信宽表（当月新增申请快照）
WITH applicants AS (
    SELECT
        applicant_id,
        -- 循环额度利用率（>1 为超额，入模前按 p99.9 截尾）
        LEAST(revolving_utilization, 0.9999999)              AS revolving_utilization,
        age,
        -- 逾期次数（征信标准口径，0/1/2/3+）
        times_30_59_dpd                                     AS num_time_30_59_dpd,
        times_60_89_dpd                                     AS num_time_60_89_dpd,
        times_90_dpd                                        AS num_times_90_dpd,
        debt_ratio,
        monthly_income,                                     -- 缺失 19.8%，WOE 入最低箱
        num_open_credit_lines,
        num_real_estate_loans,
        num_dependents,                                     -- 缺失 2.6%
        -- 标签：未来两年是否发生财务困境（表现期 24 个月回填）
        serious_dlqin_2yrs                                  AS y,
        apply_date
    FROM dw.credit_application_snapshot
    WHERE apply_month = '${bizmonth}'                       -- 分区参数
      AND serious_dlqin_2yrs IS NOT NULL                    -- 表现期已到期
),

-- 2) 收入缺失指示（XGBoost 特征）
income_na AS (
    SELECT applicant_id,
           CASE WHEN monthly_income IS NULL THEN 1 ELSE 0 END AS income_na
    FROM applicants
)

-- 3) 建模宽表
SELECT
    a.applicant_id, a.revolving_utilization, a.age,
    a.num_time_30_59_dpd, a.num_time_60_89_dpd, a.num_times_90_dpd,
    a.debt_ratio,
    COALESCE(a.monthly_income, -1)                          AS monthly_income,  -- -1=缺失并入最低箱
    a.num_open_credit_lines, a.num_real_estate_loans,
    COALESCE(a.num_dependents, -1)                          AS num_dependents,
    i.income_na,
    a.y, a.apply_date
FROM applicants a
LEFT JOIN income_na i ON a.applicant_id = i.applicant_id
;

-- 4) 评分与定价结果回写（供审批引擎与定价引擎拉取）
-- INSERT OVERWRITE TABLE dw.credit_score_daily PARTITION (dt = '${bizdate}')
-- SELECT applicant_id, pd, score, breakeven_rate, suggested_rate, model_version
-- FROM staging.credit_pricing_output;

-- 5) 监控：评分 PSI（近 30 天 vs 训练基准）按月跑
-- SELECT score_bin,
--        train_pct, recent_pct,
--        (recent_pct - train_pct) * ln(recent_pct / train_pct) AS psi_contrib
-- FROM staging.score_psi_calc
-- HAVING SUM(psi_contrib) OVER () > 0.25;   -- 触发重训评审
