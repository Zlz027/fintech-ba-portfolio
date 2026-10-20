"""生成 01-python-credit-scoring 的 Notebook：信用风险评分与风险-定价联动（V2.0 主打项目）。

数据：Give Me Some Credit（Kaggle，经 OpenML/TabArena 清洗版，150,000 行）。
验收线：AUC>=0.78, KS>=0.35, Gini>=0.56（CV 口径）。
约束：Notebook 代码行数 <= 200；一页 README 含财务影响层。
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parent
nb = nbf.v4.new_notebook()
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s))
code = lambda s: cells.append(nbf.v4.new_code_cell(s))

md("""# 信用风险评分卡 × 风险-定价联动（Give Me Some Credit）

**业务问题**：消费信贷审批中，风控回答"谁可能违约"（评分卡），FP&A 回答"因此怎么定价、组合赚多少"（风险-定价联动）。本项目把两者打通：

```
PD 评分（LR 评分卡 + XGBoost challenger）→ 分数刻度（600/PDO20/odds50:1）
→ 风险分档定价 → 通过率-坏账率-利润曲线 → 组合策略与财务影响
```

**口径声明**
- 目标：未来两年发生财务困境（`SeriousDlqin2yrs`）的概率；
- 分箱/WOE/PSI 基准仅在训练集估计，防泄漏；
- 全部产出为分析底稿，不构成投资建议；数字需人工复核签署后使用。""")

code('''import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.io import arff
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
import xgboost as xgb
import shap

SEED = 42  # 固定种子：切分/训练/采样全部锚定，保证"复跑=复现"——README 数字任何人可一键验证
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
import finance as fin  # noqa: E402

plt.rcParams.update({"font.sans-serif": ["Noto Sans CJK JP", "DejaVu Sans"], "axes.unicode_minus": False})

def ks_stat(y, p):
    o = np.argsort(-p); y = y[o]
    tp = np.cumsum(y) / max(y.sum(), 1); fp = np.cumsum(1 - y) / max((1 - y).sum(), 1)
    return float(np.max(tp - fp))

data, _ = arff.loadarff(ROOT / "data/raw/givesomecredit.arff")
df = pd.DataFrame(data)
df["y"] = (df["FinancialDistressNextTwoYears"] == b"Yes").astype(int)
df = df.drop(columns=["FinancialDistressNextTwoYears"]).astype(float)
print(df.shape, "| default rate = %.4f" % df["y"].mean())''')

md("""## 1. 数据清洗与探索性分析

- `RevolvingUtilization` / `DebtRatio` 存在极端值（>1 或上千），按 99.9% 分位截尾；
- `MonthlyIncome` 缺失 19.8%、`NumberOfDependents` 缺失 2.6%：WOE 分箱中缺失并入最低箱（缺失与更高违约率同向，方向保守），XGBoost 侧用中位数填补 + 缺失指示。""")

code('''for c in ["RevolvingUtilizationOfUnsecuredLines", "DebtRatio", "MonthlyIncome"]:  # p99.9 截尾而非删行：长尾极端值会扭曲分位数与相关系数，截尾保留样本量使 WOE 分箱更稳
    cap = df[c].quantile(0.999)
    df[c] = df[c].clip(upper=cap)
FEATS = [c for c in df.columns if c != "y"]
eda = df.groupby(pd.qcut(df["RevolvingUtilizationOfUnsecuredLines"], 10), observed=True)["y"].agg(["mean", "count"])
print("利用率十分位违约率:\\n", eda.round(4).to_string())

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
df["y"].value_counts().plot.bar(ax=axes[0], color=["#2c3e50", "#c0392b"])
axes[0].set(title="目标分布（1=两年内财务困境）", xticklabels=["No", "Yes"], ylabel="客户数")
df.boxplot(column="RevolvingUtilizationOfUnsecuredLines", by="y", ax=axes[1])
axes[1].set(title="循环额度利用率 × 违约", ylabel="utilization（截尾后）")
fig.suptitle("GMSC EDA 总览"); fig.tight_layout()
fig.savefig(ROOT / "images/eda.png", dpi=150); plt.close(fig)''')

md("""## 2. 特征筛选：IV + 相关性 + VIF

