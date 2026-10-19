# -*- coding: utf-8 -*-
"""把 p4_analysis.py 与 make_charts.py 组装为可执行的 P4_analysis.ipynb 并执行嵌入输出。"""
import os
import re

import nbformat as nbf

# 可移植路径：脚本位于 <项目>/code/ 时定位项目根；直接运行时 cwd 即根目录
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _HERE = os.path.abspath(os.getcwd())
DOC = os.path.dirname(_HERE) if os.path.basename(_HERE) == "code" else _HERE

src = open(f"{DOC}/code/p4_analysis.py", encoding="utf-8").read()
charts = open(f"{DOC}/code/make_charts.py", encoding="utf-8").read()
charts_code = charts  # notebook 内自包含：含字体注册、可移植路径与绘图代码

# 按章节 banner 切分
parts = re.split(r"# ={20,}\n(# \d+\. .*?)\n# ={20,}\n", src)
# parts: [preamble, header1, body1, header2, body2, ...]
preamble = parts[0].strip()
sections = [(parts[i].lstrip("# ").strip(), parts[i + 1].strip()) for i in range(1, len(parts), 2)]

nb = nbf.v4.new_notebook()
nb.metadata.update({"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                    "language_info": {"name": "python", "version": "3.11"}})

nb.cells.append(nbf.v4.new_markdown_cell(
    "# P4 分析：星联金科 FP&A 模型（Holt-Winters 预测 · 量价分解 · 三情景 · 现金流与融资）\n\n"
    "**单位**：人民币亿元｜**口径**：管理会计（税前、不含联营）｜**历史区间**：2023Q1–2026Q3（15 个季度）\n\n"
    "> **数据来源说明（OPT-2）**：本包所有历史与预测数据均为**模拟数据**——\"星联金科\"为虚构的演示公司，"
    "用于完整展示 FP&A 月度经营分析的方法论与工程链路，不构成任何投资建议。所有假设在代码中显式列出、可逐条追溯。\n\n"
    "本 notebook 是 MVP2 一页纸的**唯一数据源**：`outputs/` 下全部 CSV 与 `key_metrics.json` 由此生成，"
    "一页纸 HTML 从 `key_metrics.json` 程序化注入数字，无任何手工转录。\n\n"
    "**方法论要点**：\n"
    "1. 收入 Holt-Winters 指数平滑 ETS(A,Ad,M)（有界 MLE，无约束解在小样本下退化，见敏感性对照）；\n"
    "2. 变现率 Holt 线性趋势 ETS(A,A,N)；2028 按基准情景 +20% 平移季节性；\n"
    "3. 量价分解惯例：规模效应 = ΔV×P25，价格效应 = V26×ΔP（已在输出中披露）；\n"
    "4. 三情景与季度现金流引擎完全同源（基准 = HW 中枢，悲观/乐观按规模增速 ∓/±12pp、变现率 −0.20/+0.12pp 缩放），"
    "另附变现率单因素敏感度（±0.10/±0.20pp）；\n"
    "5. 融资路径：股权 3.0 亿（2027Q1 一次性）+ 银行授信 2.0 亿按需提款，授信利息按 4.5%/年对季初提款余额计价、计入现金路径；\n"
    "6. EBITDA 差异桥为 P&L 行级桥（各行为 EBITDA 贡献口径，可加和）。"))

# 前言（imports + 假设）
nb.cells.append(nbf.v4.new_markdown_cell("## 0. 基础假设（显式可追溯）"))
nb.cells.append(nbf.v4.new_code_cell(preamble))

TITLES = {
    "1": "## 1. 历史季度损益表",
    "2": "## 2. Holt-Winters 指数平滑预测（基准情景）\n\n"
         "**参数边界依据（OPT-4）**：样本仅 15 个季度，无约束 MLE 会退化为 α→1、β→0、γ→0（趋势与季节项被同时关闭，"
         "SSE 翻倍至 0.11，2027E 收入低估 5% 至 23.49 亿），故采用有界 MLE。边界取值：α∈[0.4,0.8]——上界 0.8 防止单季度噪声主导；"
         "β∈[0.1,0.3]、γ∈[0.1,0.3]——趋势与季节保持适度灵活而不追逐噪声。另以\"无约束（弃用）/窄区间/严区间\""
         "三档边界做敏感性对照，2027E 收入区间 23.49–24.79 亿（相对中枢 -5%~+0.3%），结论对边界选择不敏感。",
    "3": "## 3. 2026E 与量价分解（2025A → 2026E）\n\n"
         "**两个规模贡献口径的区分（OPT-3）**：\n"
         "- **收入增量归因**（量价分解惯例）：规模效应 = ΔV×P25 = +4.40 亿、价格效应 = V26×ΔP = +1.15 亿，"
         "用于回答\"收入增长从哪来\"；\n"
         "- **EBITDA 改善归因**（反事实口径）：若 2026 年维持 2025 年 EBITDA 利润率，规模增长仅贡献 +0.10 亿，"
         "其余 +1.97 亿来自利润率提升——用于回答\"利润改善是靠规模还是靠单位经济\"。\n"
         "两个口径回答不同问题，均显式披露，不可混用。",
    "4": "## 4. 三情景（2027E 全年，与季度引擎同源）\n\n"
         "三情景以 HW 为中枢：悲观/乐观在**规模增速**（∓/±12pp）与**变现率**（−0.20/+0.12pp）两个维度上施加压力/乐观偏移，"
         "季度路径由基准引擎按年度比例缩放（基准情景 k=1，与引擎完全同源）。\n\n"
         "**变现率单因素敏感度**：为区分\"规模\"与\"变现率\"各自的影响，另固定规模增速于基准、仅将变现率平移 ±0.10/±0.20pp："
         "变现率每 ±0.10pp，2027E 净收入 ±0.60 亿、EBITDA ±0.33 亿（ΔEBITDA = Δ收入 ×（1 − 获客% − 运营%）——"
         "信用与风险分担按放款额计价，不受变现率影响）；±0.20pp 覆盖三情景全部变现率离散度，EBITDA 区间 3.87–5.18 亿。",
    "5": "## 5. 历史与预测期现金流（季度滚动）\n\n"
         "期末现金 = 期初 + EBITDA − Capex − ΔNWC + 净融资；ΔNWC = 6% × 收入环比增量；"
         "最低运营现金红线 3.0 亿（约 1 个季度峰值净现金流出 + 结算在途缓冲）。\n\n"
         "**融资路径（OPT-5）**：融资总额 5.0 亿 = **股权 3.0 亿**（2027Q1 一次性到账）+ **银行授信 2.0 亿**"
         "（按需提款：仅当季末现金低于 4.0 亿地板价时提款补足，总额不超过额度）。"
         "**授信利息已正式建入模型**：按年利率 4.5%（1Y LPR + 适度上浮，假设值）对**季初存量提款余额**计价，"
         "作为当期现金流出计入融资后路径（当季提款次季起计息，闲置不计息）。\n\n"
         "基准情景下股权到账后现金即回到红线上方（低点 5.23 亿），无需动用授信、无利息支出；"
         "悲观情景下授信 2.0 亿分 3 次提尽、预测期利息合计 0.12 亿，现金探底 0.20 亿，故叠加成本触发预案。\n\n"
         "**成本触发机制（OPT-6）**：悲观情景预案——若连续两季收入增速 <10%（最早 2027Q2 末确认触发），"
         "获客成本 −30%、运营成本 −15%，对 2027 年收入年化释放 2.46 亿；释放额自 2027Q3 起按季度线性累积（1/4→2/4→3/4→全额），"
         "触发后悲观情景低点回到 3.90 亿，守住红线。该机制不计入基准情景，仅作为与融资绑定的保护条款测算。"
         "注：释放额按 2027 年悲观收入固定计算，若触发延续至 2028 年实际释放更高，此处偏保守。",
    "6": "## 6. P&L 行级差异桥（2025A → 2026E）",
    "7": "## 7. 导出 outputs/（CSV + key_metrics.json）\n\n"
         "导出 6 个数据文件：quarterly_pl.csv（历史季度 P&L）、hw_forecast_cashflow.csv（预测+三情景现金路径，"
         "含授信利息列）、scenario_summary.csv（三情景汇总）、take_sensitivity.csv（变现率单因素敏感度）、"
         "ebitda_bridge.csv（差异桥）、key_metrics.json（全部指标，一页纸的唯一数字源）。\n\n"
         "**月度粒度切换**：代码中 `MONTHLY = False`（默认）。置为 `True` 时额外导出 monthly_pl.csv——"
         "历史+预测全序列按\"季度值三等分均摊\"展开为月度行；口径上收入/成本/EBITDA 为期间值可均摊，"
         "变现率取季度值、现金取期末余额重复，模型不含月度季节性假设，月度行仅用于汇报颗粒度切换。",
    "8": "## 8. 控制台摘要（供团队核对）",
}
for header, body in sections:
    num = header.split(".")[0]
    if num in TITLES:
        nb.cells.append(nbf.v4.new_markdown_cell(TITLES[num]))
    nb.cells.append(nbf.v4.new_code_cell(body))

nb.cells.append(nbf.v4.new_markdown_cell(
    "## 9. 生成 MVP2 一页纸图表（印刷尺度 3.62in ≈ 92mm，1:1 嵌入）\n\n"
    "图1 差异桥瀑布图、图2 现金流折线图；中国市场惯例：正向贡献红色、负向贡献绿色。"))
charts_nb = charts_code + (
    '\n\n# 在 notebook 内联展示生成的图表\n'
    'from IPython.display import Image, display\n'
    'display(Image(filename=f"{OUT}/fig1_ebitda_bridge.png"))\n'
    'display(Image(filename=f"{OUT}/fig2_cashflow.png"))\n'
)
nb.cells.append(nbf.v4.new_code_cell(charts_nb))

nbf.write(nb, f"{DOC}/P4_analysis.ipynb")
print("notebook written, cells:", len(nb.cells))
