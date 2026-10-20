"""回收系数敏感性分析（OPT-3，可复跑）。

对回收系数 recovery ∈ {1.00, 0.95, 0.92, 0.88} 重跑模拟 → Holt 13 周预测 →
现金余额跑道 → 13 周最低现金与融资缺口。口径与 Notebook 模块 2 完全一致：
缓冲线 ¥3,000 万，缺口 = max(0, 缓冲 − 最低现金)；四个情景共用同一随机种子，
唯一差异是回收系数（common random numbers，排除抽样噪声干扰）。

基线校验：recovery=0.92 必须还原 Notebook 的第 13 周见底 ¥80 万 / 缺口 ¥2,920 万。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import finance as fin  # noqa: E402

BUFFER = 3000.0


def runway_summary(recovery_rate: float) -> dict:
    """单个回收系数情景下的 13 周现金流摘要（口径 = Notebook 模块 2）。"""
    _, weekly, opening = fin.simulate_company(seed=fin.SEED, recovery_rate=recovery_rate)
    point, resid, alpha, beta = fin.fit_holt(weekly.net_cf.values, h=13)
    lo, hi = fin.forecast_band(point, resid.std(ddof=1))
    bal = fin.cash_runway(point, opening)        # 第 0-13 周现金余额（点预测）
    bal_lo = fin.cash_runway(lo, opening)        # 80% 悲观边界
    below = bal < BUFFER
    return {"min_cash": float(bal[1:].min()),                       # 13 周最低现金（点预测）
            "min_week": int(np.argmin(bal[1:])) + 1,                # 见底周（1-13）
            "breach": int(np.argmax(below)) if below.any() else None,  # 击穿缓冲周（None=未击穿）
            "gap": fin.funding_gap(bal[1:].min(), BUFFER),
            "bal_lo13": float(bal_lo[-1]),                          # 80% 悲观边界第 13 周
            "net_cf13": float(point.sum()),                         # 13 周净现金流合计
            "alpha": float(alpha), "beta": float(beta)}


base = runway_summary(0.92)
print("基线校验（recovery=0.92）：第 %d 周见底 ¥%.0f 万 / 缺口 ¥%.0f 万（期望 第 13 周 / ¥80 / ¥2,920）"
      % (base["min_week"], base["min_cash"], base["gap"]))
assert base["min_week"] == 13 and abs(base["min_cash"] - 80) < 1.5 and abs(base["gap"] - 2920) < 1.5, \
    "基线复刻失败：Notebook 口径变更？"

rows = []
for r in [1.00, 0.95, 0.92, 0.88]:
    s = runway_summary(r)
    rows.append({"回收系数": "%.2f" % r,
                 "13周净现金流合计": round(s["net_cf13"]),
                 "击穿缓冲周": "第%d周" % s["breach"] if s["breach"] else "未击穿",
                 "13周最低现金": round(s["min_cash"]),
                 "融资缺口": round(s["gap"]),
                 "80%悲观边界(第13周)": round(s["bal_lo13"])})
tab = pd.DataFrame(rows)
print("\n回收系数敏感性：\n" + tab.to_string(index=False))
tab.to_csv(ROOT / "outputs/recovery_sensitivity.csv", index=False)