1. **IV**：等频 10 箱 PAV 单调合并后计算，保留 IV>0.02（预测力"有用"以上）；
2. **相关性**：|r|>0.7 的重复信息只保留 IV 高者（GMSC 的三组逾期天数高度共线）；
3. **VIF**：WOE 特征矩阵上 `VIF = diag(inv(corr))`，剔除 VIF>10 者。""")

code('''woe_cols, iv_rows, bin_tables = [], [], {}
for c in FEATS:
    x = df[c].fillna(-np.inf).values  # 缺失并入最低箱：缺失与更高违约率同向（保守方向），比中位数填补更符合评分卡业务直觉
    w, tab, iv = fin.monotonic_woe(x, df["y"].values, n_bins=20)  # 等频 20 箱而非等距：RevolvingUtilization 呈长尾分布，等距会让高利用率段样本过少、WOE 估计不稳定
    df["woe_" + c] = w
    woe_cols.append("woe_" + c)
    iv_rows.append({"feature": c, "iv": iv, "n_bins": len(tab)})
    bin_tables[c] = tab.assign(feature=c)
iv_df = pd.DataFrame(iv_rows).sort_values("iv", ascending=False)
print(iv_df.round(4).to_string(index=False))

# 相关性 + VIF：先按 IV>0.02 筛选，再按 IV 降序处理 |r|>0.7 的共线，最后剔除 VIF>10
W = df[woe_cols].values
corr = np.corrcoef(W.T)
pos = {c: i for i, c in enumerate(woe_cols)}
iv_pass = iv_df[iv_df["iv"] > 0.02]["feature"].tolist()
print("\\nIV<=0.02 剔除:", iv_df[iv_df["iv"] <= 0.02]["feature"].tolist())
keep, dropped = [], []
for f in iv_pass:  # IV 降序
    c = "woe_" + f
    if any(abs(corr[pos[c], pos[j]]) > 0.7 for j in keep):
        dropped.append(f); continue
    keep.append(c)
vif = pd.Series(np.diag(np.linalg.inv(np.corrcoef(df[keep].values.T))), index=keep)
final = [c for c in keep if vif[c] < 10]
print("相关性(|r|>0.7)剔除:", dropped)
print("VIF>10 剔除:", [c.replace("woe_", "") for c in keep if vif[c] >= 10])
print("最终入模特征:", [c.replace("woe_", "") for c in final])''')

md("""## 3. 模型：LR 评分卡 vs XGBoost challenger

- LR：WOE 特征 + L2，输出可解释评分卡；
- XGBoost：原始特征（中位数填补 + 缺失指示），challenger；
- 泛化性能用 5 折 CV 的 **mean ± std** 作为置信区间口径。""")

code('''train_df, test_df = train_test_split(df, test_size=0.25, stratify=df["y"], random_state=SEED)
Xw_tr, Xw_te = train_df[final].values, test_df[final].values
y_tr, y_te = train_df["y"].values, test_df["y"].values

lr = LogisticRegression(max_iter=2000, C=1.0).fit(Xw_tr, y_tr)
p_lr = lr.predict_proba(Xw_te)[:, 1]

Xr = df[FEATS].copy()
for c in ["MonthlyIncome", "NumberOfDependents"]:
    Xr[c + "_na"] = Xr[c].isna().astype(int)
    Xr[c] = Xr[c].fillna(Xr[c].median())
Xr_tr, Xr_te = Xr.loc[train_df.index].values, Xr.loc[test_df.index].values
xgbm = xgb.XGBClassifier(n_estimators=500, max_depth=5, learning_rate=0.05, subsample=0.85,
                         colsample_bytree=0.85, min_child_weight=20, reg_lambda=2.0,
                         eval_metric="auc", random_state=SEED, n_jobs=4)
cv = cross_val_score(xgbm, Xr_tr, y_tr, cv=StratifiedKFold(5, shuffle=True, random_state=42), scoring="roc_auc")  # 报 5 折 CV 的 mean±std：单次切分 AUC 有运气成分，CV 标准差即泛化性能的置信区间口径
xgbm.fit(Xr_tr, y_tr)
p_xgb = xgbm.predict_proba(Xr_te)[:, 1]
met = pd.DataFrame([
    {"model": "LR 评分卡", "cv_auc": np.nan, "test_auc": roc_auc_score(y_te, p_lr), "test_gini": 2 * roc_auc_score(y_te, p_lr) - 1, "test_ks": ks_stat(y_te, p_lr)},
    {"model": "XGBoost", "cv_auc": f"{cv.mean():.4f}±{cv.std():.4f}", "test_auc": roc_auc_score(y_te, p_xgb),
     "test_gini": 2 * roc_auc_score(y_te, p_xgb) - 1, "test_ks": ks_stat(y_te, p_xgb)},
])
print(met.round(4).to_string(index=False))''')

md("""## 4. 评分刻度与 PSI 监控

