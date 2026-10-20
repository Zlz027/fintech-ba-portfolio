"""共享财务函数库：信用评分卡（WOE/单调分箱/PSI）与风险-定价联动。

设计原则：
- 每个函数只做一件事，公式与口径在 docstring 写明，便于复核；
- 分箱/WOE/PSI 基准一律只在训练集估计，防止数据泄漏；
- 金额单位为元（CNY），利率为年化小数。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------- 评分卡分箱
def woe_table_from_idx(idx: np.ndarray, y: np.ndarray) -> pd.DataFrame:
    """按分箱索引计算 WOE / IV 表。

    WOE_j = ln( (good_j / total_good) / (bad_j / total_bad) )
    IV    = Σ_j (good_j/total_good - bad_j/total_bad) × WOE_j   （恒非负）
    """
    bad_total, good_total = max(y.sum(), 1), max((1 - y).sum(), 1)
    rows = []
    for b in np.unique(idx):
        m = idx == b
        bad, good = y[m].sum(), (1 - y[m]).sum()
        br, gr = bad / bad_total, good / good_total
        woe = np.log((gr + 1e-6) / (br + 1e-6))
        rows.append({"bin": int(b), "n": int(m.sum()), "bad_rate": bad / max(m.sum(), 1),
                     "woe": woe, "iv_contrib": (gr - br) * woe})
    return pd.DataFrame(rows)


def woe_table(x: np.ndarray, y: np.ndarray, bins: np.ndarray) -> pd.DataFrame:
    """按给定分箱边界（内部边界）计算 WOE / IV 表。

    注意：digitize 用 right=True——恰好等于边界的样本归入下箱，
    否则"98% 取值为 0"这类特征会把质量点全部推入上箱导致分箱坍缩。
    """
    return woe_table_from_idx(np.digitize(x, bins, right=True), y)


def pav_merge(bad_rates: list[float], counts: list[int]) -> list[int]:
    """PAV（Pool Adjacent Violators）：把相邻箱的坏账率合并成单调非降序列。

    返回每个初始箱所属的合并组编号。评分卡要求 WOE 随风险单调，
    对"坏账率非降"做保序回归，天然满足单调性要求。
    """
    groups: list[list] = []  # [sum_bad, n, member_bins]
    for i, (br, n) in enumerate(zip(bad_rates, counts)):
        groups.append([br * n, n, [i]])
        while len(groups) > 1 and groups[-2][0] / groups[-2][1] > groups[-1][0] / groups[-1][1]:
            b2, n2, m2 = groups.pop()
            b1, n1, m1 = groups.pop()
            groups.append([b1 + b2, n1 + n2, m1 + m2])
    assign = {}
    for g, (_, _, members) in enumerate(groups):
        for m in members:
            assign[m] = g
    return [assign[i] for i in range(len(bad_rates))]


def monotonic_woe(x: np.ndarray, y: np.ndarray, n_bins: int = 20) -> tuple[np.ndarray, pd.DataFrame, float]:
    """等频初始分箱 + PAV 单调合并，返回 (每样本WOE映射, 分箱表, IV)。

    处理流程：等频分箱（默认 20 个初始箱，给长尾特征留分辨率）
    -> PAV 合并违背单调的相邻箱 -> 合并组内重算 WOE。
    返回值 woe_map 为每个样本的 WOE 值（训练集口径），供 LR 评分卡使用。
    """
    qs = np.unique(np.quantile(x, np.linspace(0, 1, n_bins + 1)))
    if len(qs) < 3:  # 特征无区分度（常量或近常量），WOE 全 0
        return np.zeros(len(x)), pd.DataFrame({"group": [0], "bins": [[0]], "n": [len(x)],
                                               "bad_rate": [y.mean()], "woe": [0.0], "iv_contrib": [0.0]}), 0.0
    inner = qs[1:-1]
    idx = np.digitize(x, inner, right=True)
    base = woe_table_from_idx(idx, y)
    if len(base) < 2:  # 全部样本落入同一箱
        return np.zeros(len(x)), base.assign(group=0, bins=[[b] for b in base["bin"]]).assign(iv_contrib=0.0), 0.0
    merged = pav_merge(base["bad_rate"].tolist(), base["n"].tolist())
    base["group"] = merged
    bad_total, good_total = y.sum(), (1 - y).sum()
    rows, woe_of_group = [], {}
    for g, sub in base.groupby("group"):
        n_g = sub["n"].sum()
        bad = (sub["bad_rate"] * sub["n"]).sum()
        br, gr = bad / bad_total, (n_g - bad) / good_total
        woe = np.log((gr + 1e-6) / (br + 1e-6))
        woe_of_group[g] = woe
        rows.append({"group": int(g), "bins": sorted(sub["bin"]), "n": int(n_g),
                     "bad_rate": bad / max(n_g, 1), "woe": woe})
    tab = pd.DataFrame(rows)
    tab["iv_contrib"] = ((1 - tab["bad_rate"]) * tab["n"] / good_total
                         - tab["bad_rate"] * tab["n"] / bad_total) * tab["woe"]
    iv = float(tab["iv_contrib"].sum())
    bin_to_group = dict(zip(base["bin"], base["group"]))
    woe_map = np.array([woe_of_group[bin_to_group[b]] for b in idx])
    return woe_map, tab, iv


# ---------------------------------------------------------------- 评分刻度
def score_mapping(p_good_odds_anchor: float = 50.0, base: int = 600, pdo: int = 20):
    """业界标准评分刻度：基准分 base 对应好坏比 anchor:1，每 PDO 分好坏比翻倍。

    Score = base + (PDO/ln2) × ln(odds_good / anchor)
    其中 odds_good = (1-p)/p。返回 (factor, offset)：score = offset + factor × ln(odds_good)。
    """
    factor = pdo / np.log(2)
    offset = base - factor * np.log(p_good_odds_anchor)
    return factor, offset


def prob_to_score(p: np.ndarray, factor: float, offset: float) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return offset + factor * np.log((1 - p) / p)


# ---------------------------------------------------------------- PSI
def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> tuple[float, pd.DataFrame]:
    """总体稳定性指数 PSI（以 expected 即训练集分数分位数为基准）。

    PSI = Σ (actual% - expected%) × ln(actual% / expected%)
    分级惯例：<0.10 稳定 / 0.10-0.25 观察（警告） / >0.25 显著漂移（告警）。
    """
    qs = np.quantile(expected, np.linspace(0, 1, bins + 1))
    qs[0], qs[-1] = -np.inf, np.inf
    e = np.digitize(expected, qs[1:-1])
    a = np.digitize(actual, qs[1:-1])
    rows = []
    for b in range(bins):
        ep = (e == b).mean()
        ap = (a == b).mean()
        rows.append({"bin": b, "expected_pct": ep, "actual_pct": ap,
                     "psi_contrib": (ap - ep) * np.log((ap + 1e-6) / (ep + 1e-6))})
    return float(pd.DataFrame(rows)["psi_contrib"].sum()), pd.DataFrame(rows)


# ---------------------------------------------------------------- 风险定价
def breakeven_rate(pd: np.ndarray, lgd: float, funding: float, opex: float) -> np.ndarray:
    """盈亏平衡利率：使贷款预期损益恰好为零的年化利率。

    贷款经济学（口径 A：利息仅由未违约者产生，违约者损失 LGD 且停止生息）：
        E[profit] = (1-pd) x r - pd x LGD - funding - opex = 0
        =>  r* = (pd x LGD + funding + opex) / (1 - pd)

    注意与口径 B（始终生息，如纯手续费业务）的区别：口径 B 下 r* = pd*LGD+funding+opex。
    pd=0.97、LGD=0.45 时口径 A 要求 r* > 1600%，即该客户在任何现实利率下不可定价。
    """
    pd = np.clip(pd, 1e-6, 1 - 1e-6)
    return (pd * lgd + funding + opex) / (1 - pd)


def price_book(pd: np.ndarray, ead: np.ndarray, lgd: float, funding: float,
               opex: float, target_margin: float, rate_cap: float) -> tuple[np.ndarray, np.ndarray]:
    """风险定价 + 单客户预期年损益（口径 A）。

    r_i     = min(cap, r*_i + target_margin)，r*_i 为盈亏平衡利率；
    profit_i = (1-pd_i) x r_i x EAD - pd_i x LGD x EAD - (funding + opex) x EAD

    未触顶时 profit_i = (1-pd_i) x target_margin x EAD（目标利润率按生存概率折算）；
    触顶（r*_i + margin > cap）时 profit_i < 0，应拒贷。
    返回 (建议利率, 单客户预期年损益)。
    """
    r = np.minimum(rate_cap, breakeven_rate(pd, lgd, funding, opex) + target_margin)
    profit = ((1 - pd) * r - pd * lgd - funding - opex) * ead
    return r, profit


def policy_curve(scores: np.ndarray, pd_: np.ndarray, ead: np.ndarray, lgd: float,
                 funding: float, opex: float, target_margin: float, rate_cap: float,
                 thresholds: np.ndarray) -> pd.DataFrame:
    """通过率-坏账率-利润曲线：按分数阈值 θ 批准 score>=θ 的客户（个体风险定价）。

    指标（全组合口径，被拒客户贡献 0 利润、不吃风险）：
    - approval_rate    通过率 = n_approved / N
    - bad_rate         批准客群加权坏账率 = Σ pd×EAD / Σ EAD_approved
    - margin_approved  批准客群年化利润率 = Σ profit / Σ EAD_approved
    - margin_book      全组合年化利润率 = Σ profit / Σ EAD_total
    """
    rows = []
    _, profit_all = price_book(pd_, ead, lgd, funding, opex, target_margin, rate_cap)
    total_ead = ead.sum()
    for th in thresholds:
        m = scores >= th
        na, ea = m.sum(), ead[m].sum()
        if na == 0:
            rows.append({"threshold": th, "approval_rate": 0.0, "bad_rate": np.nan,
                         "margin_approved": np.nan, "margin_book": 0.0})
            continue
        rows.append({
            "threshold": th,
            "approval_rate": na / len(scores),
            "bad_rate": float((pd_[m] * ead[m]).sum() / ea),
            "margin_approved": float(profit_all[m].sum() / ea),
            "margin_book": float(profit_all[m].sum() / total_ead),
        })
    return pd.DataFrame(rows)


def flat_rate_baseline(pd_: np.ndarray, lgd: float, funding: float, opex: float,
                       target_margin: float, rate_cap: float) -> tuple[float, np.ndarray]:
    """无模型基准：全量通过 + 按组合平均 PD 统一定价。

    r_flat = min(cap, r*(mean_pd) + target_margin)
    返回 (统一定价, 单客户预期年损益)。统一定价下高 PD 客户亏损、低 PD 客户补贴
    （交叉补贴）——风险定价联动要消除的正是这部分。
    """
    pd_pool = float(np.mean(pd_))
    r_flat = float(min(rate_cap, breakeven_rate(np.array([pd_pool]), lgd, funding, opex)[0] + target_margin))
    profit = ((1 - pd_) * r_flat - pd_ * lgd - funding - opex)
    return r_flat, profit
