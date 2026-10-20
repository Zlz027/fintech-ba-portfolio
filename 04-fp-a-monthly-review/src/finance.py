"""共享财务函数库：Fintech 月度经营分析包（13 周现金流 / 预算差异 / 三情景 / 融资缺口）。

四个模块共用的计算原语：
- simulate_company：生成 24 个月月度损益（含预算）+ 52 周现金流（固定种子，可复现）；
- holt_forecast / fit_holt / forecast_band：13 周现金流预测与 80% 预测区间；
- pv_variance：预算差异的中值法价量分解（价差+量差恒等于总差异）；
- cash_runway / funding_gap：流动性跑道与融资缺口；
- scenario_pl：三情景损益前瞻。

设计原则：纯函数、参数化假设、返回结构化结果；不读写文件、不打印、不依赖项目数据。
单位约定：金额一律为万元。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SEED = 42


# ---------------------------------------------------------------- 数据模拟
def simulate_company(n_months: int = 24, n_weeks: int = 52, seed: int = SEED,
                     recovery_rate: float = 0.92):
    """模拟"星链数科"消费信贷平台：月度损益（含预算列）+ 周度现金流。

    月度口径（万元）：净收入 = 放款量 × 月净收入率；经营利润 = 净收入 − 获客 − 运营 − 信用损失。
    周度口径（万元）：流入 = 存量回收（≈放款量 × 回收系数 recovery_rate，基准 0.92）；流出 = 新放款
    + 获客 + 运营 + 信用损失 + 季度末营销脉冲。增长期回收系数 < 1 → 本金净投放 → 经营现金流为负，
    这是融资需求的来源（流动性口径），与损益口径分开报告。

    recovery_rate 为敏感性分析参数（见 sensitivity_analysis.py），默认 0.92 与基准一致。

    返回 (monthly, weekly, opening_cash)。
    """
    rng = np.random.default_rng(seed)
    months = pd.period_range("2023-01", periods=n_months, freq="M")
    t = np.arange(n_months)
    season = np.where(months.month.isin([1, 2]), -0.15, np.where(months.month.isin([11, 12]), 0.10, 0.0))
    vol = 6000 * 1.018 ** t * (1 + season) * (1 + rng.normal(0, 0.03, n_months))       # 放款量
    nim = np.clip(0.0195 - 0.00002 * t + rng.normal(0, 0.00008, n_months), 0.0155, 0.0210)  # 月净收入率
    cac = np.clip(0.0050 + 0.00001 * t + rng.normal(0, 0.00008, n_months), 0.0045, 0.0060)  # 获客成本率
    loss = np.clip(0.0062 + rng.normal(0, 0.0004, n_months), 0.0045, 0.0080)                # 月信用损失率
    loss[(months.year == 2024) & (months.month == 6)] += 0.0015                             # 2024-06 风险事件
    opex = 45 * 1.003 ** t + vol * 0.0012                                                   # 运营成本（固定+变动）
    rev = vol * nim
    profit = rev - vol * (cac + loss) - opex
    monthly = pd.DataFrame({
        "month": months.astype(str), "volume": vol.round(1), "nim": nim.round(5),
        "revenue": rev.round(1), "acquisition": (vol * cac).round(1), "opex": opex.round(1),
        "credit_loss": (vol * loss).round(1), "op_profit": profit.round(1),
    })
    # 最新月预算：实际放量超目标 5%（量正差）、实际净收入率低于预算 0.02pp（价负差，"以价换量"）
    monthly["budget_volume"] = np.nan
    monthly["budget_nim"] = np.nan
    monthly.loc[monthly.index[-1], "budget_volume"] = round(vol[-1] / 1.05, 1)
    monthly.loc[monthly.index[-1], "budget_nim"] = round(nim[-1] + 0.0002, 5)

    vol_w0 = vol[-1] / 4.3
    g_w = 0.012
    vol_w = vol_w0 / (1 + g_w) ** n_weeks * (1 + g_w) ** np.arange(n_weeks)   # 历史 52 周同趋势
    recovery = recovery_rate + rng.normal(0, 0.02, n_weeks)
    inflow = vol_w * recovery + rng.normal(0, 15, n_weeks)
    pulse = np.where(np.arange(n_weeks) % 13 == 12, 300.0, 0.0)              # 季度末营销脉冲
    outflow = vol_w + vol_w * (cac[-1] + loss[-1]) + opex[-1] / 4.3 + pulse + rng.normal(0, 10, n_weeks)
    weekly = pd.DataFrame({"week": np.arange(1, n_weeks + 1),
                           "inflow": inflow.round(1), "outflow": outflow.round(1),
                           "net_cf": (inflow - outflow).round(1)})
    return monthly, weekly, 4500.0   # 期初现金 4,500 万


# ---------------------------------------------------------------- 13 周现金流预测
def holt_forecast(y: np.ndarray, alpha: float, beta: float, h: int):
    """Holt 线性指数平滑。返回 (h 步点预测, 一步预测残差序列)。"""
    y = np.asarray(y, dtype=float)
    level, trend = y[0], y[1] - y[0]
    fitted, resid = [level], []
    for t in range(1, len(y)):
        resid.append(y[t] - (level + trend))
        level_prev = level
        level = alpha * y[t] + (1 - alpha) * (level + trend)
        trend = beta * (level - level_prev) + (1 - beta) * trend
        fitted.append(level + trend)
    point = np.array([level + (i + 1) * trend for i in range(h)])
    return point, np.array(resid)


def fit_holt(y: np.ndarray, h: int = 13):
    """网格搜索 (alpha, beta) 最小化历史 SSE。返回 (点预测, 残差, alpha, beta)。"""
    y = np.asarray(y, dtype=float)
    best = None
    for alpha in np.arange(0.1, 1.0, 0.1):
        for beta in np.arange(0.05, 0.55, 0.05):
            _, resid = holt_forecast(y, alpha, beta, h)
            sse = float((resid ** 2).sum())
            if best is None or sse < best[0]:
                best = (sse, alpha, beta)
    _, alpha, beta = best
    point, resid = holt_forecast(y, alpha, beta, h)
    return point, resid, alpha, beta


def forecast_band(point: np.ndarray, sigma: float, z: float = 1.2816):
    """80% 预测区间（随机游走近似：区间宽度随提前期 sqrt(h) 扩大）。返回 (lo, hi)。"""
    h = np.arange(1, len(point) + 1)
    half = z * sigma * np.sqrt(h)
    return point - half, point + half


# ---------------------------------------------------------------- 预算差异（中值法）
def pv_variance(p_b: float, q_b: float, p_a: float, q_a: float) -> dict:
    """中值法把收入差异分解为价差与量差（两因子口径，无产品结构变化）。

    价差 = (p_a − p_b) × (q_a + q_b) / 2
    量差 = (q_a − q_b) × (p_a + p_b) / 2
    恒等校验：价差 + 量差 = p_a×q_a − p_b×q_b。
    """
    price = (p_a - p_b) * (q_a + q_b) / 2
    volume = (q_a - q_b) * (p_a + p_b) / 2
    return {"price_effect": float(price), "volume_effect": float(volume),
            "total": float(price + volume)}


# ---------------------------------------------------------------- 流动性与融资
def cash_runway(weekly_net_cf: np.ndarray, opening_cash: float) -> np.ndarray:
    """给定预测期周净现金流与期初现金，返回逐周现金余额（含起点）。"""
    return np.concatenate([[opening_cash], opening_cash + np.cumsum(weekly_net_cf)])


def funding_gap(min_cash: float, buffer: float) -> float:
    """融资缺口 = max(0, 流动性缓冲线 − 预测期最低现金余额）。"""
    return float(max(0.0, buffer - min_cash))


# ---------------------------------------------------------------- 三情景前瞻
def scenario_pl(q0: float, p0: float, cac0: float, loss0: float, opex0: float,
                g_q: float, mults: dict, months: int = 12) -> pd.DataFrame:
    """从基准月 (q0, p0, cac0, loss0, opex0) 出发的月度损益前瞻。

    - 放款量按月增 g_q 复利增长，再乘情景乘数 mults["volume"]；
    - nim/cac/loss 各乘情景乘数；opex = 基准月运营成本按 0.3%/月通胀外推
      + 放款量增量 × 0.12% 变动成本；
    - 口径为损益（不含放款本金的营运现金净投放——流动性由 13 周预测模块覆盖）。
    """
    t = np.arange(1, months + 1)
    q = q0 * (1 + g_q) ** t * mults["volume"]
    rev = q * p0 * mults["nim"]
    opex = opex0 * 1.003 ** t + (q - q0) * 0.0012
    profit = rev - q * (cac0 * mults["cac"] + loss0 * mults["loss"]) - opex
    return pd.DataFrame({"month": t, "volume": q.round(1), "revenue": rev.round(1),
                         "opex": opex.round(1), "op_profit": profit.round(1)})