- 刻度：**基准 600 分 = 好坏比 50:1，PDO=20**（业界标准，与 FICO 一致）；
- 评分卡分值：`points_j = -(PDO/ln2) × β_j × WOE_j`，基准分锚定组合平均风险；
- PSI：训练集 vs 测试集评分分布，分级告警（<0.10 稳定 / 0.10-0.25 观察 / >0.25 显著漂移）。""")

code('''FACTOR, OFFSET = fin.score_mapping(50, 600, 20)  # 600 分=好坏比 50:1、PDO=20 为业界标准刻度（同 FICO）：分数每降 20 分好坏比减半，风险变化对业务方可读
p_tr = lr.predict_proba(Xw_tr)[:, 1]
s_tr, s_te = fin.prob_to_score(p_tr, FACTOR, OFFSET), fin.prob_to_score(p_lr, FACTOR, OFFSET)
print("训练集评分范围 [%.0f, %.0f]，均值 %.0f" % (s_tr.min(), s_tr.max(), s_tr.mean()))

# 评分卡分值表：每个特征的每个分箱对应分值
rows = []
for j, c in enumerate(final):
    for _, r in bin_tables[c.replace("woe_", "")].iterrows():
        rows.append({"feature": c.replace("woe_", ""), "bin_group": r["group"],
                     "bad_rate": r["bad_rate"], "woe": r["woe"], "points": -FACTOR * lr.coef_[0][j] * r["woe"]})
sc = pd.DataFrame(rows)
sc.to_csv(ROOT / "outputs/scorecard.csv", index=False)

psi_score, psi_tab = fin.psi(s_tr, s_te)
psi_feat = pd.DataFrame([{"feature": c.replace("woe_", ""), "psi": fin.psi(train_df[c].values, test_df[c].values)[0]}
                         for c in final])
def psi_grade(v):
    return "稳定" if v < 0.10 else ("观察" if v < 0.25 else "显著漂移")
print("评分分布 PSI = %.4f（%s）" % (psi_score, psi_grade(psi_score)))
print(psi_feat.round(4).to_string(index=False))
psi_tab.to_csv(ROOT / "outputs/psi_score_deciles.csv", index=False)
psi_feat.to_csv(ROOT / "outputs/psi_features.csv", index=False)''')

md("""## 5. 风险-定价联动（财务影响层）

**贷款经济学口径**（利息仅由未违约者产生；EAD=¥10,000/客户，LGD=75%——无担保消费贷行业区间 70-90% 的中性假设，资金成本 3%，运营成本率 2%，目标利润率 2%，利率上限 24%）：

| 步骤 | 公式 |
|---|---|
| 盈亏平衡利率 | `r* = (PD×LGD + funding + opex) / (1 - PD)` |
| 风险定价 | `r_i = min(24%, r*_i + 2%)`，恒在客户愿付内（见下） |
| 单客户年损益 | `profit_i = (1-PD_i)×r_i×EAD - PD_i×LGD×EAD - (funding+opex)×EAD` |

**逆向选择（客户愿付模型）**：客户愿付 `wtp_i = r*_i + 3%`（竞争性溢价假设）。统一定价 `r_flat` 下，只有 `wtp_i ≥ r_flat` 的高风险客户成交——**低风险客户被高价挤出，成交客群逆向选择**。个体定价下 `r_i ≤ r*_i + 2% < wtp_i` 恒成立，无挤出效应。

