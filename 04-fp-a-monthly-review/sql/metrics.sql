-- =============================================================
-- metrics.sql：月度经营分析包的经营指标口径（生产可复现）
-- 用途：把 docs/metrics.md 中的指标落成数仓 SQL，供月度经营例会与周度资金监控使用
-- 依赖：dw.monthly_pnl_snapshot、dw.monthly_budget、dw.weekly_cash_flow
-- 说明：演示版为 Hive/Spark SQL 语法；流动性口径与盈利口径分开计算
-- =============================================================

-- 1) 预算差异：中值法量价分解（月跑，恒等式校验）
SELECT
    f.month_id,
    (f.net_interest_margin - b.budget_nim)
        * (f.origination_amount + b.budget_volume) / 2                     AS price_effect,
    (f.origination_amount - b.budget_volume)
        * (f.net_interest_margin + b.budget_nim) / 2                       AS volume_effect,
    f.net_revenue - b.budget_nim * b.budget_volume                         AS total_variance,
    ABS((f.net_interest_margin - b.budget_nim)
        * (f.origination_amount + b.budget_volume) / 2
      + (f.origination_amount - b.budget_volume)
        * (f.net_interest_margin + b.budget_nim) / 2
      - (f.net_revenue - b.budget_nim * b.budget_volume))                  AS identity_residual
FROM dw.monthly_pnl_snapshot f
JOIN dw.monthly_budget b
  ON f.month_id = b.month_id
 AND b.budget_version = (SELECT MAX(budget_version) FROM dw.monthly_budget
                         WHERE month_id = '${bizmonth}')
WHERE f.month_id = '${bizmonth}';
-- 红线：identity_residual > 1e-6 → 归因公式或数据有问题，告警
-- 基准：价差 ¥−1.9、量差 ¥+9.0、合计 ¥+7.1 万

-- 2) 流动性：13 周现金跑道与缓冲线击穿
WITH runway AS (
    SELECT week_no,
           4500.0 + SUM(inflow - outflow)
               OVER (ORDER BY week_no)                                     AS cash_balance
    FROM dw.weekly_cash_flow
    WHERE week_no <= 13
)
SELECT
    MIN(week_no) FILTER (WHERE cash_balance < 3000)                        AS first_breach_week,
    MIN(cash_balance)                                                      AS min_cash,
    GREATEST(0, 3000 - MIN(cash_balance))                                  AS funding_gap
FROM runway;
-- 基准：第 6 周击穿缓冲、第 13 周见底 ¥80 万、缺口 ¥2,920 万
-- 红线：现金余额 < 缓冲线（¥3,000 万）→ 当日启动融资流程

-- 3) 回收系数监控（周跑，计算周回收 ÷ 周新放款）
SELECT w.week_no,
       w.collection / NULLIF(o.origination, 0)                             AS recovery_ratio,
       ABS(w.collection / NULLIF(o.origination, 0) - 0.92)                 AS deviation_from_base
FROM (SELECT week_no, SUM(amount) AS collection FROM dw.weekly_cash_flow
      WHERE flow_type = 'collection' GROUP BY week_no) w
JOIN (SELECT week_no, SUM(amount) AS origination FROM dw.weekly_cash_flow
      WHERE flow_type = 'origination' GROUP BY week_no) o
  ON w.week_no = o.week_no;
-- 红线：deviation_from_base > 0.02（偏离基准 2pp）→ 重跑 13 周预测与融资建议

-- 4) 盈利口径：三情景损益前瞻（12 个月，损益口径不含本金）
--    利润 = 放款量 × (NIM − 获客率 − 损失率) − 运营成本
SELECT scenario,
       SUM(revenue)                                                        AS revenue_total,
       SUM(op_profit)                                                      AS profit_total,
       SUM(op_profit) / NULLIF(SUM(revenue), 0)                            AS margin,
       MAX(CASE WHEN month_seq = 12 THEN op_profit END)                    AS dec_profit
FROM staging.scenario_pl_forward
GROUP BY scenario;
-- 基准：Base ¥337 万（13.5%）/ Bull ¥724 万（26.0%）/ Bear ¥−179 万（−8.3%）

-- 5) 融资建议口径：额度 = 压力情形缺口；首笔 = 点预测缺口；时点 = 击穿周 − 2 周
SELECT
    -- 授信额度：80% 悲观边界缺口向上取整
    CEIL((3000 - ${pessimistic_min_cash}) / 1000) * 1000                   AS credit_line,
    -- 首笔提取：点预测缺口向上取整
    CEIL(${point_gap} / 1000) * 1000                                       AS first_drawdown,
    ${first_breach_week} - 2                                               AS drawdown_week;
-- 基准：授信 ¥7,500 万、首笔 ¥3,000 万、第 4 周前

-- 6) 经营例会指标看板（月跑）
SELECT month_id,
       net_revenue, op_profit,
       op_profit / NULLIF(net_revenue, 0)                                  AS margin,
       acquisition_cost / NULLIF(origination_amount, 0)                    AS cac_rate,
       credit_loss / NULLIF(origination_amount, 0)                         AS loss_rate
FROM dw.monthly_pnl_snapshot
WHERE month_id >= DATE_SUB('${bizmonth}', 12);
-- 告警：净收入率环比 −5% / 信用损失率环比 +10% → 触发假设回顾
