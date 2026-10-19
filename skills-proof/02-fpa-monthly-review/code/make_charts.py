# -*- coding: utf-8 -*-
"""从 P4 outputs 提取确切数字，生成 MVP2 一页纸所需图表。
印刷尺度：图宽 3.62in = 92mm，嵌入一页纸后 1:1 显示，字号即印刷磅值。"""
import json
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# ---- OPT-1：可移植路径（脚本位于 <项目>/code/ 时定位项目根；notebook 下 cwd 即根目录）----
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _HERE = os.path.abspath(os.getcwd())
ROOT = os.path.dirname(_HERE) if os.path.basename(_HERE) == "code" else _HERE
OUT = os.path.join(ROOT, "outputs")

# ---- OPT-1：中文字体跨平台注册（① 随附提取字体 → ② 系统字体 → ③ 字体名回退）----
def _register_cjk_font():
    """注册中文字体并返回可用字体名；全部失败时回退 DejaVu Sans（缺字形但不中断）。"""
    candidates = [
        # ① 随附字体：从系统 NotoSansCJK ttc 提取的 SC 单字体面（规避 matplotlib 不支持 ttc 的问题）
        os.path.join(_HERE, "fonts", "NotoSansCJKsc-Regular.otf"),
        os.path.join(ROOT, "fonts", "NotoSansCJKsc-Regular.otf"),
        os.path.join(_HERE, "code", "fonts", "NotoSansCJKsc-Regular.otf"),  # notebook 环境：cwd 为项目根
        os.path.join(ROOT, "code", "fonts", "NotoSansCJKsc-Regular.otf"),
        # ② 系统常见字体路径
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansSC-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "C:/Windows/Fonts/msyh.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                font_manager.fontManager.addfont(p)
            except Exception:
                pass  # ttc 多字体面注册失败时继续尝试其他候选
    # 粗体字面（存在则注册，用于标题与关键数值的真加粗）
    bold_candidates = [
        os.path.join(_HERE, "fonts", "NotoSansCJKsc-Bold.otf"),
        os.path.join(ROOT, "fonts", "NotoSansCJKsc-Bold.otf"),
        os.path.join(_HERE, "code", "fonts", "NotoSansCJKsc-Bold.otf"),
        os.path.join(ROOT, "code", "fonts", "NotoSansCJKsc-Bold.otf"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
    ]
    for p in bold_candidates:
        if os.path.exists(p):
            try:
                font_manager.fontManager.addfont(p)
            except Exception:
                pass
    have = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Noto Sans CJK SC", "Noto Sans SC", "Microsoft YaHei",
                 "PingFang SC", "WenQuanYi Micro Hei", "WenQuanYi Zen Hei"):
        if name in have:
            return name
    return "DejaVu Sans"

plt.rcParams["font.sans-serif"] = [_register_cjk_font(), "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
km = json.load(open(f"{OUT}/key_metrics.json", encoding="utf-8"))
Q_HIST = [f"{y}Q{q}" for y in (2023, 2024, 2025, 2026) for q in (1, 2, 3, 4)][:15]
Q_FC = km["quarters_fc"]
Q_ALL = Q_HIST + Q_FC

C_UP, C_DOWN = "#C0392B", "#1E8449"           # 中国市场惯例：涨红跌绿
C_ANCHOR, C_LINE, C_POST, C_RED = "#2C3E50", "#1F618D", "#117A65", "#C0392B"
GRID = dict(axis="y", color="#D5DBDB", lw=0.5, alpha=0.8)

# ============================================================
# 图1：EBITDA 差异桥瀑布图（2025A -> 2026E）
# ============================================================
bridge = km["bridge"]
labels = [b[0] for b in bridge]
kinds = [b[2] for b in bridge]
short = {"2025A EBITDA": "2025A\nEBITDA", "2026E EBITDA": "2026E\nEBITDA"}

fig, ax = plt.subplots(figsize=(3.62, 2.3), dpi=300)
cum = 0.0
for i, (lb, v, kd) in enumerate(bridge):
    if kd == "anchor":
        ax.bar(i, v, width=0.62, color=C_ANCHOR, zorder=3)
        ax.text(i, v + 0.14, f"{v:.2f}", ha="center", va="bottom",
                fontsize=6.4, fontweight="bold", color=C_ANCHOR)
        if i > 0:
            ax.plot([i - 1 + 0.31, i - 0.31], [cum, cum], color="#95A5A6", lw=0.7,
                    ls=(0, (2, 2)), zorder=2)
        cum = v
    else:
        bottom = cum if v >= 0 else cum + v
        color = C_UP if v >= 0 else C_DOWN
        ax.bar(i, abs(v), bottom=bottom, width=0.62, color=color, zorder=3)
        sign_y = cum + v + 0.14 if v >= 0 else cum + 0.14
        ax.text(i, sign_y, f"{v:+.2f}", ha="center", va="bottom",
                fontsize=6.0, fontweight="bold", color=color)
        ax.plot([i - 0.31, i + 0.31], [cum, cum], color="#95A5A6", lw=0.7,
                ls=(0, (2, 2)), zorder=2)
        cum += v

ax.axhline(0, color="#2C3E50", lw=0.8)
ax.set_xticks(range(len(bridge)))
ax.set_xticklabels([short.get(lb, lb) for lb in labels], fontsize=5.9)
ax.set_ylim(-0.35, 7.1)
ax.set_yticks([0, 2, 4, 6])
ax.tick_params(axis="y", labelsize=5.9)
ax.set_ylabel("亿元", fontsize=6.2)
ax.set_title("EBITDA 差异桥：2025A → 2026E（亿元）",
             fontsize=7.6, fontweight="bold", color="#1B2631", pad=7)
ax.text(0.995, 0.985,
        f"改善+{km['eff_split']['total']:.2f}亿＝规模增长+{km['eff_split']['from_growth']:.2f}＋利润率提升+{km['eff_split']['from_margin']:.2f}（95%）",
        transform=ax.transAxes, ha="right", va="top", fontsize=5.7, color="#566573")
ax.grid(**GRID, zorder=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=C_UP, label="正向贡献"), Patch(color=C_DOWN, label="负向贡献"),
                   Patch(color=C_ANCHOR, label="年度值")],
          loc="upper left", fontsize=5.6, frameon=False, ncol=3,
          bbox_to_anchor=(-0.01, 1.005), handlelength=1.1, columnspacing=0.9, handletextpad=0.4)
