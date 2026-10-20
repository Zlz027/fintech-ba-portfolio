"""愿付溢价与 LGD 敏感性分析（OPT-2，可复跑）。

复刻 notebooks/credit_risk_pricing.ipynb 第 5 单元格的策略管道，基于
outputs/test_pd.csv（Notebook 落盘的测试集逐客 PD 分）计算：
- 愿付溢价 COMP ∈ {0%, 3%, 5%} 下的 S0 实现口径（逆向选择）与 S2 全组合利润率；
- LGD ∈ {60%, 75%, 90%} 下的 S2 全组合利润率（其余假设不变）。

基线校验：COMP=3% 必须还原 Notebook 的 S0 实现（成交 27.3% / 坏账 20.1% /
利润率 -2.69%）与 S2（+1.75%），否则说明复刻管道不一致，结果不可用。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import finance as fin  # noqa: E402

LGD, FUND, OPEX, TGT, CAP, EAD = 0.75, 0.03, 0.02, 0.02, 0.24, 10_000.0
FACTOR, OFFSET = fin.score_mapping(50, 600, 20)

pd_xgb = pd.read_csv(ROOT / "outputs/test_pd.csv")["pd"].values
ead = np.full(len(pd_xgb), EAD)
s_xgb = fin.prob_to_score(pd_xgb, FACTOR, OFFSET)
grid = np.quantile(s_xgb, np.linspace(0.02, 0.98, 40))


def strategies(comp: float, lgd: float = LGD) -> dict:
    """给定愿付溢价与 LGD，返回 S0 实现（逆向选择）与 S2 的关键数字。"""
    wtp = fin.breakeven_rate(pd_xgb, lgd, FUND, OPEX) + comp          # 客户愿付
    r_flat, profit_flat = fin.flat_rate_baseline(pd_xgb, lgd, FUND, OPEX, TGT, CAP)
    acc0 = wtp >= r_flat - 1e-9                                        # 统一定价成交集
    m0 = float(profit_flat[acc0].mean() * acc0.mean())
    curve = fin.policy_curve(s_xgb, pd_xgb, ead, lgd, FUND, OPEX, TGT, CAP, grid)
    best = curve.loc[curve["margin_book"].idxmax()]
    r_ind, prof_ind = fin.price_book(pd_xgb, ead, lgd, FUND, OPEX, TGT, CAP)
    acc2 = (s_xgb >= best["threshold"]) & (r_ind <= wtp)               # 过门槛且愿付接受
    m2 = float(prof_ind[acc2].sum() / ead.sum())
    return {"comp": comp, "acc0": float(acc0.mean()), "bad0": float(pd_xgb[acc0].mean()),
            "m0": m0, "acc2": float(acc2.mean()), "m2": m2}


base = strategies(0.03)
print("基线校验（COMP=3%%）：S0 实现 成交 %.1f%% / 坏账 %.2f%% / 利润率 %.2f%% | S2 利润率 %+.2f%%"
      % (100 * base["acc0"], 100 * base["bad0"], 100 * base["m0"], 100 * base["m2"]))
assert abs(base["acc0"] - 0.27331) < 5e-4 and abs(base["bad0"] - 0.20064) < 5e-4, "S0 复刻失败"
assert abs(base["m0"] - -0.026871) < 5e-5 and abs(base["m2"] - 0.017472) < 5e-5, "S2 复刻失败"

rows = []
for comp in [0.00, 0.03, 0.05]:
    r = strategies(comp)
    rows.append({"愿付溢价": "%d%%" % (comp * 100), "S0实现成交率": round(r["acc0"], 4),
                 "S0实现坏账率": round(r["bad0"], 4), "S0实现利润率": round(r["m0"], 4),
                 "S2利润率": round(r["m2"], 4), "S2成交率": round(r["acc2"], 4),
                 "S2减S0(pp)": round((r["m2"] - r["m0"]) * 100, 2)})
wtp_tab = pd.DataFrame(rows)
print("\n愿付溢价敏感性：\n" + wtp_tab.to_string(index=False))

lgd_rows = []
for lgd in [0.60, 0.75, 0.90]:
    r = strategies(0.03, lgd=lgd)
    lgd_rows.append({"LGD": "%d%%" % (lgd * 100), "S2利润率": round(r["m2"], 4),
                     "S0实现利润率": round(r["m0"], 4), "S2成交率": round(r["acc2"], 4)})
lgd_tab = pd.DataFrame(lgd_rows)
print("\nLGD 敏感性（COMP=3% 不变）：\n" + lgd_tab.to_string(index=False))

wtp_tab.to_csv(ROOT / "outputs/wtp_premium_sensitivity.csv", index=False)
lgd_tab.to_csv(ROOT / "outputs/lgd_sensitivity.csv", index=False)
d60 = strategies(0.03, lgd=0.60)["m2"] - strategies(0.03, lgd=0.75)["m2"]
print("\nLGD 75%%→60%%：S2 利润率 %+.2f pp" % (d60 * 100))