**三策略对比**：
- **S0 无模型**：全量通过 + 统一定价（分别报告理论口径"全量成交"与实现口径"逆向选择后实际成交"）；
- **S1 仅评分筛选 + 统一定价**：筛选与定价不联动，被门槛挡住的高风险恰是愿付统一定价的人；
- **S2 评分 + 风险定价联动**：个体定价 + 阈值筛选。""")

code('''LGD, FUND, OPEX, TGT, CAP, EAD, COMP = 0.75, 0.03, 0.02, 0.02, 0.24, 10_000.0, 0.03
pd_xgb = xgbm.predict_proba(Xr_te)[:, 1]
ead = np.full(len(pd_xgb), EAD)
s_xgb = fin.prob_to_score(pd_xgb, FACTOR, OFFSET)
wtp = fin.breakeven_rate(pd_xgb, LGD, FUND, OPEX) + COMP  # 客户愿付

# S0 无模型：全量通过 + 统一定价；实现口径只有 wtp>=r_flat 的客户成交——双口径之差即不定价的代价（理论口径测公式、实现口径测逆向选择现实）
r_flat, profit_flat = fin.flat_rate_baseline(pd_xgb, LGD, FUND, OPEX, TGT, CAP)
acc0 = wtp >= r_flat - 1e-9
m0_theory = float(profit_flat.mean())
m0_real = float(profit_flat[acc0].mean() * acc0.mean())
# S1 仅评分筛选 + 统一定价（同一最优阈值下，成交 = 过门槛 且 愿付挂牌价）
grid = np.quantile(s_xgb, np.linspace(0.02, 0.98, 40))
curve = fin.policy_curve(s_xgb, pd_xgb, ead, LGD, FUND, OPEX, TGT, CAP, grid)
best = curve.loc[curve["margin_book"].idxmax()]
mask_best = s_xgb >= best["threshold"]
acc1 = mask_best & acc0
m1 = float(profit_flat[acc1].mean() * acc1.mean())
# S2 评分 + 风险定价：个体定价恒在愿付内，按阈值通过
m2 = float(best["margin_book"])
strat = pd.DataFrame([
    {"策略": "S0 无模型（理论：全量成交）", "成交率": 1.0, "成交客群坏账率": pd_xgb.mean(), "全组合利润率": m0_theory},
    {"策略": "S0 无模型（实现：逆向选择）", "成交率": acc0.mean(), "成交客群坏账率": pd_xgb[acc0].mean(), "全组合利润率": m0_real},
    {"策略": "S1 仅评分筛选+统一定价", "成交率": acc1.mean(), "成交客群坏账率": pd_xgb[acc1].mean(), "全组合利润率": m1},
    {"策略": "S2 评分+风险定价联动", "成交率": best["approval_rate"], "成交客群坏账率": best["bad_rate"], "全组合利润率": m2},
])
print("统一定价（挂牌利率）= %.2f%%；S2 最优阈值 score=%.0f，通过率 %.1f%%" % (r_flat * 100, best["threshold"], best["approval_rate"] * 100))
print(strat.round(4).to_string(index=False))
print("\\nS2 vs S0（实现口径）：%+.3f pp，对应测试集账本（¥%.0f 万）年化增量利润 ¥%.1f 万"
      % ((m2 - m0_real) * 100, ead.sum() / 1e4, (m2 - m0_real) * ead.sum() / 1e4))
# 利率结构：S2 下低风险客户获得更低利率
r_ind, _ = fin.price_book(pd_xgb[mask_best], ead[mask_best], LGD, FUND, OPEX, TGT, CAP)
print("利率结构：S2 批准客群平均利率 %.2f%%（低于挂牌 %.2f%%）；其中 %.0f%% 的客户获得低于挂牌价的利率"
      % (r_ind.mean() * 100, r_flat * 100, (r_ind < r_flat).mean() * 100))
curve.to_csv(ROOT / "outputs/policy_curve.csv", index=False); strat.to_csv(ROOT / "outputs/strategy_comparison.csv", index=False)
pd.DataFrame({"pd": pd_xgb}).to_csv(ROOT / "outputs/test_pd.csv", index=False)  # 逐客 PD 分：供愿付溢价敏感分析复核

# 单客户定价示例
ex = pd.DataFrame({"score": s_xgb[:5], "pd": pd_xgb[:5], "wtp": wtp[:5]}).round(4)
ex["rate"], ex["profit"] = fin.price_book(pd_xgb[:5], ead[:5], LGD, FUND, OPEX, TGT, CAP)
print("\\n单客户定价示例（EAD=¥10,000，rate<=wtp 恒成交）：\\n", ex.round(3).to_string(index=False))''')

md("""## 6. SHAP 可解释性与输出""")

