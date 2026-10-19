-- =============================================================
-- extract.sql：客户流失分析宽表（T+1 日更）
-- 用途：从数仓拉取建模宽表，字段与 notebooks/churn_economics.ipynb 对齐
-- 说明：演示版为 Hive/Spark SQL 语法；生产环境按事件时间戳增量抽取
-- =============================================================

-- 1) 客户属性与合同（快照表，每日全量分区）
WITH cust_base AS (
    SELECT
        customer_id            AS customerID,
        gender,
        CASE WHEN senior_flag = 1 THEN 1 ELSE 0 END          AS SeniorCitizen,
        partner_flag                                        AS Partner,
        dependents_flag                                     AS Dependents,
        tenure_months                                       AS tenure,
        phone_service_flag                                  AS PhoneService,
        multiple_lines_flag                                 AS MultipleLines,
        internet_service_type                               AS InternetService,
        online_security_flag                                AS OnlineSecurity,
        online_backup_flag                                  AS OnlineBackup,
        device_protection_flag                              AS DeviceProtection,
        tech_support_flag                                   AS TechSupport,
        streaming_tv_flag                                   AS StreamingTV,
        streaming_movies_flag                               AS StreamingMovies,
        contract_type                                       AS Contract,
        paperless_billing_flag                              AS PaperlessBilling,
        payment_method                                      AS PaymentMethod,
        monthly_charges                                     AS MonthlyCharges,
        COALESCE(total_charges, 0.0)                        AS TotalCharges,
        -- 流失标签：观察期末合同状态；生产应以事件表 end_date 推导
        CASE WHEN contract_status = 'Churned' THEN 1 ELSE 0 END AS Churn,
        dt
    FROM dw.customer_contract_snapshot
    WHERE dt = '${bizdate}'                 -- 分区参数，由调度系统注入
),

-- 2) 服务订阅数（RFM 的 F 代理）
svc_cnt AS (
    SELECT
        customer_id,
        (phone_service_flag + multiple_lines_flag + online_security_flag
         + online_backup_flag + device_protection_flag + tech_support_flag
         + streaming_tv_flag + streaming_movies_flag)          AS F_services
    FROM dw.customer_contract_snapshot
    WHERE dt = '${bizdate}'
)

-- 3) 建模宽表：与 Notebook FEATS 列一一对应
SELECT
    b.customerID, b.gender, b.SeniorCitizen, b.Partner, b.Dependents,
    b.tenure, b.PhoneService, b.MultipleLines, b.InternetService,
    b.OnlineSecurity, b.OnlineBackup, b.DeviceProtection, b.TechSupport,
    b.StreamingTV, b.StreamingMovies, b.Contract, b.PaperlessBilling,
    b.PaymentMethod, b.MonthlyCharges, b.TotalCharges, b.Churn,
    s.F_services
FROM cust_base b
LEFT JOIN svc_cnt s
    ON b.customerID = s.customer_id
;

-- 4) 模型输出回写（评分表，供运营系统拉取挽留名单）
-- INSERT OVERWRITE TABLE dw.churn_score_daily PARTITION (dt = '${bizdate}')
-- SELECT customerID, churn_prob, ltv, expected_save, model_version
-- FROM staging.churn_score_output;
