"""共享财务函数库：欺诈检测的成本敏感阈值与规则评估。

设计原则：
- 成本矩阵参数化（漏判成本、误杀成本），最优阈值由 argmin 总成本给出；
- 规则评估同时报告精确率与覆盖率（欺诈召回），防止"高精确率但只覆盖 1 笔"的假规则；
- 不依赖项目特定数据，可被其他项目 Notebook import。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------- 成本矩阵与阈值
def expected_cost(y: np.ndarray, p: np.ndarray, amount: np.ndarray, threshold: float,
                  fp_cost: float = 120.0, miss_fixed: float = 50.0) -> float:
    """阈值 θ 下的期望总成本。

    成本矩阵（可配置假设）：
    - 误杀（好交易被拦截）：fp_cost（人工审核 + 客户体验损失）
    - 漏判（欺诈放行）：欺诈金额全额 + miss_fixed（运营/调查成本）

    总成本 = FP 数 × fp_cost + Σ漏判欺诈 (amount + miss_fixed)
    """
    flag = p >= threshold
    fp = int(((y == 0) & flag).sum())
    missed = (y == 1) & ~flag
    return float(fp * fp_cost + amount[missed].sum() + missed.sum() * miss_fixed)


def optimal_threshold(y: np.ndarray, p: np.ndarray, amount: np.ndarray,
                      fp_cost: float = 120.0, miss_fixed: float = 50.0,
                      n_grid: int = 300) -> tuple[float, float, pd.DataFrame]:
    """精确求解成本最优阈值，返回 (最优阈值, 最优成本, 阈值-成本曲线)。

    总成本关于阈值 θ 是分段常数函数，只在观测到的预测概率值处跳变。
    按概率降序逐笔累加成本增量（欺诈：-(金额+漏判固定成本)；正常：+误杀成本），
    O(n log n) 即得全局最优。

    不用分位网格：当欺诈金额相对误杀成本较小时，最优阈值落在概率分布的极上尾，
    等距分位网格会整段跳过错点（本项目实测：80-99.9 分位网格漏掉了 0.5 附近的真正最优点）。
    """
    y, p, amount = (np.asarray(v) for v in (y, p, amount))
    n_fraud = int((y == 1).sum())
    base = float(amount[y == 1].sum() + n_fraud * miss_fixed)  # 不拦截时的总成本
    order = np.argsort(-p, kind="stable")
    y_s, amt_s, ps = y[order], amount[order], p[order]
    delta = np.where(y_s == 1, -(amt_s + miss_fixed), fp_cost)  # 每降低一档阈值的成本增量
    costs = base + np.cumsum(delta)
    # 相同概率值只在组末取候选（阈值语义为 p >= th，同组会被同时拦截）
    last = np.ones(len(ps), dtype=bool)
    last[:-1] = ps[:-1] != ps[1:]
    idx = np.flatnonzero(last)
    cand_cost = np.concatenate([[base], costs[idx]])
    cand_th = np.concatenate([[1.01], ps[idx]])  # 1.01 高于任何概率，等价于不拦截
    best = int(np.argmin(cand_cost))
    best_th, best_cost = float(cand_th[best]), float(cand_cost[best])
    # 阈值-成本曲线：高分段（可解释阈值区）全取，其余等距抽样，必含最优点
    n_top = min(2000, len(idx))
    sel = list(np.arange(n_top))
    if n_top < len(idx) - 1:
        sel += list(np.linspace(n_top, len(idx) - 1, n_grid).astype(int))
    if best > 0:
        sel.append(best - 1)  # cand 中的最优点对应 idx 空间的位置
    sel = np.unique(np.asarray(sel, dtype=int))
    cum_caught = np.cumsum(y_s)[idx]
    curve = pd.DataFrame({
        "threshold": ps[idx][sel],
        "flagged": (idx + 1)[sel],
        "flag_rate": (idx + 1)[sel] / len(y),
        "caught": cum_caught[sel],
        "recall": cum_caught[sel] / max(n_fraud, 1),
        "cost": costs[idx][sel],
    }).reset_index(drop=True)
    return best_th, best_cost, curve


def threshold_sensitivity(y: np.ndarray, p: np.ndarray, amount: np.ndarray,
                          fp_costs: list[float], miss_fixed: float = 50.0) -> pd.DataFrame:
    """误杀成本敏感性：不同 fp_cost 假设下的最优阈值与总成本。"""
    rows = []
    for c in fp_costs:
        th, cost, _ = optimal_threshold(y, p, amount, fp_cost=c, miss_fixed=miss_fixed)
        flag = p >= th
        rows.append({"fp_cost": c, "best_threshold": th, "total_cost": cost,
                     "flag_rate": float(flag.mean()),
                     "recall": float(((y == 1) & flag).sum() / max(y.sum(), 1))})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 规则评估
def rule_eval(mask: np.ndarray, y: np.ndarray) -> dict:
    """规则评估：精确率（规则内欺诈占比）、覆盖率（规则捕获的欺诈占比）、提升度。"""
    n = int(mask.sum())
    tp = int((y[mask] == 1).sum())
    prec = tp / max(n, 1)
    rec = tp / max(int(y.sum()), 1)
    return {"n_flagged": n, "tp": tp, "precision": prec, "recall": rec,
            "lift": prec / max(float(y.mean()), 1e-9)}


# ---------------------------------------------------------------- 监控
def score_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """评分分布 PSI（以 expected 为基准），用于上线后漂移监控。"""
    qs = np.quantile(expected, np.linspace(0, 1, bins + 1))
    qs[0], qs[-1] = -np.inf, np.inf
    e = np.digitize(expected, qs[1:-1])
    a = np.digitize(actual, qs[1:-1])
    val = 0.0
    for b in range(bins):
        ep, ap = (e == b).mean(), (a == b).mean()
        val += (ap - ep) * np.log((ap + 1e-6) / (ep + 1e-6))
    return float(val)