plt.tight_layout(pad=0.35)
plt.savefig(f"{OUT}/fig1_ebitda_bridge.png", bbox_inches="tight", facecolor="white")
plt.close()

# ============================================================
# 图2：现金流折线图（历史实际 + 基准预测 + 融资后）
# ============================================================
cash_h, cash_b, cash_p = km["cash_hist"], km["cash_base"], km["cash_base_post"]
n_h, n_f = len(cash_h), len(cash_b)
x_h = np.arange(n_h)
x_f = np.arange(n_h - 1, n_h + n_f)

fig, ax = plt.subplots(figsize=(3.62, 2.3), dpi=300)
ax.plot(x_h, cash_h, color=C_LINE, lw=1.5, marker="o", ms=2.4, zorder=4, label="历史实际")
ax.plot(x_f, np.concatenate([[cash_h[-1]], cash_b]), color=C_LINE, lw=1.5, ls="--",
        marker="o", ms=2.4, zorder=4, label="基准预测(未融资)")
ax.plot(x_f, np.concatenate([[cash_h[-1]], cash_p]), color=C_POST, lw=1.5,
        marker="s", ms=2.2, zorder=4, label="融资后(股权3.0亿)")
ax.axhline(km["min_cash"], color=C_RED, lw=1.0, ls=(0, (4, 2)), zorder=3)
ax.text(0.3, km["min_cash"] + 0.14, f"最低运营现金红线 {km['min_cash']:.1f}亿",
        fontsize=5.6, color=C_RED, va="bottom")

tr = int(np.argmin(cash_b))
tr_i = n_h - 1 + tr
ax.annotate(f"低点 {cash_b[tr]:.2f}亿\n({Q_FC[tr]})", xy=(tr_i, cash_b[tr]),
            xytext=(tr_i - 6.2, cash_b[tr] - 0.55), fontsize=5.7, color=C_RED,
            fontweight="bold", va="top",
            arrowprops=dict(arrowstyle="->", color=C_RED, lw=0.8))
ax.annotate("股权3.0亿\n一次性到账", xy=(n_h, cash_p[1] - 0.28),
            xytext=(n_h - 8.6, 6.55), fontsize=5.7, color=C_POST, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=C_POST, lw=0.8))

ticks = list(range(0, n_h + n_f, 3))
ax.set_xticks(ticks)
ax.set_xticklabels([Q_ALL[i] for i in ticks], fontsize=5.6)
ax.tick_params(axis="y", labelsize=5.6)
ax.set_ylim(-0.5, 9.2)
ax.set_ylabel("期末现金余额（亿元）", fontsize=6.2)
ax.set_title("期末现金余额：历史实际 vs 基准情景预测（亿元）",
             fontsize=7.6, fontweight="bold", color="#1B2631", pad=7)
ax.grid(**GRID, zorder=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.axvline(n_h - 0.5, color="#7F8C8D", lw=0.8, ls=":")
ax.text(n_h - 0.35, 8.7, "预测 →", fontsize=5.6, color="#7F8C8D")
ax.legend(loc="upper left", fontsize=5.6, frameon=False, ncol=2,
          bbox_to_anchor=(-0.005, 1.005), handlelength=1.4, columnspacing=0.8)
plt.tight_layout(pad=0.35)
plt.savefig(f"{OUT}/fig2_cashflow.png", bbox_inches="tight", facecolor="white")
plt.close()
print("charts done (print scale)")
