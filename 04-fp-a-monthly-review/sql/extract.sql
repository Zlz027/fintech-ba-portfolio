-- =============================================================
-- extract.sql：月度经营分析宽表（损益 + 预算 + 周度现金流）
-- 用途：从数仓拉取月度损益（含预算版本）与周度现金流流水，
--       字段与 notebooks/monthly_business_pack.ipynb 对齐
-- 说明：演示版为 Hive/Spark SQL 语法；生产环境预算表需带版本号（budget_version）
-- =============================================================

-- 1) 月度损益事实（放款流量口径）
WITH monthly_fact AS (
    SELECT
        month_id,                                        -- 'YYYY-MM'
        origination_amount,                              -- 放款量（万元）
        net_interest_margin,                             -- 月净收入率（小数）
        net_revenue,                                     -- 净收入 = 放款量 × 净收入率
        acquisition_cost,                                -- 获客成本
        operating_cost,                                  -- 运营成本（固定+变动）
        credit_loss,                                     -- 信用损失（净回收后）
        op_profit                                        -- 经营利润
    FROM dw.monthly_pnl_snapshot
    WHERE month_id <= '${bizmonth}'                      -- 截至参数月
),

-- 2) 最新月预算（当前生效版本，按版本号取最新）
monthly_budget AS (
    SELECT month_id,
           budget_origination AS budget_volume,
           budget_nim         AS budget_nim
    FROM dw.monthly_budget
    WHERE month_id = '${bizmonth}'
      AND budget_version = (SELECT MAX(budget_version) FROM dw.monthly_budget
                            WHERE month_id = '${bizmonth}')
),

-- 3) 周度现金流流水（流入=存量回收；流出=新放款+获客+运营+信用损失+营销脉冲）
weekly_cash AS (
    SELECT
        week_no,                                         -- 周序号
        SUM(CASE WHEN flow_type = 'collection' THEN amount ELSE 0 END) AS inflow,
        SUM(CASE WHEN flow_type IN ('origination', 'acquisition', 'operating',
                                    'credit_loss', 'marketing_pulse')
                 THEN amount ELSE 0 END)                 AS outflow
    FROM dw.weekly_cash_flow
    WHERE week_no <= 52
    GROUP BY week_no
)

-- 4) 建模宽表（月度损益左连预算）
SELECT f.*, b.budget_volume, b.budget_nim
FROM monthly_fact f
LEFT JOIN monthly_budget b ON f.month_id = b.month_id
ORDER BY f.month_id
;

-- 5) 监控：预算差异中值法分解（月跑，进经营分析例会）
-- SELECT month_id,
--        (nim - budget_nim) * (volume + budget_volume) / 2        AS price_effect,
--        (volume - budget_volume) * (nim + budget_nim) / 2        AS volume_effect,
--        net_revenue - budget_nim * budget_volume                 AS total_variance
-- FROM staging.pnl_with_budget
-- HAVING ABS(price_effect + volume_effect - total_variance) > 1e-6;  -- 恒等式校验失败即告警

-- 6) 监控：13 周现金跑道（周跑，击穿缓冲线即升级资金计划会）
-- SELECT week_no, cash_balance,
--        CASE WHEN cash_balance < 3000 THEN 1 ELSE 0 END          AS below_buffer
-- FROM staging.cash_runway_13w
-- WHERE below_buffer = 1
-- ORDER BY week_no LIMIT 1;   -- 首个击穿周