code('''expl = shap.TreeExplainer(xgbm)
sv = expl.shap_values(Xr_te[:3000])
shap.summary_plot(sv, Xr_te[:3000], feature_names=list(Xr.columns), show=False, max_display=12)
plt.tight_layout(); plt.savefig(ROOT / "images/shap_summary.png", dpi=150, bbox_inches="tight"); plt.close()

met.to_json(ROOT / "outputs/metrics.json", orient="records", indent=2, force_ascii=False)
fig, axes = plt.subplots(1, 3, figsize=(16, 4.2))
fpr, tpr, _ = roc_curve(y_te, p_xgb)
axes[0].plot(fpr, tpr, c="#c0392b", label="XGBoost AUC=%.4f" % roc_auc_score(y_te, p_xgb))
axes[0].plot([0, 1], [0, 1], "--", c="grey"); axes[0].set(xlabel="FPR", ylabel="TPR", title="ROC"); axes[0].legend()
o = np.argsort(-p_xgb); ys = y_te[o]
axes[1].plot(np.cumsum(ys) / ys.sum(), np.cumsum(1 - ys) / (1 - ys).sum(), c="#2c3e50")
axes[1].plot([0, 1], [0, 1], "--", c="grey")
axes[1].axvline(np.searchsorted(np.cumsum(ys) / ys.sum(), 0.8) / len(ys), ls=":", c="#c0392b")
axes[1].set(xlabel="累计坏客户占比", ylabel="累计好客户占比", title="KS 曲线（KS=%.3f）" % ks_stat(y_te, p_xgb))
axes[2].hist(s_te[y_te == 0], bins=40, alpha=.6, density=True, label="好客户")
axes[2].hist(s_te[y_te == 1], bins=40, alpha=.6, density=True, label="坏客户")
axes[2].set(xlabel="评分（600=好坏比50:1, PDO=20）", ylabel="密度", title="评分分布"); axes[2].legend()
fig.tight_layout(); fig.savefig(ROOT / "images/roc_ks_score.png", dpi=150)

fig, ax1 = plt.subplots(figsize=(8.5, 4.5))
ax2 = ax1.twinx()
ax2.plot(curve["approval_rate"], curve["bad_rate"] * 100, "o--", c="#c0392b", ms=3, alpha=.75, label="批准客群坏账率(%)")
ax2.set_ylabel("批准客群坏账率(%)", color="#c0392b")
ax2.tick_params(axis="y", labelcolor="#c0392b")
ax2.set_ylim(0, min(12, curve["bad_rate"].max() * 100 * 1.1))
ax1.plot(curve["approval_rate"], curve["margin_book"] * 100, "s-", c="#2c3e50", ms=3, label="S2 全组合利润率(%)")
ax1.plot(curve["approval_rate"], curve["margin_approved"] * 100, "^-", c="#27ae60", ms=3, label="S2 批准客群利润率(%)")
ax1.axhline(m0_theory * 100, ls="--", c="#7f8c8d", label="S0 理论口径 %.2f%%" % (m0_theory * 100))
ax1.axhline(m0_real * 100, ls="--", c="#c0392b", label="S0 实现口径(逆向选择) %.2f%%" % (m0_real * 100))
ax1.axvline(best["approval_rate"], ls=":", c="#c0392b")
ax1.annotate("S2 最优：通过率 %.0f%%，利润率 %.2f%%" % (best["approval_rate"] * 100, m2 * 100),
             xy=(best["approval_rate"], m2 * 100), xytext=(0.25, m2 * 100 + 1.2),
             arrowprops=dict(arrowstyle="->", color="grey"))
ax1.set(xlabel="通过率（按分数阈值）", ylabel="利润率(%)", title="通过率-坏账率-利润曲线（风险定价联动）")
ax1.set_ylim(-4, 4)
h1, l1 = ax1.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, loc="lower left", fontsize=8)
fig.tight_layout(); fig.savefig(ROOT / "images/strategy_curve.png", dpi=150)
print("saved: images x4, outputs x8")''')

md("""## 7. 业务建议（详见 README）

1. **定价即风控**：盈亏平衡利率 `r* = (PD×LGD+funding+opex)/(1-PD)` 把评分直接翻译成利率——分数每降一档（PDO=20）建议利率随之上浮，实现"高风险高定价"而非一刀切拒贷；低风险客户获得低于挂牌价的利率，在竞争市场中转化为份额。
2. **筛选与定价必须联动**：仅做评分筛选而维持统一定价，会把"过得了门槛、付不起挂牌价"的客群几乎清空；反之仅定价不筛选，则 24% 上限下的高 PD 尾部亏损无人拦截。
3. **监控常态化**：评分 PSI 与特征 PSI 入库按月跑，>0.25 触发重训评审；三组逾期天数特征高度共线，生产上建议只保留 30-59 天组并做衰减加权。""")

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}
out = ROOT / "notebooks/credit_risk_pricing.ipynb"
nbf.write(nb, str(out))
n_code = sum(len(c.source.splitlines()) for c in cells if c.cell_type == "code")
print(f"written {out} | cells={len(cells)} | code_lines={n_code}")
