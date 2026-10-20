# 指标字典：客户流失预测与留存经济性

> **用途**：把 Notebook 中的每个指标落成生产口径——定义、公式、验收线、数据来源。
> **原则**：指标先定义再计算；每个指标都能用 `sql/metrics.sql` 在数仓中复现。
> **单位约定**：金额为元（CNY），周期为月。

## 1. 模型区分度指标

| 指标 | 定义 | 公式 | 验收线 | 来源 |
|---|---|---|---|---|
| **AUC** | 随机取一留存一流失，模型给流失客户更高概率的概率 | ROC 曲线下面积 | ≥ 0.75 | `outputs/metrics.json` |
| **KS** | 留存/流失样本累积分布最大间距 | max\|F_retained(s) − F_churned(s)\| | ≥ 0.35 | `outputs/metrics.json` |
| **PR-AUC** | 精确率-召回率曲线下面积（流失不均衡时的补充指标） | — | 高于基准流失率 | `outputs/metrics.json` |
| **Cohort AUC** | 分在网时长（tenure）子群的 AUC | 同 AUC | 各 cohort ≥ 0.75 | `outputs/metrics.json` |

**本项目实测**（`outputs/metrics.json`）：

| 模型 | AUC | KS | PR-AUC |
|---|---|---|---|
| LogisticRegression | 0.8422 | 0.5210 | 0.6350 |
| XGBoost | 0.8345 | 0.5243 | 0.6419 |
| XGB cohort tenure 0-12（n=449） | 0.7629 | 0.4041 | 0.7347 |
| XGB cohort tenure 13-36（n=369） | 0.7981 | 0.4963 | 0.5452 |
| XGB cohort tenure 37-72（n=591） | 0.7824 | 0.4509 | 0.2791 |

## 2. 价值与风险指标

| 指标 | 定义 | 公式 | 来源 |
|---|---|---|---|
| **折现 LTV** | horizon=36 个月折现期望毛利贡献 | `Σ_m MonthlyCharges × 毛利率 × S(tenure+m) / (1+r)^m` | `src/finance.discounted_ltv` |
| **收入风险敞口 RaR** | 未来 12 个月期望收入流失 | `Σ MonthlyCharges × p_churn × 12` | `src/finance.revenue_at_risk` |
| **期望保住收益** | 单客户挽留的期望收益 | `p_churn × uplift × LTV` | `outputs/priority_retention_list.csv` |
| **留存曲线 S(t)** | Kaplan-Meier 生存函数 | 自实现（避免额外依赖） | `src/finance.km_survival` |

**口径要点**：
- 毛利率默认 0.60（与财务确认后锁定）；折现率 r 与财务统一；
- KM 生存函数用于把 tenure 处的中位留存外推至 36 个月——**存在长度偏差**，生产应以 cohort 留存表替代（见局限性）。

## 3. 挽留经济性指标

| 指标 | 定义 | 公式 | 来源 |
|---|---|---|---|
| **最优触达规模 N\*** | 累计净利润最大的触达人数（边际收益=边际成本） | argmax_n [cum_gain(n) − cum_cost(n)] | `outputs/uplift_sensitivity.csv` |
| **触达预算** | N\* 对应的总成本 | Σ 前 N 名的触达成本 | `outputs/uplift_sensitivity.csv` |
| **净利润** | 累计期望收益 − 累计成本 | — | `outputs/uplift_sensitivity.csv` |
| **毛 ROI** | 累计收益 / 累计成本 | cum_gain / cum_cost | `outputs/uplift_sensitivity.csv` |

**ROI 口径说明**：本项目 ROI 为**毛 ROI**（收益/成本），与净利/成本的"净 ROI"不同，引用时必须标明口径。基准（uplift=30%）：N\*=550、净收益 ¥62,468、毛 ROI 2.62。

**挽留成功率敏感性**（uplift ∈ {10%, 20%, 30%, 40%}）：

| 挽留成功率 | 最优触达 N\* | 触达预算 | 净收益 | 毛 ROI |
|---|---|---|---|---|
| 10% | 182 | ¥12,740 | ¥4,835 | 1.38 |
| 20% | 436 | ¥30,520 | ¥30,241 | 1.99 |
| **30%（基准）** | **550** | **¥38,500** | **¥62,468** | **2.62** |
| 40% | 622 | ¥43,540 | ¥96,925 | 3.23 |

## 4. 口径红线（生产必须遵守）

1. **uplift 未校准前不做全量触达**：N\* 依赖 uplift 假设，必须先做 A/B 实验校准再放量；
2. **LTV 口径需与财务统一**：毛利率、折现率、horizon 三者任一变都会改变 N\*；
3. **PII 不出域**：评分结果只输出客户 ID 与分数，原始 PII 不回写分析环境；
4. **触达合规**：不得向敏感客群过度营销，名单触达前过合规审查。

---

*本文件为分析工作底稿，不构成投资建议；指标口径需经经营分析与财务部复核签署后生效。*
