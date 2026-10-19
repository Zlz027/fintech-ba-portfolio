-- ============================================================================
-- MVP3 金融风控 SQL 查询集 · 建表与数据导入脚本（setup.sql）
-- 数据源：Kaggle "Give Me Some Credit" (GMSC) 竞赛数据 cs-training.csv
--         150,000 条客户信贷记录，11 个特征字段 + 1 个索引列
-- 运行方式：将 cs-training.csv 放在本目录，然后执行
--           sqlite3 credit.db < setup.sql
-- 说明：本脚本可重复执行（每次先 DROP 再重建，保证幂等）
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- 1. 主表 credit_data：一笔一行，存储客户信贷明细
--    字段命名统一为小写下划线（snake_case）；列顺序与 CSV 完全一致，
--    以便直接使用 .import 按位置导入。
--    原版 Kaggle 字段 -> 本表字段 映射：
--      SeriousDlqin2yrs                        -> serious_dlqin2yrs（1=两年内严重违约）
--      RevolvingUtilizationOfUnsecuredLines    -> revolving_utilization（信用利用率）
--      age                                     -> age（年龄）
--      NumberOfTime30-59DaysPastDueNotWorse    -> number_of_time_30_59_days_past_due_not_worse
--      DebtRatio                               -> debt_ratio（债务收入比）
--      MonthlyIncome                           -> monthly_income（月收入，允许缺失）
--      NumberOfOpenCreditLinesAndLoans         -> number_of_open_credit_lines_and_loans
--      NumberOfTimes90DaysLate                 -> number_of_times_90_days_late
--      NumberRealEstateLoansOrLines            -> number_real_estate_loans_or_lines
--      NumberOfTime60-89DaysPastDueNotWorse    -> number_of_time_60_89_days_past_due_not_worse
--      NumberOfDependents                      -> number_of_dependents（供养人数，允许缺失）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS credit_data;
CREATE TABLE credit_data (
    id                                            INTEGER PRIMARY KEY,
    serious_dlqin2yrs                             INTEGER NOT NULL CHECK (serious_dlqin2yrs IN (0, 1)),
    revolving_utilization                         REAL    NOT NULL,
    age                                           INTEGER NOT NULL CHECK (age >= 0 AND age <= 120),
    number_of_time_30_59_days_past_due_not_worse  INTEGER NOT NULL,
    debt_ratio                                    REAL    NOT NULL,
    monthly_income                                REAL,           -- 原数据存在缺失
    number_of_open_credit_lines_and_loans          INTEGER NOT NULL,
    number_of_times_90_days_late                  INTEGER NOT NULL,
    number_real_estate_loans_or_lines             INTEGER NOT NULL,
    number_of_time_60_89_days_past_due_not_worse  INTEGER NOT NULL,
    number_of_dependents                          INTEGER         -- 原数据存在缺失
);

-- ----------------------------------------------------------------------------
-- 2. 维度表 score_dim：信用分分段维度（人为构建，用于演示多表 JOIN）
--    GMSC 原始数据不含信用评分字段，按风控行业常识构造映射：
--     revolving_utilization（信用利用率）越低 -> 模拟信用分越高 -> 风险等级越低。
--    score_band 为主键，util_min/util_max 为与主表关联的区间键（左闭右开）。
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS score_dim;
CREATE TABLE score_dim (
    score_band TEXT    PRIMARY KEY,   -- 信用分区间标签
    score_min  INTEGER NOT NULL,      -- 区间下限
    score_max  INTEGER NOT NULL,      -- 区间上限
    util_min   REAL    NOT NULL,      -- 对应信用利用率下限（含）
    util_max   REAL    NOT NULL,      -- 对应信用利用率上限（不含）
    risk_level TEXT    NOT NULL       -- 风险等级
);

INSERT INTO score_dim (score_band, score_min, score_max, util_min, util_max, risk_level) VALUES
    ('801-900', 801, 900, 0.0,     0.2,    '低'),
    ('701-800', 701, 800, 0.2,     0.4,    '中低'),
    ('601-700', 601, 700, 0.4,     0.6,    '中'),
    ('501-600', 501, 600, 0.6,     0.8,    '中高'),
    ('0-500',    0,  500, 0.8,  999999.0,   '高');   -- 999999.0 为上限哨兵值：覆盖利用率 >100% 的极端客户

-- ----------------------------------------------------------------------------
-- 3. 导入 CSV 数据（SQLite 3.32+ 支持 .import --csv --skip）
--    --skip 1：跳过首行表头；表头第一列为无名字段（原数据索引列），无需处理。
--    注意：.import 会把 CSV 中的空字段导入为空字符串 ''，下一步统一转为 NULL。
-- ----------------------------------------------------------------------------
.mode csv
.import --csv --skip 1 cs-training.csv credit_data

-- ----------------------------------------------------------------------------
-- 4. 缺失值规范化：非数字文本 -> NULL
--    .import 会把 CSV 中的空字段导入为空字符串 ''；本数据源由 R 导出，
--    缺失值被序列化为字符串 'NA'。两种情况统一转换为真正的 SQL NULL，
--    保证 IS NULL 统计与后续聚合计算正确。
--    （MonthlyIncome 缺失 29,731 条，NumberOfDependents 缺失 3,924 条）
--    用事务包裹，保证两步 UPDATE 要么全部生效要么全部回滚。
-- ----------------------------------------------------------------------------
BEGIN TRANSACTION;
UPDATE credit_data SET monthly_income       = NULL WHERE monthly_income       IN ('', 'NA');
UPDATE credit_data SET number_of_dependents = NULL WHERE number_of_dependents IN ('', 'NA');
COMMIT;

-- ----------------------------------------------------------------------------
-- 5. 导入结果自检（运行后应看到：150000 行 / 违约客户数 10026 / 收入缺失 29731）
-- ----------------------------------------------------------------------------
SELECT 'total_rows'        AS metric, COUNT(*)                                AS value FROM credit_data
UNION ALL
SELECT 'default_customers', SUM(serious_dlqin2yrs)                                        FROM credit_data
UNION ALL
SELECT 'income_missing',    SUM(CASE WHEN monthly_income IS NULL THEN 1 ELSE 0 END)       FROM credit_data
UNION ALL
SELECT 'dependents_missing',SUM(CASE WHEN number_of_dependents IS NULL THEN 1 ELSE 0 END) FROM credit_data;
