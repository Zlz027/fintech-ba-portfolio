"""共享财务函数库：客户流失项目的 LTV / 挽留 ROI 计算。

设计原则：
- 每个函数只做一件事，公式与参数在 docstring 中写明，便于复核；
- 不依赖项目特定数据，可被其他项目的 Notebook import；
- 所有金额单位为元（CNY），周期单位为月。
"""
from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------- 生存分析与留存期
def km_survival(times: np.ndarray, events: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Kaplan-Meier 生存函数（自实现，避免额外依赖）。

    返回 (surv_times, surv_probs)：surv_probs[i] = P(T > surv_times[i])。
    """
    order = np.argsort(times)
    t, e = times[order], events[order]
    uniq = np.unique(t)
    n = len(t)
    surv, s = [1.0], 1.0
    for tt in uniq:
        at_risk = (t >= tt).sum()
        d = ((t == tt) & (e == 1)).sum()
        if at_risk > 0:
            s *= 1.0 - d / at_risk
        surv.append(s)
    return uniq, np.array(surv[1:])


def expected_remaining_months(
    tenure: np.ndarray, surv_times: np.ndarray, surv_probs: np.ndarray, horizon: int = 36
) -> np.ndarray:
    """给定当前 tenure，按 KM 曲线计算 horizon 个月内的期望剩余留存月数。

    E[min(remaining, H)] = sum_{m=1..H} S(tenure + m)，S 为 Kaplan-Meier 生存函数。
    这是"折现前"的期望在网月数，天然处理右删失，无需假设参数分布。
    """
    out = np.zeros(len(tenure))
    for m in range(1, horizon + 1):
        out += np.interp(tenure + m, surv_times, surv_probs, left=1.0, right=surv_probs[-1])
    return out


# ---------------------------------------------------------------- 折现 LTV
def discounted_ltv(
    monthly_revenue: np.ndarray,
    tenure: np.ndarray,
    surv_times: np.ndarray,
    surv_probs: np.ndarray,
    gross_margin: float = 0.60,
    annual_discount: float = 0.10,
    horizon: int = 36,
) -> np.ndarray:
    """折现期望 LTV（月粒度）。

    公式：LTV = sum_{m=1..H} [MonthlyCharges * gross_margin * S(tenure+m)] / (1+r_m)^m
    其中 r_m = (1+annual_discount)^(1/12) - 1 为月度折现率。

    参数
    -----
    monthly_revenue : 月收入（MonthlyCharges）
    tenure          : 已在网月数
    gross_margin    : 毛利率（收入扣除服务成本后的边际贡献率）
    annual_discount : 年化折现率
    horizon         : 预测 horizon（月），默认 36
    """
    r_m = (1.0 + annual_discount) ** (1.0 / 12.0) - 1.0
    ltv = np.zeros(len(monthly_revenue))
    for m in range(1, horizon + 1):
        s = np.interp(tenure + m, surv_times, surv_probs, left=1.0, right=surv_probs[-1])
        ltv += monthly_revenue * gross_margin * s / (1.0 + r_m) ** m
    return ltv


# ---------------------------------------------------------------- 挽留 ROI
def campaign_roi(
    churn_prob: np.ndarray,
    ltv: np.ndarray,
    gross_margin: float = 0.60,
    uplift: float = 0.30,
    contact_cost: float = 20.0,
    benefit_cost: float = 50.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """挽留活动 ROI（按期望收益 p*uplift*LTV 降序触达前 N 名客户）。

    收益模型（可落地假设，均可在 README 中调整）：
    - 干预使目标客户流失概率相对下降 uplift 比例（相对值），即 p -> p*(1-uplift)；
    - 单客户保住期望毛利 = p * uplift * LTV（传入的 ltv 为"含毛利"口径，
      即 discounted_ltv 的输出，gross_margin 已在 LTV 中计入，此处不再重复相乘）；
    - 成本_i = contact_cost + benefit_cost

    排序口径：按"期望保住收益" p*uplift*LTV 降序——高概率低价值客户不应优先于
    中概率高价值客户，这与优先挽留名单口径一致。

    返回 (roi_curve, cost_curve, net_curve)：
    - roi_curve[N-1]  = 累计收益 / 累计成本
    - cost_curve[N-1] = N * (contact_cost + benefit_cost)
    - net_curve[N-1]  = 累计收益 - 累计成本（净利润，其峰值即最优触达规模）
    """
    score = churn_prob * uplift * ltv
    idx = np.argsort(-score)
    p, v = churn_prob[idx], ltv[idx]
    gain_per = p * uplift * v
    cost_per = contact_cost + benefit_cost
    cum_gain = np.cumsum(gain_per)
    cum_cost = np.cumsum(np.full(len(p), cost_per))
    with np.errstate(divide="ignore", invalid="ignore"):
        roi = np.where(cum_cost > 0, cum_gain / cum_cost, np.nan)
    return roi, cum_cost, cum_gain - cum_cost


# ---------------------------------------------------------------- 收入风险敞口
def revenue_at_risk(monthly_revenue: np.ndarray, churn_prob: np.ndarray, horizon: int = 12) -> float:
    """未来 horizon 个月的期望收入流失（年化口径，未折现）。

    公式：RaR = sum_i( MonthlyCharges_i * p_i ) * horizon
    即"按当前风险加权"的月收入流失速度乘以 horizon。
    """
    return float(np.sum(monthly_revenue * churn_prob) * horizon)
