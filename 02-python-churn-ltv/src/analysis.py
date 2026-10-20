"""挽留成功率（uplift）敏感性分析（OPT-1，可复跑）。

基于 outputs/test_scored.csv（Notebook 落盘的测试集逐客 churn_prob 与 LTV），
对 uplift ∈ {10%, 20%, 30%, 40%} 计算最优触达规模 N*、净收益与毛 ROI
（ROI 口径 = 累计收益 / 累计成本，与 README 基准 2.62 一致）。

基线校验：uplift=30% 必须还原 Notebook 的 N*=550 / 净收益 ¥62,468 / ROI 2.62。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import finance as fin  # noqa: E402

df = pd.read_csv(ROOT / "outputs/test_scored.csv")
p, ltv = df["churn_prob"].values, df["LTV"].values

roi, cost, net = fin.campaign_roi(p, ltv, uplift=0.30)
n = int(np.argmax(net)) + 1
print("基线校验（uplift=30%%）：N*=%d / 净收益 ¥%.0f / ROI %.2f（期望 550 / 62468 / 2.62）"
      % (n, net[n - 1], roi[n - 1]))
assert n == 550 and abs(net[n - 1] - 62468) < 1 and abs(roi[n - 1] - 2.62) < 0.01, "基线复刻失败"

rows = []
for u in [0.10, 0.20, 0.30, 0.40]:
    roi, cost, net = fin.campaign_roi(p, ltv, uplift=u)
    k = int(np.argmax(net)) + 1
    rows.append({"挽留成功率": "%d%%" % (u * 100), "最优触达N*": k,
                 "触达预算": round(float(cost[k - 1])), "净收益": round(float(net[k - 1])),
                 "毛ROI": round(float(roi[k - 1]), 2)})
tab = pd.DataFrame(rows)
print("\n挽留成功率敏感性：\n" + tab.to_string(index=False))
tab.to_csv(ROOT / "outputs/uplift_sensitivity.csv", index=False)
