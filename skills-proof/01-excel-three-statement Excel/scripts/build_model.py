#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星链数科（模拟 fintech）三表联动模型 v4

v4 = v3 全部功能（情景切换器 / 现金跑道 / 结论看板 / 演示动线 / 债务+固定资产排程）
    + MVP1 优化清单落地：
      · 说明页：30 秒速览（3 行）+ 模型地图（Sheet 关系文字版）
      · 敏感性页：第六节三情景并排对比表（净利润 / 现金 / 股权价值 / 保障倍数）
      · 支持排程：新增 ROIC = EBIT×(1−t)/(有息负债+总权益−现金)
      · 注释补全：简化假设声明（敏感性①）、终值假设（DCF）、边际敏感度局部近似、
        数组推导（敏感性③）、新增借款生息口径（债务排程）
      · 现金流量表行名改为“营运资本变动（增加 = 现金占用）”
    v3 原有结构性扩展：
      · 新增「支持排程」Sheet：债务排程（期初→新增→偿还→期末）+ 偿债能力指标
      · 利息 = 平均有息负债 × 年利率（含新增借款生息），当年全额付现
      · 利息付现列入筹资活动，经营活动加回，净利润已含税盾 → 无循环引用
    + 优化四.1 固定资产排程：
      · 折旧按期初固定资产净值 × 折旧率计提，以期初净值为上限（MIN），不会折成负值
      · 原值 / 资本支出 / 净值 / 累计折旧滚动，利润表折旧与资产负债表净值全部联动

现金流勾稽（含利息的会计口径，中国企业会计准则）：
  经营 = 净利润 + 折旧 + 利息费用 − 营运资本增加        （间接法加回财务费用）
  投资 = −资本支出
  融资 = 新增借款 − 偿还本金 − 偿付利息
  净利润 = （EBIT − 利息费用）×（1 − 税率），利息税盾自然体现在净利润中

用法: python3 scripts/build_model.py [增长率 默认0.05] [输出路径]

交付说明：脚本产出"公式版"工作簿（fullCalcOnLoad=True，Excel/WPS/LibreOffice 打开即自动重算）；
如需程序化读取数值，用 LibreOffice headless 转换一次以写入缓存值即可。
"""
import sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.marker import Marker
from openpyxl.worksheet.pagebreak import Break

GROWTH = float(sys.argv[1]) if len(sys.argv) > 1 else 0.05
OUT = sys.argv[2] if len(sys.argv) > 2 else "three_statement_model.xlsx"

A = "假设"
S = "支持排程"
FONT = "微软雅黑"
DARK, MID, LIGHT, CHECKF, GREY = "1F4E79", "2E75B6", "D9E1F2", "BDD7EE", "F2F2F2"
BLUE, GREEN, BLACK, WHITE, GREYT = "0000FF", "008000", "000000", "FFFFFF", "808080"
MONEY = "#,##0;(#,##0)"
DIFF = "#,##0.00;(#,##0.00)"
PCT0, PCT1, NUM = "0%", "0.0%", "#,##0"
YEARS = ["2025A", "2026E", "2027E", "2028E", "2029E", "2030E"]
COLS = ["B", "C", "D", "E", "F", "G"]
FC = COLS[1:]

# ---- 假设面板行号（单一事实来源，公式一律引用常量） ----
R_SEL, R_HDR = 3, 4
AS = dict(g=5, m=6, cac=7, tax=8, disc=9, cust=10, capex=11,
          ar=12, ap=13, safe=14, rate=15, deprate=16)
R_MAP_T, R_MAP_H = 24, 25
R_MAP_1, R_MAP_2, R_MAP_3 = 26, 27, 28

# ---- 利润表行号 ----
IS = dict(cust=4, rev=5, gp=6, opex=7, dep=8, ebit=9, int=10, ebt=11,
          tax=12, ni=13, sec=15, growth=16, arpu=17, gm=18, nm=19)
# ---- 资产负债表行号 ----
BS = dict(ta=8, ap=10, debt=11, tl=12, eq=14, re=15, te=16, tle=17,
          lev=18, sec2=19, diff1=20, res1=21, diff2=22, res2=23)
# ---- 现金流量表行号 ----
CF = dict(ni=5, dep=6, int=7, wc=8, cfo=9, capex=11, cfi=12,
          borrow=14, repay=15, intpaid=16, cff=17, net=18, beg=19,
          end=20, fcf=21, safe=22, flag=23, note=24)
# ---- 支持排程行号 ----
SUP = dict(beg=5, new=6, repay=7, end=8, avg=9, int=10, negchk=11,
           sec2=13, lev=14, de=15, cov=16, roic=17, sec3=18, gbeg=19, capex=20,
           gend=21, nbeg=22, dep=23, nend=24, accdep=25, note=27)
# ---- 敏感性分析行号 ----
SN = dict(hdr=5, fcf=6, df=7, pv=8, sumpv=10, tv=11, tpv=12, ev=13,
          netcash=14, eq=15, note=16, sec2=18, s2note=19, s2hdr=20,
          s2r0=21, s2chk=26, s2note2=27, sec3=29, s3note=30, s3hdr=31,
          s3r0=32, s3chk=37, s3note2=38, sec4=40, g1=41, g2=42, cum1=43,
          cum2=44, marg=45, margnote=46, sec5=48, s5note=49, s5hdr=50, s5r0=51,
          s5chk=56, s5note2=57, sec6=59, s6note=60, s6hdr=61, s6g=62, s6m=63,
          s6ni=64, s6cash=65, s6eq=66, s6cov=67, s6chk=68, calchdr=70,
          cfBase=71, cfBull=72, cfBear=73, evBase=75, evBull=76, evBear=77,
          eqBase=78, eqBull=79, eqBear=80, ebBase=82, ebBull=83, ebBear=84,
          cvBase=86, cvBull=87, cvBear=88, concl=90)

thin = Side(style="thin", color="BFBFBF")
BD = Border(left=thin, right=thin, top=thin, bottom=thin)


def put(ws, coord, value, bold=False, color=BLACK, size=10, fill=None, fmt=None,
        align=None, border=True, italic=False, wrap=False):
    c = ws[coord]
    c.value = value
    c.font = Font(name=FONT, bold=bold, color=color, size=size, italic=italic)
    if fill:
        c.fill = PatternFill("solid", start_color=fill)
    if fmt:
        c.number_format = fmt
    c.alignment = Alignment(horizontal=align, vertical="center", wrap_text=wrap)
    if border:
        c.border = BD
    return c


def title_bar(ws, row, text, span, sub=None):
    ws.merge_cells(f"A{row}:{span}{row}")
    put(ws, f"A{row}", text, bold=True, color=WHITE, size=12, fill=DARK,
        align="left", border=False)
    ws.row_dimensions[row].height = 24
    if sub:
        ws.merge_cells(f"A{row+1}:{span}{row+1}")
        put(ws, f"A{row+1}", sub, color=GREYT, size=9, align="left",
            border=False, italic=True)


def year_header(ws, row):
    put(ws, f"A{row}", "项目", bold=True, fill=LIGHT, align="left")
    for col, y in zip(COLS, YEARS):
        put(ws, f"{col}{row}", y, bold=True, fill=LIGHT, align="center")


def sec(ws, row, text, span="G"):
    for i in range(ord(span) - ord("A") + 1):
        put(ws, f"{chr(65+i)}{row}", None, fill=LIGHT, bold=True)
    put(ws, f"A{row}", text, bold=True, fill=LIGHT, align="left")


def page(ws, wide=False):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1 if not wide else 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_margins.left = ws.page_margins.right = 0.35
    ws.sheet_view.showGridLines = False


wb = Workbook()
wb.properties.title = "星链数科三表联动模型 v3"
wb.properties.creator = "Model Builder"

ws_doc = wb.active
ws_doc.title = "说明与检查"
ws_a = wb.create_sheet(A)
ws_is = wb.create_sheet("利润表")
ws_bs = wb.create_sheet("资产负债表")
ws_cf = wb.create_sheet("现金流量表")
ws_sc = wb.create_sheet(S)
ws_ch = wb.create_sheet("图表")
ws_sn = wb.create_sheet("敏感性分析")

# ============================================================ 假设
ws = ws_a
ws.sheet_properties.tabColor = DARK
for col, w in zip("ABCDEF", [7, 30, 13, 11, 26, 54]):
    ws.column_dimensions[col].width = w
title_bar(ws, 1, "星链数科（模拟 fintech 公司）— 假设面板（模型主控台）", "F",
          "单位：人民币元 | 基年 2025A（蓝色实际数）| 预测期 2026E–2030E | 切换顶部情景 → 三张报表 + 支持排程 + 图表 + 敏感性分析全部联动重算")

put(ws, f"A{R_SEL}", "① 情景切换（主控台）", bold=True, color=WHITE, fill=MID, align="left")
put(ws, f"B{R_SEL}", "Base", bold=True, color=BLUE, fill=GREY, align="center", size=11)
for col in "CD":
    put(ws, f"{col}{R_SEL}", None, fill=GREY)
ws.merge_cells(f"C{R_SEL}:F{R_SEL}")
put(ws, f"C{R_SEL}", "下拉选择：Base / Bull / Bear　→　自动切换下方增长率与毛利率",
    color=GREYT, size=9, align="left")

for i, h in enumerate(["编号", "假设项", "数值", "单位", "数据验证", "影响范围"]):
    put(ws, f"{chr(65+i)}{R_HDR}", h, bold=True, fill=LIGHT, align="center")

ASSUM = [
    dict(no="A-01", name="收入增长率", mode="link_g", fmt=PCT0, unit="%",
         dv="情景联动（Base/Bull/Bear）", impact="收入、客户数、毛利、净利润、留存收益、现金"),
    dict(no="A-02", name="毛利率", mode="link_m", fmt=PCT1, unit="%",
         dv="情景联动（Base/Bull/Bear）", impact="毛利、税前利润、净利润"),
    dict(no="A-03", name="获客成本 CAC", mode=200, fmt=NUM, unit="元/客户",
         dv="数值：100–500", impact="运营成本、净利润", dvtype="decimal", lo="100", hi="500"),
    dict(no="A-04", name="企业所得税率", mode=0.25, fmt=PCT1, unit="%",
         dv="数值：0%–35%", impact="所得税费用、净利润", dvtype="decimal", lo="0", hi="0.35"),
    dict(no="A-05", name="折现率", mode=0.10, fmt=PCT1, unit="%",
         dv="数值：5%–20%", impact="估值（见敏感性分析）", dvtype="decimal", lo="0.05", hi="0.2"),
    dict(no="A-06", name="客户数（基年）", mode=1000, fmt=NUM, unit="户",
         dv="数值：1–100,000", impact="客户数、运营成本、净利润", dvtype="whole", lo="1", hi="100000"),
    dict(no="A-07", name="年资本支出", mode=100000, fmt=NUM, unit="元/年",
         dv="数值：0–1,000,000", impact="投资现金流、固定资产原值与净值、期末现金",
         dvtype="whole", lo="0", hi="1000000"),
    dict(no="A-08", name="应收账款占收入比", mode=0.10, fmt=PCT1, unit="%",
         dv="数值：0%–50%", impact="应收账款、营运资本、经营现金流", dvtype="decimal", lo="0", hi="0.5"),
    dict(no="A-09", name="应付账款占收入比", mode=0.05, fmt=PCT1, unit="%",
         dv="数值：0%–50%", impact="应付账款、营运资本、经营现金流", dvtype="decimal", lo="0", hi="0.5"),
    dict(no="A-10", name="现金安全线", mode=4000000, fmt=NUM, unit="元",
         dv="数值：0–10,000,000", impact="现金跑道图预警线", dvtype="whole", lo="0", hi="10000000"),
    dict(no="A-11", name="借款年利率", mode=0.045, fmt=PCT1, unit="%",
         dv="数值：0%–15%", impact="利息费用、税前利润、净利润、偿债能力指标",
         dvtype="decimal", lo="0", hi="0.15"),
    dict(no="A-12", name="折旧率（按固定资产净值）", mode=0.05, fmt=PCT1, unit="%",
         dv="数值：0%–20%", impact="折旧、税前利润、固定资产净值、经营现金流",
         dvtype="decimal", lo="0", hi="0.2"),
]
for i, it in enumerate(ASSUM):
    r = AS["g"] + i
    put(ws, f"A{r}", it["no"], align="center", color=GREYT)
    put(ws, f"B{r}", it["name"], align="left")
    if it["mode"] == "link_g":
        f = f"=INDEX($B${R_MAP_1}:$B${R_MAP_3},MATCH($B${R_SEL},$A${R_MAP_1}:$A${R_MAP_3},0))"
        put(ws, f"C{r}", f, color=BLACK, fill=CHECKF, fmt=it["fmt"], align="center", bold=True)
    elif it["mode"] == "link_m":
        f = f"=INDEX($C${R_MAP_1}:$C${R_MAP_3},MATCH($B${R_SEL},$A${R_MAP_1}:$A${R_MAP_3},0))"
        put(ws, f"C{r}", f, color=BLACK, fill=CHECKF, fmt=it["fmt"], align="center", bold=True)
    else:
        put(ws, f"C{r}", it["mode"], color=BLUE, fill=GREY, fmt=it["fmt"], align="center", bold=True)
        dv = DataValidation(type=it["dvtype"], operator="between",
                            formula1=it["lo"], formula2=it["hi"], allow_blank=False,
                            errorTitle="输入无效", error=f"请输入 {it['dv'].replace('数值：','')} 范围内的数值",
                            promptTitle=it["name"], prompt=f"有效范围：{it['dv'].replace('数值：','')}")
        dv.showErrorMessage = True
        dv.showInputMessage = True
        ws.add_data_validation(dv)
        dv.add(f"C{r}")
    put(ws, f"D{r}", it["unit"], align="center", color=GREYT)
    put(ws, f"E{r}", it["dv"], align="left", size=9)
    put(ws, f"F{r}", it["impact"], align="left", size=9)

dv_sel = DataValidation(type="list", formula1='"Base,Bull,Bear"', allow_blank=False,
                        errorTitle="输入无效", error="请从下拉列表中选择：Base / Bull / Bear",
                        promptTitle="情景切换",
                        prompt="切换情景后，收入增长率与毛利率自动切换，三表联动")
dv_sel.showErrorMessage = True
dv_sel.showInputMessage = True
ws.add_data_validation(dv_sel)
dv_sel.add(f"B{R_SEL}")

ws.merge_cells(f"A{R_MAP_T}:F{R_MAP_T}")
put(ws, f"A{R_MAP_T}", "② 驱动因子映射表（情景切换器数据源 · 蓝色可直接修改）",
    bold=True, color=WHITE, fill=MID, align="left")
for col, h in zip("ABC", ["情景", "收入增长率", "毛利率"]):
    put(ws, f"{col}{R_MAP_H}", h, bold=True, fill=LIGHT, align="center")
SCEN = [("Base", GROWTH, 0.60), ("Bull", 0.10, 0.65), ("Bear", 0.03, 0.55)]
for i, (nm, g, m) in enumerate(SCEN):
    r = R_MAP_1 + i
    put(ws, f"A{r}", nm, bold=True, align="center", fill=GREY, color=BLUE)
    put(ws, f"B{r}", g, color=BLUE, fill=GREY, fmt=PCT0, align="center")
    put(ws, f"C{r}", m, color=BLUE, fill=GREY, fmt=PCT1, align="center")
dv_g = DataValidation(type="list", formula1='"3%,5%,8%,10%,15%,20%"', allow_blank=False,
                      errorTitle="输入无效",
                      error="请从下拉列表中选择：3% / 5% / 8% / 10% / 15% / 20%",
                      promptTitle="收入增长率", prompt="下拉选择")
dv_g.showErrorMessage = True
dv_g.showInputMessage = True
ws.add_data_validation(dv_g)
dv_g.add(f"B{R_MAP_1}:B{R_MAP_3}")
dv_m = DataValidation(type="decimal", operator="between", formula1="0", formula2="1",
                      allow_blank=False, errorTitle="输入无效",
                      error="请输入 0%–100% 之间的数值", promptTitle="毛利率",
                      prompt="有效范围：0%–100%")
dv_m.showErrorMessage = True
dv_m.showInputMessage = True
ws.add_data_validation(dv_m)
dv_m.add(f"C{R_MAP_1}:C{R_MAP_3}")

notes = [
    "颜色规范：蓝色字体 = 可修改输入；黑色字体 = 本表公式计算；绿色字体 = 跨表引用；浅蓝底 = 受情景切换器驱动或校验区。",
    "① 情景切换：顶部下拉框切换 Base / Bull / Bear，自动改变收入增长率与毛利率；其余假设沿用默认值，可单独覆盖。",
    "② 驱动因子映射表位于本表下方（可见可改）：三情景的增长率/毛利率均带数据验证，改数值即可自定义情景。",
    "③ 债务与折旧排程集中在「支持排程」页：新增借款/偿还本金为蓝色融资计划输入；利息 = 平均有息负债 × 年利率（A-11），当年全额付现，不构成循环引用。",
    "④ 折旧按固定资产期初净值 × 折旧率（A-12）计提，并以期初净值为上限，不会折成负值；原值/净值/累计折旧滚动见「支持排程」页。",
    "⑤ 所有预测单元格均为公式、无硬编码——改任一项，利润表 / 资产负债表 / 现金流量表 / 支持排程 / 图表 / 敏感性分析同步联动。",
]
for i, t in enumerate(notes):
    r = 18 + i
    ws.merge_cells(f"A{r}:F{r}")
    put(ws, f"A{r}", t, color=GREYT, size=9, border=False, align="left")
ws.freeze_panes = "A5"
page(ws)

# ============================================================ 利润表
ws = ws_is
ws.sheet_properties.tabColor = MID
ws.column_dimensions["A"].width = 32
for col in COLS:
    ws.column_dimensions[col].width = 13
title_bar(ws, 1, "星链数科 — 利润表（Income Statement）", "G",
          "单位：元 | 2025A 为基年实际数（蓝色），2026E–2030E 由假设面板情景驱动；利息费用来自「支持排程」债务排程")
year_header(ws, 3)
for r, label, bold in [
    (IS["cust"], "客户数（期末，户）", False),
    (IS["rev"], "营业收入", False),
    (IS["gp"], "毛利", False),
    (IS["opex"], "运营成本（获客：客户数×CAC）", False),
    (IS["dep"], "折旧（支持排程·按净值计提）", False),
    (IS["ebit"], "息税前利润 EBIT", True),
    (IS["int"], "减：利息费用（平均有息负债×利率）", False),
    (IS["ebt"], "税前利润", True),
    (IS["tax"], "减：所得税费用", False),
    (IS["ni"], "净利润", True),
]:
    put(ws, f"A{r}", label, bold=bold, align="left", fill=CHECKF if bold else None)
put(ws, f"B{IS['cust']}", f"={A}!$C${AS['cust']}", color=GREEN, fmt=NUM)
for coord, v in [(f"B{IS['rev']}", 1000000), (f"B{IS['gp']}", 600000),
                 (f"B{IS['opex']}", 200000), (f"B{IS['dep']}", 100000)]:
    put(ws, coord, v, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, f"B{IS['ebit']}", f"=B{IS['gp']}-B{IS['opex']}-B{IS['dep']}", fmt=MONEY, bold=True)
put(ws, f"B{IS['int']}", f"={S}!B{SUP['int']}", color=GREEN, fmt=MONEY)
put(ws, f"B{IS['ebt']}", f"=B{IS['ebit']}-B{IS['int']}", fmt=MONEY, bold=True)
put(ws, f"B{IS['tax']}", f"=MAX(B{IS['ebt']},0)*{A}!$C${AS['tax']}", fmt=MONEY)
put(ws, f"B{IS['ni']}", f"=B{IS['ebt']}-B{IS['tax']}", fmt=MONEY, bold=True, fill=CHECKF)
for i, x in enumerate(FC):
    p = COLS[i]
    put(ws, f"{x}{IS['cust']}", f"={p}{IS['cust']}*(1+{A}!$C${AS['g']})", fmt=NUM)
    put(ws, f"{x}{IS['rev']}", f"={p}{IS['rev']}*(1+{A}!$C${AS['g']})", fmt=MONEY)
    put(ws, f"{x}{IS['gp']}", f"={x}{IS['rev']}*{A}!$C${AS['m']}", fmt=MONEY)
    put(ws, f"{x}{IS['opex']}", f"={x}{IS['cust']}*{A}!$C${AS['cac']}", fmt=MONEY)
    put(ws, f"{x}{IS['dep']}", f"={S}!{x}{SUP['dep']}", color=GREEN, fmt=MONEY)
    put(ws, f"{x}{IS['ebit']}", f"={x}{IS['gp']}-{x}{IS['opex']}-{x}{IS['dep']}",
        fmt=MONEY, bold=True)
    put(ws, f"{x}{IS['int']}", f"={S}!{x}{SUP['int']}", color=GREEN, fmt=MONEY)
    put(ws, f"{x}{IS['ebt']}", f"={x}{IS['ebit']}-{x}{IS['int']}", fmt=MONEY, bold=True)
    put(ws, f"{x}{IS['tax']}", f"=MAX({x}{IS['ebt']},0)*{A}!$C${AS['tax']}", fmt=MONEY)
    put(ws, f"{x}{IS['ni']}", f"={x}{IS['ebt']}-{x}{IS['tax']}", fmt=MONEY, bold=True, fill=CHECKF)
sec(ws, IS["sec"], "补充指标")
for r, label in [(IS["growth"], "收入同比增长率"), (IS["arpu"], "ARPU（收入/客户数，元）"),
                 (IS["gm"], "毛利率"), (IS["nm"], "净利率")]:
    put(ws, f"A{r}", label, align="left", color=GREYT, size=9)
put(ws, f"B{IS['growth']}", "—", align="center", color=GREYT)
for i, x in enumerate(FC):
    p = COLS[i]
    put(ws, f"{x}{IS['growth']}", f"={x}{IS['rev']}/{p}{IS['rev']}-1", fmt=PCT0,
        color=GREYT, size=9)
    put(ws, f"{x}{IS['arpu']}", f"={x}{IS['rev']}/{x}{IS['cust']}", fmt=NUM,
        color=GREYT, size=9)
for x in COLS:
    put(ws, f"{x}{IS['gm']}", f"={x}{IS['gp']}/{x}{IS['rev']}", fmt=PCT1,
        color=GREYT, size=9)
    put(ws, f"{x}{IS['nm']}", f"={x}{IS['ni']}/{x}{IS['rev']}", fmt=PCT1,
        color=GREYT, size=9)
ws.freeze_panes = "B4"
page(ws)

# ============================================================ 资产负债表
ws = ws_bs
ws.sheet_properties.tabColor = MID
ws.column_dimensions["A"].width = 36
for col in COLS:
    ws.column_dimensions[col].width = 13
title_bar(ws, 1, "星链数科 — 资产负债表（Balance Sheet）", "G",
          "单位：元 | 勾稽关系：总资产 = 总负债 + 总权益；现金与留存收益逐年滚动；有息负债与「支持排程」一致")
year_header(ws, 3)
sec(ws, 4, "资产")
sec(ws, 9, "负债")
sec(ws, 13, "权益")
sec(ws, 19, "勾稽校验（应始终显示“平衡”）")
for r, label, bold in [
    (5, "现金", False), (6, "应收账款", False),
    (7, "固定资产净值（支持排程）", False), (8, "总资产", True),
    (BS["ap"], "应付账款", False), (BS["debt"], "有息负债（支持排程）", False),
    (BS["tl"], "总负债", True),
    (BS["eq"], "股本", False), (BS["re"], "留存收益", False),
    (BS["te"], "总权益", True), (BS["tle"], "负债和权益总计", True),
    (BS["lev"], "资产负债率", False),
]:
    put(ws, f"A{r}", label, bold=bold, align="left", fill=CHECKF if bold else None,
        color=GREYT if r == BS["lev"] else BLACK, size=9 if r == BS["lev"] else 10)
for coord, v in [("B5", 7000000), ("B6", 100000), ("B10", 50000),
                 (f"B{BS['eq']}", 3000000), (f"B{BS['re']}", 4000000)]:
    put(ws, coord, v, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, "B7", f"={S}!B{SUP['nend']}", color=GREEN, fmt=MONEY)
put(ws, "B8", "=SUM(B5:B7)", fmt=MONEY, bold=True, fill=CHECKF)
put(ws, f"B{BS['debt']}", f"={S}!B{SUP['end']}", color=GREEN, fmt=MONEY)
put(ws, f"B{BS['tl']}", f"=B{BS['ap']}+B{BS['debt']}", fmt=MONEY, bold=True, fill=CHECKF)
put(ws, f"B{BS['te']}", f"=B{BS['eq']}+B{BS['re']}", fmt=MONEY, bold=True, fill=CHECKF)
put(ws, f"B{BS['tle']}", f"=B{BS['tl']}+B{BS['te']}", fmt=MONEY, bold=True, fill=CHECKF)
put(ws, f"B{BS['lev']}", f"=B{BS['tl']}/B8", fmt=PCT1, color=GREYT, size=9)
for i, x in enumerate(FC):
    p = COLS[i]
    put(ws, f"{x}5", f"={p}5+现金流量表!{x}{CF['net']}", fmt=MONEY)
    put(ws, f"{x}6", f"=利润表!{x}{IS['rev']}*{A}!$C${AS['ar']}", fmt=MONEY)
    put(ws, f"{x}7", f"={S}!{x}{SUP['nend']}", color=GREEN, fmt=MONEY)
    put(ws, f"{x}8", f"=SUM({x}5:{x}7)", fmt=MONEY, bold=True, fill=CHECKF)
    put(ws, f"{x}{BS['ap']}", f"=利润表!{x}{IS['rev']}*{A}!$C${AS['ap']}", fmt=MONEY)
    put(ws, f"{x}{BS['debt']}", f"={S}!{x}{SUP['end']}", color=GREEN, fmt=MONEY)
    put(ws, f"{x}{BS['tl']}", f"={x}{BS['ap']}+{x}{BS['debt']}", fmt=MONEY, bold=True, fill=CHECKF)
    put(ws, f"{x}{BS['eq']}", f"={p}{BS['eq']}", fmt=MONEY)
    put(ws, f"{x}{BS['re']}", f"={p}{BS['re']}+利润表!{x}{IS['ni']}", fmt=MONEY)
    put(ws, f"{x}{BS['te']}", f"={x}{BS['eq']}+{x}{BS['re']}", fmt=MONEY, bold=True, fill=CHECKF)
    put(ws, f"{x}{BS['tle']}", f"={x}{BS['tl']}+{x}{BS['te']}", fmt=MONEY, bold=True, fill=CHECKF)
    put(ws, f"{x}{BS['lev']}", f"={x}{BS['tl']}/{x}8", fmt=PCT1, color=GREYT, size=9)
put(ws, f"A{BS['diff1']}", "① 总资产 −（总负债 + 总权益）", align="left", size=9, color=GREYT)
put(ws, f"A{BS['res1']}", "① 校验结果", align="left", size=9, color=GREYT)
put(ws, f"A{BS['diff2']}", "② 本表现金 − 现金流量表期末现金", align="left", size=9, color=GREYT)
put(ws, f"A{BS['res2']}", "② 校验结果", align="left", size=9, color=GREYT)
for x in COLS:
    put(ws, f"{x}{BS['diff1']}", f"={x}8-{x}{BS['tle']}", fmt=DIFF, size=9)
    put(ws, f"{x}{BS['res1']}", f'=IF(ABS({x}{BS["diff1"]})<0.01,"平衡","不平衡")',
        bold=True, fill=CHECKF, align="center")
    put(ws, f"{x}{BS['diff2']}", f"={x}5-现金流量表!{x}{CF['end']}", fmt=DIFF, size=9)
    put(ws, f"{x}{BS['res2']}", f'=IF(ABS({x}{BS["diff2"]})<0.01,"平衡","不平衡")',
        bold=True, fill=CHECKF, align="center")
ws.freeze_panes = "B4"
page(ws)

# ============================================================ 现金流量表
ws = ws_cf
ws.sheet_properties.tabColor = MID
ws.column_dimensions["A"].width = 36
for col in COLS:
    ws.column_dimensions[col].width = 13
title_bar(ws, 1, "星链数科 — 现金流量表（Cash Flow Statement）", "G",
          "单位：元 | 间接法 | 利息当年全额付现：经营活动加回利息费用，筹资活动列示偿付利息；期末现金 = 期初现金 + 净现金流")
year_header(ws, 3)
sec(ws, 4, "一、经营活动")
sec(ws, 10, "二、投资活动")
sec(ws, 13, "三、融资活动")
for r, label, bold in [
    (CF["ni"], "净利润", False),
    (CF["dep"], "加：折旧（非现金费用）", False),
    (CF["int"], "加：利息费用（付现列入筹资活动）", False),
    (CF["wc"], "营运资本变动（增加 = 现金占用）", False),
    (CF["cfo"], "经营活动现金流净额", True),
    (CF["capex"], "资本支出", False),
    (CF["cfi"], "投资活动现金流净额", True),
    (CF["borrow"], "新增借款收到的现金", False),
    (CF["repay"], "偿还债务支付的现金", False),
    (CF["intpaid"], "偿付利息支付的现金", False),
    (CF["cff"], "融资活动现金流净额", True),
    (CF["net"], "现金及现金等价物净增加额", True),
    (CF["beg"], "期初现金", False),
    (CF["end"], "期末现金", True),
    (CF["fcf"], "补充：自由现金流（经营+投资）", False),
    (CF["safe"], "现金安全线", False),
    (CF["flag"], "低于安全线标记（1 = 是）", "0"),
]:
    put(ws, f"A{r}", label, bold=bold, align="left", fill=CHECKF if bold else None,
        color=GREYT if r in (CF["fcf"], CF["safe"], CF["flag"]) else BLACK,
        size=9 if r in (CF["fcf"], CF["safe"], CF["flag"]) else 10)

put(ws, f"B{CF['ni']}", f"=利润表!B{IS['ni']}", color=GREEN, fmt=MONEY)
put(ws, f"B{CF['dep']}", f"=利润表!B{IS['dep']}", color=GREEN, fmt=MONEY)
put(ws, f"B{CF['int']}", f"={S}!B{SUP['int']}", color=GREEN, fmt=MONEY)
put(ws, f"B{CF['wc']}", 0, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, f"B{CF['cfo']}", f"=B{CF['ni']}+B{CF['dep']}+B{CF['int']}-B{CF['wc']}",
    fmt=MONEY, bold=True, fill=CHECKF)
put(ws, f"B{CF['capex']}", -100000, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, f"B{CF['cfi']}", f"=B{CF['capex']}", fmt=MONEY, bold=True, fill=CHECKF)
put(ws, f"B{CF['borrow']}", 2000000, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, f"B{CF['repay']}", 0, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, f"B{CF['intpaid']}", f"=-{S}!B{SUP['int']}", color=GREEN, fmt=MONEY)
put(ws, f"B{CF['cff']}", f"=SUM(B{CF['borrow']}:B{CF['intpaid']})",
    fmt=MONEY, bold=True, fill=CHECKF)
put(ws, f"B{CF['net']}", f"=B{CF['cfo']}+B{CF['cfi']}+B{CF['cff']}",
    fmt=MONEY, bold=True, fill=CHECKF)
put(ws, f"B{CF['beg']}", 4808750, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, f"B{CF['end']}", f"=B{CF['beg']}+B{CF['net']}", fmt=MONEY, bold=True, fill=CHECKF)
put(ws, f"B{CF['fcf']}", f"=B{CF['cfo']}+B{CF['cfi']}", fmt=MONEY, color=GREYT, size=9)
put(ws, f"B{CF['safe']}", f"={A}!$C${AS['safe']}", fmt=MONEY, color=GREYT, size=9)
put(ws, f"B{CF['flag']}", f"=IF(B{CF['end']}<B{CF['safe']},1,0)", align="center",
    color=GREYT, size=9)

for i, x in enumerate(FC):
    p = COLS[i]
    put(ws, f"{x}{CF['ni']}", f"=利润表!{x}{IS['ni']}", color=GREEN, fmt=MONEY)
    put(ws, f"{x}{CF['dep']}", f"=利润表!{x}{IS['dep']}", color=GREEN, fmt=MONEY)
    put(ws, f"{x}{CF['int']}", f"={S}!{x}{SUP['int']}", color=GREEN, fmt=MONEY)
    put(ws, f"{x}{CF['wc']}",
        f"=(资产负债表!{x}6-资产负债表!{p}6)-(资产负债表!{x}{BS['ap']}-资产负债表!{p}{BS['ap']})",
        fmt=MONEY)
    put(ws, f"{x}{CF['cfo']}", f"={x}{CF['ni']}+{x}{CF['dep']}+{x}{CF['int']}-{x}{CF['wc']}",
        fmt=MONEY, bold=True, fill=CHECKF)
    put(ws, f"{x}{CF['capex']}", f"=-{A}!$C${AS['capex']}", fmt=MONEY)
    put(ws, f"{x}{CF['cfi']}", f"={x}{CF['capex']}", fmt=MONEY, bold=True, fill=CHECKF)
    put(ws, f"{x}{CF['borrow']}", f"={S}!{x}{SUP['new']}", color=GREEN, fmt=MONEY)
    put(ws, f"{x}{CF['repay']}", f"=-{S}!{x}{SUP['repay']}", color=GREEN, fmt=MONEY)
    put(ws, f"{x}{CF['intpaid']}", f"=-{S}!{x}{SUP['int']}", color=GREEN, fmt=MONEY)
    put(ws, f"{x}{CF['cff']}", f"=SUM({x}{CF['borrow']}:{x}{CF['intpaid']})",
        fmt=MONEY, bold=True, fill=CHECKF)
    put(ws, f"{x}{CF['net']}", f"={x}{CF['cfo']}+{x}{CF['cfi']}+{x}{CF['cff']}",
        fmt=MONEY, bold=True, fill=CHECKF)
    put(ws, f"{x}{CF['beg']}", f"=资产负债表!{p}5", color=GREEN, fmt=MONEY)
    put(ws, f"{x}{CF['end']}", f"={x}{CF['beg']}+{x}{CF['net']}", fmt=MONEY, bold=True, fill=CHECKF)
    put(ws, f"{x}{CF['fcf']}", f"={x}{CF['cfo']}+{x}{CF['cfi']}", fmt=MONEY, color=GREYT, size=9)
    put(ws, f"{x}{CF['safe']}", f"={A}!$C${AS['safe']}", fmt=MONEY, color=GREYT, size=9)
    put(ws, f"{x}{CF['flag']}", f"=IF({x}{CF['end']}<{x}{CF['safe']},1,0)", align="center",
        color=GREYT, size=9)
put(ws, f"A{CF['note']}",
    "注：B7/B8/B14/B15/B19 为基年实际数（蓝色）；2025A 利息按期初（0）与期末（200 万）负债的平均余额计提，"
    "融资活动含当年新增借款 200 万元——净利润、筹资现金流与资产负债表现金完整勾稽。"
    "营运资本变动 = Δ应收 − Δ应付，正数表示现金被占用（间接法中为减项）。",
    color=GREYT, size=9, border=False)
ws.freeze_panes = "B4"
page(ws)

# ============================================================ 支持排程（债务 + 固定资产）
ws = ws_sc
ws.sheet_properties.tabColor = "8EAADB"
ws.column_dimensions["A"].width = 36
for col in COLS:
    ws.column_dimensions[col].width = 13
title_bar(ws, 1, "星链数科 — 支持排程（债务排程 + 固定资产排程）", "G",
          "单位：元 | 债务：期末 = 期初 + 新增 − 偿还；利息 = 平均余额 × 利率（假设 A-11） | 固定资产：折旧按期初净值计提，以期初净值为上限")
year_header(ws, 3)
sec(ws, 4, "一、债务排程（有息负债 · 蓝色为融资计划输入）")
for r, label in [(SUP["beg"], "期初有息负债"), (SUP["new"], "新增借款（输入）"),
                 (SUP["repay"], "偿还本金（输入）"), (SUP["end"], "期末有息负债"),
                 (SUP["avg"], "平均有息负债"), (SUP["int"], "利息费用（平均余额×年利率）"),
                 (SUP["negchk"], "负债余额非负校验")]:
    put(ws, f"A{r}", label, bold=(r in (SUP["end"], SUP["int"])), align="left",
        fill=CHECKF if r in (SUP["end"], SUP["int"]) else None,
        color=GREYT if r == SUP["negchk"] else BLACK,
        size=9 if r == SUP["negchk"] else 10)
# 基年实际：期初 0，年内新增 200 万，期末 200 万
put(ws, f"B{SUP['beg']}", 0, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, f"B{SUP['new']}", 2000000, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, f"B{SUP['repay']}", 0, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, f"B{SUP['end']}", f"=B{SUP['beg']}+B{SUP['new']}-B{SUP['repay']}",
    fmt=MONEY, bold=True, fill=CHECKF)
put(ws, f"B{SUP['avg']}", f"=(B{SUP['beg']}+B{SUP['end']})/2", fmt=MONEY)
put(ws, f"B{SUP['int']}", f"=B{SUP['avg']}*{A}!$C${AS['rate']}", fmt=MONEY, bold=True, fill=CHECKF)
put(ws, f"B{SUP['negchk']}", f'=IF(B{SUP["end"]}<-0.01,"✗","✓")', align="center",
    color=GREYT, size=9)
# 融资计划（输入）：新增 300 万、偿还 450 万 → 2030E 末保留 50 万
BORROW = [1500000, 1000000, 500000, 0, 0]
REPAY = [0, 500000, 1000000, 1500000, 1500000]
for i, x in enumerate(FC):
    p = COLS[i]
    put(ws, f"{x}{SUP['beg']}", f"={p}{SUP['end']}", fmt=MONEY)
    put(ws, f"{x}{SUP['new']}", BORROW[i], color=BLUE, fill=GREY, fmt=MONEY)
    put(ws, f"{x}{SUP['repay']}", REPAY[i], color=BLUE, fill=GREY, fmt=MONEY)
    put(ws, f"{x}{SUP['end']}", f"={x}{SUP['beg']}+{x}{SUP['new']}-{x}{SUP['repay']}",
        fmt=MONEY, bold=True, fill=CHECKF)
    put(ws, f"{x}{SUP['avg']}", f"=({x}{SUP['beg']}+{x}{SUP['end']})/2", fmt=MONEY)
    put(ws, f"{x}{SUP['int']}", f"={x}{SUP['avg']}*{A}!$C${AS['rate']}",
        fmt=MONEY, bold=True, fill=CHECKF)
    put(ws, f"{x}{SUP['negchk']}", f'=IF({x}{SUP["end"]}<-0.01,"✗","✓")', align="center",
        color=GREYT, size=9)
dv_plan = DataValidation(type="decimal", operator="between", formula1="0", formula2="10000000",
                         allow_blank=False, errorTitle="输入无效",
                         error="请输入 0–10,000,000 元范围内的金额",
                         promptTitle="融资计划", prompt="当年新增借款 / 偿还本金金额（元）")
dv_plan.showErrorMessage = True
dv_plan.showInputMessage = True
ws.add_data_validation(dv_plan)
dv_plan.add(f"C{SUP['new']}:G{SUP['repay']}")

sec(ws, SUP["sec2"], "二、偿债能力与回报指标（自动计算）")
for r, label in [(SUP["lev"], "资产负债率（含负债）"), (SUP["de"], "有息负债 / 总权益"),
                 (SUP["cov"], "利息保障倍数（EBIT / 利息费用）"),
                 (SUP["roic"], "ROIC（EBIT×(1−税率) / 投入资本）")]:
    put(ws, f"A{r}", label, align="left", color=GREYT, size=9)
for x in COLS:
    put(ws, f"{x}{SUP['lev']}", f"=资产负债表!{x}{BS['tl']}/资产负债表!{x}8",
        fmt=PCT1, color=GREYT, size=9)
    put(ws, f"{x}{SUP['de']}", f"={x}{SUP['end']}/资产负债表!{x}{BS['te']}",
        fmt=PCT1, color=GREYT, size=9)
    put(ws, f"{x}{SUP['cov']}", f'=IF({x}{SUP["int"]}>0.001,利润表!{x}{IS["ebit"]}/{x}{SUP["int"]},"n.a.")',
        fmt="0.0", color=GREYT, size=9, align="center")
    put(ws, f"{x}{SUP['roic']}",
        f"=利润表!{x}{IS['ebit']}*(1-{A}!$C${AS['tax']})"
        f"/({x}{SUP['end']}+资产负债表!{x}{BS['te']}-资产负债表!{x}5)",
        fmt=PCT1, color=GREYT, size=9)

sec(ws, SUP["sec3"], "三、固定资产排程（折旧按净值计提，以期初净值为上限，不会折成负值）")
for r, label in [(SUP["gbeg"], "期初固定资产原值"), (SUP["capex"], "加：本年资本支出"),
                 (SUP["gend"], "期末固定资产原值"), (SUP["nbeg"], "期初固定资产净值"),
                 (SUP["dep"], "本年折旧（=MIN(期初净值×折旧率, 期初净值)）"),
                 (SUP["nend"], "期末固定资产净值"), (SUP["accdep"], "累计折旧（=期末原值−期末净值）")]:
    put(ws, f"A{r}", label, align="left",
        color=GREYT if r == SUP["accdep"] else BLACK,
        size=9 if r == SUP["accdep"] else 10)
put(ws, f"B{SUP['gbeg']}", 2500000, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, f"B{SUP['capex']}", 100000, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, f"B{SUP['gend']}", f"=B{SUP['gbeg']}+B{SUP['capex']}", fmt=MONEY)
put(ws, f"B{SUP['nbeg']}", 1950000, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, f"B{SUP['dep']}", 100000, color=BLUE, fill=GREY, fmt=MONEY)
put(ws, f"B{SUP['nend']}", f"=B{SUP['nbeg']}+B{SUP['capex']}-B{SUP['dep']}", fmt=MONEY)
put(ws, f"B{SUP['accdep']}", f"=B{SUP['gend']}-B{SUP['nend']}", fmt=MONEY,
    color=GREYT, size=9)
for i, x in enumerate(FC):
    p = COLS[i]
    put(ws, f"{x}{SUP['gbeg']}", f"={p}{SUP['gend']}", fmt=MONEY)
    put(ws, f"{x}{SUP['capex']}", f"={A}!$C${AS['capex']}", fmt=MONEY)
    put(ws, f"{x}{SUP['gend']}", f"={x}{SUP['gbeg']}+{x}{SUP['capex']}", fmt=MONEY)
    put(ws, f"{x}{SUP['nbeg']}", f"={p}{SUP['nend']}", fmt=MONEY)
    put(ws, f"{x}{SUP['dep']}", f"=MIN({x}{SUP['nbeg']}*{A}!$C${AS['deprate']},{x}{SUP['nbeg']})",
        fmt=MONEY)
    put(ws, f"{x}{SUP['nend']}", f"={x}{SUP['nbeg']}+{x}{SUP['capex']}-{x}{SUP['dep']}", fmt=MONEY)
    put(ws, f"{x}{SUP['accdep']}", f"={x}{SUP['gend']}-{x}{SUP['nend']}", fmt=MONEY,
        color=GREYT, size=9)

sup_notes = [
    "注1：利息 = 平均有息负债 × 年利率（「假设」页 A-11）——新增借款自放入年起即按平均余额生息；平均余额法下当年新增借款按半年计息（偏乐观），如需更保守可将平均余额改为期末余额；利息全额付现，无应付利息挂账。",
    "注2：利息付现列入筹资活动“偿付利息支付的现金”，同时在经营活动加回利息费用，两者对消；净利润已含利息税盾 → 不存在“利息←负债←现金”循环引用。",
    "注3：固定资产折旧按期初净值 × 折旧率（A-12）计提，并以期初净值为上限（MIN），期末净值不会为负；资本支出同时计入原值与净值。",
    "注4：2026E–2030E 融资计划（蓝色输入）：新增借款合计 300 万、偿还合计 450 万，2030E 末保留 50 万借款余额；改蓝色单元格，利息/偿债指标/三表同步联动。",
    "注5：投入资本 = 有息负债 + 总权益 − 现金；ROIC 与 DCF 互为补充——DCF 回答“公司值多少钱”，ROIC 回答“每一块投入资本赚回多少”，两者合看才是完整的资本配置视角。",
]
for i, t in enumerate(sup_notes):
    r = SUP["note"] + i
    ws.merge_cells(f"A{r}:G{r}")
    put(ws, f"A{r}", t, color=GREYT, size=9, border=False, align="left")
ws.freeze_panes = "B4"
page(ws)

# ============================================================ 图表
ws = ws_ch
ws.sheet_properties.tabColor = "8EAADB"
for col in ["A", "B", "C", "D", "E", "F", "G"]:
    ws.column_dimensions[col].width = 13
title_bar(ws, 1, "星链数科 — 图表（随「假设」页情景自动更新）", "G",
          "图1：收入与净利润｜图2：经营现金流与期末现金｜图3：现金跑道（期末现金 vs 安全线）｜图4：有息负债余额与利息费用")


def add_combo(anchor, title, y_title, src, bar_row, line_row, y2_title, bar_color="8EAADB"):
    b = BarChart()
    b.type = "col"
    b.title = title
    b.y_axis.title = y_title
    b.y_axis.delete = False
    b.x_axis.delete = False
    b.add_data(Reference(src, min_col=1, max_col=7, min_row=bar_row, max_row=bar_row),
               titles_from_data=True, from_rows=True)
    b.set_categories(Reference(src, min_col=2, max_col=7, min_row=3, max_row=3))
    b.series[0].graphicalProperties.solidFill = bar_color
    l = LineChart()
    l.add_data(Reference(src, min_col=1, max_col=7, min_row=line_row, max_row=line_row),
               titles_from_data=True, from_rows=True)
    l.series[0].graphicalProperties.line.solidFill = DARK
    l.series[0].graphicalProperties.line.width = 22000
    l.series[0].marker = Marker(symbol="circle", size=6)
    l.series[0].smooth = False
    l.y_axis.axId = 200
    l.y_axis.title = y2_title
    l.y_axis.delete = False
    l.y_axis.majorGridlines = None
    b.y_axis.crosses = "max"
    b += l
    b.height, b.width = 8, 20
    ws.add_chart(b, anchor)


add_combo("A4", "图1　营业收入与净利润（2025A–2030E）", "营业收入（元）",
         ws_is, IS["rev"], IS["ni"], "净利润（元）")
add_combo("A23", "图2　经营现金流与期末现金（2025A–2030E）", "经营现金流（元）",
         ws_cf, CF["cfo"], CF["end"], "期末现金（元）")
add_combo("A63", "图4　有息负债余额与利息费用（2025A–2030E）", "期末有息负债（元）",
         ws_sc, SUP["end"], SUP["int"], "利息费用（元）", bar_color="2E75B6")

# 图3：现金跑道（同轴：期末现金 + 安全线）
l3 = LineChart()
l3.title = "图3　现金跑道：期末现金 vs 安全线（2025A–2030E）"
l3.y_axis.title = "现金（元）"
l3.y_axis.delete = False
l3.x_axis.delete = False
l3.add_data(Reference(ws_cf, min_col=1, max_col=7, min_row=CF["end"], max_row=CF["end"]),
           titles_from_data=True, from_rows=True)
l3.add_data(Reference(ws_cf, min_col=1, max_col=7, min_row=CF["safe"], max_row=CF["safe"]),
           titles_from_data=True, from_rows=True)
l3.set_categories(Reference(ws_cf, min_col=2, max_col=7, min_row=3, max_row=3))
l3.series[0].graphicalProperties.line.solidFill = DARK
l3.series[0].graphicalProperties.line.width = 24000
l3.series[0].marker = Marker(symbol="circle", size=6)
l3.series[0].smooth = False
l3.series[1].graphicalProperties.line.solidFill = "C00000"
l3.series[1].graphicalProperties.line.width = 18000
l3.series[1].smooth = False
l3.height, l3.width = 8, 20
ws.add_chart(l3, "A42")
ws.row_breaks.append(Break(id=21))
ws.row_breaks.append(Break(id=40))
ws.row_breaks.append(Break(id=61))
put(ws, "A82", "注：图3 中红线 = 现金安全线（「假设」页 A-10）；若期末现金折线跌破红线，说明需提前规划融资。图4 展示债务排程：借款高峰后逐年偿还，利息费用随平均余额同步回落。",
    color=GREYT, size=9, border=False)
page(ws, wide=True)

# ============================================================ 敏感性分析
ws = ws_sn
ws.sheet_properties.tabColor = MID
ws.column_dimensions["A"].width = 36
for col in ["B", "C", "D", "E", "F", "G"]:
    ws.column_dimensions[col].width = 15
title_bar(ws, 1, "星链数科 — 估值与敏感性分析", "G",
          "单位：元 | 估值使用假设面板折现率；无杠杆自由现金流口径；敏感性为解析解，并与模型实时勾稽校验")
sec(ws, 4, "一、简化 DCF 估值（无杠杆自由现金流）")
put(ws, f"A{SN['hdr']}", "项目", bold=True, fill=LIGHT, align="left")
for col, y in zip(COLS, YEARS):
    put(ws, f"{col}{SN['hdr']}", y, bold=True, fill=LIGHT, align="center")
put(ws, f"A{SN['fcf']}", "自由现金流（经营+投资−利息税盾）", align="left")
put(ws, f"A{SN['df']}", "折现因子", align="left")
put(ws, f"A{SN['pv']}", "现金流现值", align="left")
for i, x in enumerate(FC):
    t = i + 1
    put(ws, f"{x}{SN['fcf']}",
        f"=现金流量表!{x}{CF['cfo']}+现金流量表!{x}{CF['cfi']}"
        f"-{S}!{x}{SUP['int']}*{A}!$C${AS['tax']}", fmt=MONEY)
    put(ws, f"{x}{SN['df']}", f"=1/(1+{A}!$C${AS['disc']})^{t}", fmt="0.000")
    put(ws, f"{x}{SN['pv']}", f"={x}{SN['fcf']}*{x}{SN['df']}", fmt=MONEY)
for r in (SN["fcf"], SN["df"], SN["pv"]):
    put(ws, f"B{r}", "—", align="center", color=GREYT)
for r, label, f in [
    (SN["sumpv"], "预测期现值合计（2026E–2030E）", f"=SUM(C{SN['pv']}:G{SN['pv']})"),
    (SN["tv"], "终值（永续增长法，g = 收入增长率）",
     f'=IF({A}!$C${AS["disc"]}<={A}!$C${AS["g"]},"n.a.（折现率≤增长率）",'
     f'G{SN["fcf"]}*(1+{A}!$C${AS["g"]})/({A}!$C${AS["disc"]}-{A}!$C${AS["g"]}))'),
    (SN["tpv"], "终值现值", f'=IF(ISNUMBER($C${SN["tv"]}),$G${SN["df"]}*$C${SN["tv"]},0)'),
    (SN["ev"], "企业价值（经营价值）", f"=$C${SN['sumpv']}+$C${SN['tpv']}"),
    (SN["netcash"], "加：基年净现金（现金 − 有息负债）",
     f"=资产负债表!$B$5-{S}!$B${SUP['end']}"),
    (SN["eq"], "股权价值（简化）", f"=$C${SN['ev']}+$C${SN['netcash']}"),
]:
    put(ws, f"A{r}", label, align="left", bold=(r in (SN["ev"], SN["eq"])),
        fill=CHECKF if r == SN["eq"] else None)
    put(ws, f"C{r}", f, fmt="0.0%" if r == SN["tv"] else MONEY,
        bold=(r in (SN["ev"], SN["eq"])), fill=CHECKF if r == SN["eq"] else None)
put(ws, f"A{SN['note']}",
    "注：FCF 剔除利息税盾后为无杠杆口径（经营 + 投资 − 利息费用×税率）；"
    "终值假设 5 年后永续增长率 = 当前收入增长率（Base 5%）——对成熟期公司建议将终值增长率下调至 2%–3%，本模型为简化处理；"
    "2025A 末有息负债 200 万元，股权价值 = 企业价值 + 基年现金 − 有息负债。估值仅供参考。",
    color=GREYT, size=9, border=False)

sec(ws, SN["sec2"], "二、敏感性分析①：5 年累计净利润（2026E–2030E，元）")
put(ws, f"A{SN['s2note']}", "行 = 收入增长率，列 = 毛利率；蓝色行列头带数据验证，可修改后自动重算。",
    color=GREYT, size=9, border=False)
put(ws, f"A{SN['s2hdr']}", "增长率＼毛利率", bold=True, fill=LIGHT, align="center")
MARGINS = [0.50, 0.55, 0.60, 0.65, 0.70]
GROWTHS = [0.03, 0.05, 0.08, 0.10, 0.15]
for j, m in enumerate(MARGINS):
    put(ws, f"{chr(66+j)}{SN['s2hdr']}", m, bold=True, fill=GREY, color=BLUE, fmt=PCT0, align="center")
for i, g in enumerate(GROWTHS):
    r = SN["s2r0"] + i
    put(ws, f"A{r}", g, bold=True, fill=GREY, color=BLUE, fmt=PCT0, align="center")
    for j in range(5):
        cl = chr(66 + j)
        f = (f"=(1-{A}!$C${AS['tax']})*(({cl}${SN['s2hdr']}*利润表!$B${IS['rev']}"
             f"-{A}!$C${AS['cac']}*{A}!$C${AS['cust']})"
             f"*IF($A{r}=0,5,(1+$A{r})*((1+$A{r})^5-1)/$A{r})"
             f"-SUM({S}!$C${SUP['dep']}:$G${SUP['dep']})"
             f"-SUM({S}!$C${SUP['int']}:$G${SUP['int']}))")
        put(ws, f"{cl}{r}", f, fmt=MONEY)
put(ws, f"A{SN['s2chk']}", "勾稽校验（当前情景）", align="left", size=9, color=GREYT)
ws.merge_cells(f"B{SN['s2chk']}:G{SN['s2chk']}")
put(ws, f"B{SN['s2chk']}",
    f'=IF(IFERROR(ABS(INDEX($B${SN["s2r0"]}:$F${SN["s2r0"]+4},MATCH({A}!$C${AS["g"]},$A${SN["s2r0"]}:$A${SN["s2r0"]+4},0),'
    f'MATCH({A}!$C${AS["m"]},$B${SN["s2hdr"]}:$F${SN["s2hdr"]},0))-SUM(利润表!$C${IS["ni"]}:$G${IS["ni"]})),1)<1,'
    f'"✓ 与利润表 5 年净利润合计勾稽一致","✗ 与模型不一致（或当前情景不在表中）")',
    bold=True, fill=CHECKF, align="left")
put(ws, f"A{SN['s2note2']}",
    "注：解析解假设各年税前利润为正；5 年折旧与 5 年利息直接取自「支持排程」当期计划（与增长率、毛利率无关）。"
    "本表隐含 CapEx 与融资计划不随增长率变化（折旧、利息为固定值）、ARPU 稳定（客户数增速 = 收入增速）；"
    "若高增长需要额外 CapEx / 融资，实际利润增幅会低于本表。",
    color=GREYT, size=9, border=False)

sec(ws, SN["sec3"], "三、敏感性分析②：2030E 期末现金（元）")
put(ws, f"A{SN['s3note']}", "行 = 收入增长率；蓝色行头带数据验证，可修改后自动重算。",
    color=GREYT, size=9, border=False)
put(ws, f"A{SN['s3hdr']}", "收入增长率", bold=True, fill=LIGHT, align="center")
put(ws, f"B{SN['s3hdr']}", "2030E 期末现金", bold=True, fill=LIGHT, align="center")
for i, g in enumerate(GROWTHS):
    r = SN["s3r0"] + i
    put(ws, f"A{r}", g, bold=True, fill=GREY, color=BLUE, fmt=PCT0, align="center")
    f = (f"=资产负债表!$B$5+(1-{A}!$C${AS['tax']})*(({A}!$C${AS['m']}*利润表!$B${IS['rev']}"
         f"-{A}!$C${AS['cac']}*{A}!$C${AS['cust']})"
         f"*IF($A{r}=0,5,(1+$A{r})*((1+$A{r})^5-1)/$A{r})"
         f"-SUM({S}!$C${SUP['dep']}:$G${SUP['dep']})"
         f"-SUM({S}!$C${SUP['int']}:$G${SUP['int']}))"
         f"+SUM({S}!$C${SUP['dep']}:$G${SUP['dep']})"
         f"-({A}!$C${AS['ar']}-{A}!$C${AS['ap']})"
         f"*利润表!$B${IS['rev']}*(1+$A{r})^5+(资产负债表!$B$6-资产负债表!$B$10)"
         f"-SUM({S}!$C${SUP['capex']}:$G${SUP['capex']})"
         f"+SUM({S}!$C${SUP['new']}:$G${SUP['new']})"
         f"-SUM({S}!$C${SUP['repay']}:$G${SUP['repay']})")
    put(ws, f"B{r}", f, fmt=MONEY)
put(ws, f"A{SN['s3chk']}", "勾稽校验（当前情景）", align="left", size=9, color=GREYT)
ws.merge_cells(f"B{SN['s3chk']}:G{SN['s3chk']}")
put(ws, f"B{SN['s3chk']}",
    f'=IF(IFERROR(ABS(INDEX($B${SN["s3r0"]}:$B${SN["s3r0"]+4},'
    f'MATCH({A}!$C${AS["g"]},$A${SN["s3r0"]}:$A${SN["s3r0"]+4},0))'
    f'-资产负债表!$G$5),1)<1,"✓ 与资产负债表 2030E 现金勾稽一致",'
    f'"✗ 与模型不一致（或当前情景不在表中）")',
    bold=True, fill=CHECKF, align="left")
put(ws, f"A{SN['s3note2']}",
    "注：期末现金 = 基年现金 + 5 年累计净利润 + 5 年折旧 − 营运资本累计变动 − 5 年资本支出"
    " + 5 年新增借款 − 5 年偿还本金（利息影响已含在净利润，经营加回与筹资付现对消）。",
    color=GREYT, size=9, border=False)

sec(ws, SN["sec4"], "四、边际敏感度：收入增长率每 ±1 个百分点的影响")
put(ws, f"A{SN['g1']}", "当前增长率 g", align="left", color=GREYT, size=9)
put(ws, f"C{SN['g1']}", f"={A}!$C${AS['g']}", fmt=PCT0, color=GREEN, align="center")
put(ws, f"A{SN['g2']}", "g + 1pp", align="left", color=GREYT, size=9)
put(ws, f"C{SN['g2']}", f"=C{SN['g1']}+0.01", fmt=PCT0, align="center")
put(ws, f"A{SN['cum1']}", "当前 g 的 5 年累计净利润（元）", align="left", size=9)
put(ws, f"C{SN['cum1']}",
    f"=(1-{A}!$C${AS['tax']})*(({A}!$C${AS['m']}*利润表!$B${IS['rev']}"
    f"-{A}!$C${AS['cac']}*{A}!$C${AS['cust']})"
    f"*IF($C${SN['g1']}=0,5,(1+$C${SN['g1']})*((1+$C${SN['g1']})^5-1)/$C${SN['g1']})"
    f"-SUM({S}!$C${SUP['dep']}:$G${SUP['dep']})"
    f"-SUM({S}!$C${SUP['int']}:$G${SUP['int']}))",
    fmt=MONEY)
put(ws, f"A{SN['cum2']}", "g + 1pp 的 5 年累计净利润（元）", align="left", size=9)
put(ws, f"C{SN['cum2']}",
    f"=(1-{A}!$C${AS['tax']})*(({A}!$C${AS['m']}*利润表!$B${IS['rev']}"
    f"-{A}!$C${AS['cac']}*{A}!$C${AS['cust']})"
    f"*IF($C${SN['g2']}=0,5,(1+$C${SN['g2']})*((1+$C${SN['g2']})^5-1)/$C${SN['g2']})"
    f"-SUM({S}!$C${SUP['dep']}:$G${SUP['dep']})"
    f"-SUM({S}!$C${SUP['int']}:$G${SUP['int']}))",
    fmt=MONEY)
put(ws, f"A{SN['marg']}", "边际影响（万元 / 每 1pp）", align="left", bold=True)
put(ws, f"C{SN['marg']}", f"=(C{SN['cum2']}-C{SN['cum1']})/10000", fmt="#,##0.0",
    bold=True, fill=CHECKF, align="center")
ws.merge_cells(f"A{SN['margnote']}:G{SN['margnote']}")
put(ws, f"A{SN['margnote']}",
    "注：边际影响为当前增长率附近的局部近似（5 年累计净利润对增长率为非线性、指数增长）；非线性效应见上方敏感性表。",
    color=GREYT, size=9, border=False)

sec(ws, SN["sec5"], "五、敏感性分析③：5 年累计利息费用（元）——利率 × 融资规模")
put(ws, f"A{SN['s5note']}",
    "行 = 借款年利率，列 = 融资计划规模倍数（1.0 = 当前计划）；利息 = 利率 × Σ平均余额，"
    "Σ平均余额 = 5 × 期初余额 + 规模 × Σ净融资×(5.5−年份序号)。",
    color=GREYT, size=9, border=False)
put(ws, f"A{SN['s5hdr']}", "利率＼规模倍数", bold=True, fill=LIGHT, align="center")
SCALES = [0.5, 0.75, 1.0, 1.25, 1.5]
RATES = [0.03, 0.04, 0.045, 0.055, 0.07]
for j, s in enumerate(SCALES):
    put(ws, f"{chr(66+j)}{SN['s5hdr']}", s, bold=True, fill=GREY, color=BLUE,
        fmt="0.00", align="center")
for i, rt in enumerate(RATES):
    r = SN["s5r0"] + i
    put(ws, f"A{r}", rt, bold=True, fill=GREY, color=BLUE, fmt=PCT1, align="center")
    for j in range(5):
        cl = chr(66 + j)
        f = (f"=$A{r}*(5*{S}!$B${SUP['end']}"
             f"+{cl}${SN['s5hdr']}*SUMPRODUCT({S}!$C${SUP['new']}:$G${SUP['new']}"
             f"-{S}!$C${SUP['repay']}:$G${SUP['repay']},{{4.5,3.5,2.5,1.5,0.5}}))")
        put(ws, f"{cl}{r}", f, fmt=MONEY)
put(ws, f"A{SN['s5chk']}", "勾稽校验（当前利率×当前规模）", align="left", size=9, color=GREYT)
ws.merge_cells(f"B{SN['s5chk']}:G{SN['s5chk']}")
put(ws, f"B{SN['s5chk']}",
    f'=IF(IFERROR(ABS(INDEX($B${SN["s5r0"]}:$F${SN["s5r0"]+4},'
    f'MATCH({A}!$C${AS["rate"]},$A${SN["s5r0"]}:$A${SN["s5r0"]+4},0),'
    f'MATCH(1,$B${SN["s5hdr"]}:$F${SN["s5hdr"]},0))'
    f'-SUM({S}!$C${SUP["int"]}:$G${SUP["int"]})),1)<1,'
    f'"✓ 与债务排程 5 年累计利息勾稽一致","✗ 与模型不一致（或当前利率/规模不在表中）")',
    bold=True, fill=CHECKF, align="left")
put(ws, f"A{SN['s5note2']}",
    "注：新增借款自放入年起按平均余额生息，累计利息对利率与融资规模均为线性；"
    "年份权重 {4.5,3.5,2.5,1.5,0.5} = 5.5−t——第 t 年净融资对 5 年平均余额的贡献系数 =（5−t）+0.5（当年计半年、次年起计全年）；"
    "改「支持排程」页蓝色融资计划后，本表与勾稽校验同步更新。",
    color=GREYT, size=9, border=False)
dv_sc = DataValidation(type="decimal", operator="between", formula1="0.1", formula2="3",
                       allow_blank=False, errorTitle="输入无效",
                       error="请输入 0.1–3 之间的倍数", promptTitle="规模倍数",
                       prompt="融资计划规模倍数")
dv_sc.showErrorMessage = True
dv_sc.showInputMessage = True
ws.add_data_validation(dv_sc)
dv_sc.add(f"B{SN['s5hdr']}:F{SN['s5hdr']}")
dv_rt = DataValidation(type="decimal", operator="between", formula1="0", formula2="0.15",
                       allow_blank=False, errorTitle="输入无效",
                       error="请输入 0%–15% 之间的利率", promptTitle="借款年利率",
                       prompt="有效范围：0%–15%")
dv_rt.showErrorMessage = True
dv_rt.showInputMessage = True
ws.add_data_validation(dv_rt)
dv_rt.add(f"A{SN['s5r0']}:A{SN['s5r0']+4}")

# ---- 六、三情景并排对比（公式驱动） ----
sec(ws, SN["sec6"], "六、三情景并排对比（公式驱动 · 随映射表与假设自动更新）")
put(ws, f"A{SN['s6note']}",
    "列头（蓝色）= 情景名（带下拉验证）；增长率 / 毛利率由 INDEX+MATCH 从「假设」页映射表抓取；"
    "净利润与期末现金为解析解，股权价值经下方计算区按无杠杆 DCF 汇总——三列并列，无需逐个切换。",
    color=GREYT, size=9, border=False)
put(ws, f"A{SN['s6hdr']}", "指标", bold=True, fill=LIGHT, align="left")
for col, nm in zip("BCD", ["Base", "Bull", "Bear"]):
    put(ws, f"{col}{SN['s6hdr']}", nm, bold=True, fill=GREY, color=BLUE, align="center")
dv_s6 = DataValidation(type="list", formula1='"Base,Bull,Bear"', allow_blank=False,
                       errorTitle="输入无效", error="请从下拉列表中选择：Base / Bull / Bear",
                       promptTitle="情景列头", prompt="该列的增长率/毛利率按此情景抓取")
dv_s6.showErrorMessage = True
dv_s6.showInputMessage = True
ws.add_data_validation(dv_s6)
dv_s6.add(f"B{SN['s6hdr']}:D{SN['s6hdr']}")
for col in "BCD":
    gc, mc = f"${col}${SN['s6g']}", f"${col}${SN['s6m']}"
    put(ws, f"{col}{SN['s6g']}",
        f"=INDEX({A}!$B${R_MAP_1}:$B${R_MAP_3},MATCH({col}${SN['s6hdr']},{A}!$A${R_MAP_1}:$A${R_MAP_3},0))",
        fmt=PCT0, align="center", color=GREYT, size=9)
    put(ws, f"{col}{SN['s6m']}",
        f"=INDEX({A}!$C${R_MAP_1}:$C${R_MAP_3},MATCH({col}${SN['s6hdr']},{A}!$A${R_MAP_1}:$A${R_MAP_3},0))",
        fmt=PCT1, align="center", color=GREYT, size=9)
    put(ws, f"{col}{SN['s6ni']}",
        f"=(1-{A}!$C${AS['tax']})*(({mc}*利润表!$B${IS['rev']}-{A}!$C${AS['cac']}*{A}!$C${AS['cust']})"
        f"*(1+{gc})^2-{S}!$D${SUP['dep']}-{S}!$D${SUP['int']})", fmt=MONEY)
    put(ws, f"{col}{SN['s6cash']}",
        f"=资产负债表!$B$5+(1-{A}!$C${AS['tax']})*(({mc}*利润表!$B${IS['rev']}"
        f"-{A}!$C${AS['cac']}*{A}!$C${AS['cust']})"
        f"*IF({gc}=0,5,(1+{gc})*((1+{gc})^5-1)/{gc})"
        f"-SUM({S}!$C${SUP['dep']}:$G${SUP['dep']})-SUM({S}!$C${SUP['int']}:$G${SUP['int']}))"
        f"+SUM({S}!$C${SUP['dep']}:$G${SUP['dep']})"
        f"-({A}!$C${AS['ar']}-{A}!$C${AS['ap']})*利润表!$B${IS['rev']}*(1+{gc})^5"
        f"+(资产负债表!$B$6-资产负债表!$B$10)"
        f"-SUM({S}!$C${SUP['capex']}:$G${SUP['capex']})"
        f"+SUM({S}!$C${SUP['new']}:$G${SUP['new']})-SUM({S}!$C${SUP['repay']}:$G${SUP['repay']})",
        fmt=MONEY)
    put(ws, f"{col}{SN['s6eq']}", f"=$C${SN['eqBase'] if col == 'B' else SN['eqBull'] if col == 'C' else SN['eqBear']}",
        fmt=MONEY)
    put(ws, f"{col}{SN['s6cov']}",
        f"=MIN($C${SN['cvBase'] if col == 'B' else SN['cvBull'] if col == 'C' else SN['cvBear']}:$G${SN['cvBase'] if col == 'B' else SN['cvBull'] if col == 'C' else SN['cvBear']})",
        fmt='0.0"x"', align="center")
for r, label in [(SN["s6g"], "收入增长率 g"), (SN["s6m"], "毛利率 m"),
                 (SN["s6ni"], "2027E 净利润（元）"), (SN["s6cash"], "2030E 期末现金（元）"),
                 (SN["s6eq"], "股权价值 · 简化 DCF（元）", ), (SN["s6cov"], "最低利息保障倍数")]:
    put(ws, f"A{r}", label, align="left", color=GREYT, size=9)
put(ws, f"A{SN['s6chk']}", "勾稽校验（当前情景列 vs 模型）", align="left", size=9, color=GREYT)
ws.merge_cells(f"B{SN['s6chk']}:G{SN['s6chk']}")
put(ws, f"B{SN['s6chk']}",
    f'=IF(AND(ABS(INDEX($B${SN["s6ni"]}:$D${SN["s6ni"]},MATCH({A}!$B${R_SEL},$B${SN["s6hdr"]}:$D${SN["s6hdr"]},0))-利润表!$D${IS["ni"]})<1,'
    f'ABS(INDEX($B${SN["s6cash"]}:$D${SN["s6cash"]},MATCH({A}!$B${R_SEL},$B${SN["s6hdr"]}:$D${SN["s6hdr"]},0))-资产负债表!$G$5)<1,'
    f'ABS(INDEX($B${SN["s6eq"]}:$D${SN["s6eq"]},MATCH({A}!$B${R_SEL},$B${SN["s6hdr"]}:$D${SN["s6hdr"]},0))-$C${SN["eq"]})<1),'
    f'"✓ 当前情景列与模型勾稽一致（其余情景列为解析解，切换情景后自动重算）",'
    f'"✗ 与模型不一致")',
    bold=True, fill=CHECKF, align="left")

# ---- 计算区（公式中间结果） ----
put(ws, f"A{SN['calchdr']}", "计算区（公式中间结果，供上方对比表引用）｜行 = 情景，列 = 年份",
    color=GREYT, size=9, align="left", italic=True)
for col, y in zip(FC, YEARS[1:]):
    put(ws, f"{col}{SN['calchdr']}", y, color=GREYT, size=9, align="center", italic=True)
CALC_ROWS = [(SN["cfBase"], "B", "FCF（无杠杆）· Base"),
             (SN["cfBull"], "C", "FCF（无杠杆）· Bull"),
             (SN["cfBear"], "D", "FCF（无杠杆）· Bear"),
             (SN["ebBase"], "B", "EBIT · Base"),
             (SN["ebBull"], "C", "EBIT · Bull"),
             (SN["ebBear"], "D", "EBIT · Bear")]
for row, srccol, label in CALC_ROWS:
    gc, mc = f"${srccol}${SN['s6g']}", f"${srccol}${SN['s6m']}"
    put(ws, f"A{row}", label, color=GREYT, size=9, align="left")
    for i, x in enumerate(FC):
        t = i + 1
        if row in (SN["cfBase"], SN["cfBull"], SN["cfBear"]):
            f = (f"=(1-{A}!$C${AS['tax']})*(({mc}*利润表!$B${IS['rev']}"
                 f"-{A}!$C${AS['cac']}*{A}!$C${AS['cust']})*(1+{gc})^{t}"
                 f"-{S}!{x}{SUP['dep']}-{S}!{x}{SUP['int']})"
                 f"+{S}!{x}{SUP['dep']}+{S}!{x}{SUP['int']}-{S}!{x}{SUP['int']}*{A}!$C${AS['tax']}"
                 f"-{S}!{x}{SUP['capex']}"
                 f"-({A}!$C${AS['ar']}-{A}!$C${AS['ap']})*利润表!$B${IS['rev']}*((1+{gc})^{t}-(1+{gc})^{t-1})")
            put(ws, f"{x}{row}", f, fmt=MONEY, color=GREYT, size=9)
        else:
            put(ws, f"{x}{row}",
                f"=(({mc}*利润表!$B${IS['rev']}-{A}!$C${AS['cac']}*{A}!$C${AS['cust']})*(1+{gc})^{t})"
                f"-{S}!{x}{SUP['dep']}", fmt=MONEY, color=GREYT, size=9)
for row, cfrow, label in [(SN["evBase"], SN["cfBase"], "企业价值 · Base"),
                          (SN["evBull"], SN["cfBull"], "企业价值 · Bull"),
                          (SN["evBear"], SN["cfBear"], "企业价值 · Bear")]:
    srccol = "B" if row == SN["evBase"] else ("C" if row == SN["evBull"] else "D")
    gc = f"${srccol}${SN['s6g']}"
    put(ws, f"A{row}", label, color=GREYT, size=9, align="left")
    put(ws, f"C{row}",
        f"=SUMPRODUCT($C${cfrow}:$G${cfrow},$C${SN['df']}:$G${SN['df']})"
        f"+IF({A}!$C${AS['disc']}<={gc},0,$G${cfrow}*(1+{gc})/({A}!$C${AS['disc']}-{gc})*$G${SN['df']})",
        fmt=MONEY, color=GREYT, size=9)
for row, evrow, label in [(SN["eqBase"], SN["evBase"], "股权价值 · Base"),
                          (SN["eqBull"], SN["evBull"], "股权价值 · Bull"),
                          (SN["eqBear"], SN["evBear"], "股权价值 · Bear")]:
    put(ws, f"A{row}", label, color=GREYT, size=9, align="left")
    put(ws, f"C{row}", f"=C{evrow}+$C${SN['netcash']}", fmt=MONEY, color=GREYT, size=9)
for row, ebrow, label in [(SN["cvBase"], SN["ebBase"], "利息保障倍数 · Base"),
                          (SN["cvBull"], SN["ebBull"], "利息保障倍数 · Bull"),
                          (SN["cvBear"], SN["ebBear"], "利息保障倍数 · Bear")]:
    put(ws, f"A{row}", label, color=GREYT, size=9, align="left")
    for x in FC:
        put(ws, f"{x}{row}",
            f'=IF({S}!{x}${SUP["int"]}>0.001,{x}{ebrow}/{S}!{x}${SUP["int"]},"n.a.")',
            fmt="0.0", color=GREYT, size=9, align="center")

ws.merge_cells(f"A{SN['concl']}:G{SN['concl']}")
put(ws, f"A{SN['concl']}",
    f'="【动态结论】当前情景 "&{A}!$B${R_SEL}&"（收入增长率 "&TEXT({A}!$C${AS["g"]},"0.0%")'
    f'&"、毛利率 "&TEXT({A}!$C${AS["m"]},"0.0%")&"）：2027E 净利润 "&TEXT(利润表!$D${IS["ni"]}/10000,"0.0")'
    f'&" 万元，期末现金 "&TEXT(现金流量表!$D${CF["end"]}/10000,"0.0")'
    f'&" 万元，有息负债 "&TEXT({S}!$D${SUP["end"]}/10000,"0.0")'
    f'&" 万元；收入增长率每提高 1 个百分点，5 年累计净利润增加约 "&TEXT($C${SN["marg"]},"0.0")&" 万元。"',
    bold=True, fill=CHECKF, align="left")
page(ws, wide=True)

# ============================================================ 说明与检查
ws = ws_doc
ws.sheet_properties.tabColor = GREYT
ws.column_dimensions["A"].width = 48
ws.column_dimensions["B"].width = 44
for col in ["C", "D"]:
    ws.column_dimensions[col].width = 12
ws.merge_cells("A1:D1")
put(ws, "A1", "星链数科（模拟 fintech 公司）— Excel 三表联动模型 v4 · 说明与检查", bold=True,
    color=WHITE, size=12, fill=DARK, align="left", border=False)
ws.row_dimensions[1].height = 24
ws.merge_cells("A2:D2")
put(ws, "A2", "单位：人民币元 | 基年 2025A | 预测期 2026E–2030E | 打开本页即可看到模型结论与自动勾稽状态",
    color=GREYT, size=9, align="left", border=False, italic=True)

# ------------------------- 30秒速览 -------------------------
ws.merge_cells("A3:D3")
put(ws, "A3", "【30 秒速览】", bold=True, color=WHITE, fill=DARK, align="left")
quick = [
    ("是什么", "一个 6 年（2025A + 2026E–2030E）三表联动模型：利润表 / 资产负债表 / 现金流量表全公式咬合，含债务排程与简化 DCF，改一个假设全簿重算。"),
    ("怎么演示", "「假设」页顶部下拉框切 Base / Bull / Bear → 三表、债务排程、图表、敏感性结论同步变；本页 6 项勾稽始终显示 ✓。"),
    ("核心数字", f'="2027E 净利润 "&TEXT(利润表!$D${IS["ni"]}/10000,"0.0")&" 万元 · 2030E 期末现金 "&TEXT(现金流量表!$G${CF["end"]}/10000,"0.0")&" 万元 · 股权价值 "&TEXT(敏感性分析!$C${SN["eq"]}/10000,"0.0")&" 万元 · 最小利息保障 "&TEXT(MIN({S}!$C${SUP["cov"]}:$G${SUP["cov"]}),"0.0")&"x"'),
]
for i, (lab, f) in enumerate(quick):
    r = 4 + i
    put(ws, f"A{r}", lab, bold=True, align="left", fill=GREY, size=10)
    ws.merge_cells(f"B{r}:D{r}")
    put(ws, f"B{r}", f, size=10, align="left", fill=CHECKF)
    ws.row_dimensions[r].height = 30

# ------------------------- 核心结论看板 -------------------------
ws.merge_cells("A8:B8")
put(ws, "A8", "核心结论看板（随「假设」页情景自动重算）", bold=True, color=WHITE, fill=MID, align="left")

dash = [
    ("当前情景", f"={A}!$B${R_SEL}", None),
    ("收入增长率 / 毛利率", f'=TEXT({A}!$C${AS["g"]},"0.0%")&"  /  "&TEXT({A}!$C${AS["m"]},"0.0%")', None),
    ("2027E 净利润（万元）", f"=利润表!$D${IS['ni']}/10000", "#,##0.0"),
    ("2027E 期末现金（万元）", f"=现金流量表!$D${CF['end']}/10000", "#,##0.0"),
    ("2030E 期末现金（万元）", f"=现金流量表!$G${CF['end']}/10000", "#,##0.0"),
    ("5 年累计净利润（2026E–2030E，万元）", f"=SUM(利润表!$C${IS['ni']}:$G${IS['ni']})/10000", "#,##0.0"),
    ("增长率每 +1pp → 5 年累计净利润（万元）", f"=敏感性分析!$C${SN['marg']}", "#,##0.0"),
    ("股权价值（简化DCF，万元）", f"=敏感性分析!$C${SN['eq']}/10000", "#,##0.0"),
    ("2030E 有息负债余额（万元）", f"={S}!$G${SUP['end']}/10000", "#,##0.0"),
    ("最小利息保障倍数（2026E–2030E）", f"=MIN({S}!$C${SUP['cov']}:$G${SUP['cov']})", '0.0"x"'),
]
for i, (lab, f, fmt) in enumerate(dash):
    r = 9 + i
    put(ws, f"A{r}", lab, bold=True, align="left", fill=GREY, size=10)
    c = put(ws, f"B{r}", f, bold=True, align="center", size=14, fill=CHECKF)
    if fmt:
        c.number_format = fmt
    ws.row_dimensions[r].height = 26

put(ws, "A19", "现金安全预警", bold=True, align="left", fill=GREY, size=10)
ws.merge_cells("B19:D19")
put(ws, "B19",
    f'=IF(MIN(现金流量表!$C${CF["end"]}:$G${CF["end"]})<{A}!$C${AS["safe"]},'
    f'"⚠ 预测期内现金低于安全线：最低 "&TEXT(MIN(现金流量表!$C${CF["end"]}:$G${CF["end"]}),"#,##0")&" 元，安全垫 "&TEXT(MIN(现金流量表!$C${CF["end"]}:$G${CF["end"]})-{A}!$C${AS["safe"]},"#,##0")&" 元",'
    f'"✓ 预测期内现金始终高于安全线，最低 "&TEXT(MIN(现金流量表!$C${CF["end"]}:$G${CF["end"]}),"#,##0")&" 元，安全垫 "&TEXT(MIN(现金流量表!$C${CF["end"]}:$G${CF["end"]})-{A}!$C${AS["safe"]},"#,##0")&" 元")',
    bold=True, size=11, fill=CHECKF, align="left")
put(ws, "A20", "三表勾稽状态", bold=True, align="left", fill=GREY, size=10)
ws.merge_cells("B20:D20")
put(ws, "B20",
    f'=IF(AND(COUNTIF(资产负债表!$B${BS["res1"]}:$G${BS["res1"]},"平衡")=6,'
    f'COUNTIF(资产负债表!$B${BS["res2"]}:$G${BS["res2"]},"平衡")=6,'
    f'SUMPRODUCT(ABS(利润表!$B${IS["ni"]}:$G${IS["ni"]}-现金流量表!$B${CF["ni"]}:$G${CF["ni"]}))<0.01,'
    f'SUMPRODUCT(ABS(资产负债表!$C${BS["re"]}:$G${BS["re"]}-(资产负债表!$B${BS["re"]}:$F${BS["re"]}+利润表!$C${IS["ni"]}:$G${IS["ni"]})))<0.01,'
    f'SUMPRODUCT(ABS(资产负债表!$B${BS["debt"]}:$G${BS["debt"]}-{S}!$B${SUP["end"]}:$G${SUP["end"]}))<0.01,'
    f'SUMPRODUCT(ABS(利润表!$B${IS["int"]}:$G${IS["int"]}-{S}!$B${SUP["int"]}:$G${SUP["int"]}))<0.01),'
    f'"✓ 6 项检查全部通过：三表 + 债务排程联动无断点","✗ 存在不平衡，请检查")',
    bold=True, size=11, fill="C6EFCE", align="left")

ws.merge_cells("A22:D22")
put(ws, "A22", "演示动线（面试 3 步走，建议提前演练）", bold=True, color=WHITE, fill=MID, align="left")
steps = [
    "① 打开本页：看上方【30 秒速览】与“核心结论看板”，再看下方“自动勾稽检查”6 项全部 ✓，说明三表 + 债务排程联动无断点。",
    "② 打开「假设」页，把顶部“情景切换”下拉框从 Base 切到 Bull（增长率 5%→10%、毛利率 60%→65%），口头说：“我只改了这一个下拉框。”",
    "③ 切到「利润表 / 资产负债表 / 现金流量表」看三表同步变化 → 「支持排程」看债务与固定资产滚动及 ROIC → 「图表」看趋势图与现金跑道重绘 → 「敏感性分析」第六节看三情景并排对比表与动态结论句自动改写。",
    "④ 打开「支持排程」页，修改蓝色“新增借款 / 偿还本金”——利息费用、资产负债率、利息保障倍数、筹资现金流、期末现金全部联动（利息 = 平均余额 × 利率，无循环引用）。",
    "提示：自定义情景请改「假设」页第 26–28 行的驱动因子映射表（蓝色单元格）；直接改正式假设区数值会覆盖情景联动。",
]
for i, t in enumerate(steps):
    r = 23 + i
    ws.merge_cells(f"A{r}:D{r}")
    put(ws, f"A{r}", t, size=9, align="left")

ws.merge_cells("A29:B29")
put(ws, "A29", "自动勾稽检查", bold=True, color=WHITE, fill=MID, align="left")
chk_defs = [
    ("① 资产 = 负债 + 权益（全部 6 年）",
     f'=IF(COUNTIF(资产负债表!$B${BS["res1"]}:$G${BS["res1"]},"平衡")=6,"✓ 全部平衡（6/6）","✗ 存在不平衡")'),
    ("② 现金勾稽：本表现金 = 现金流量表期末现金（6 年）",
     f'=IF(COUNTIF(资产负债表!$B${BS["res2"]}:$G${BS["res2"]},"平衡")=6,"✓ 全部平衡（6/6）","✗ 存在不平衡")'),
    ("③ 净利润联动：利润表净利润 = 现金流量表起点",
     f'=IF(SUMPRODUCT(ABS(利润表!$B${IS["ni"]}:$G${IS["ni"]}-现金流量表!$B${CF["ni"]}:$G${CF["ni"]}))<0.01,"✓ 完全联动","✗ 存在断点")'),
    ("④ 留存收益滚动：上年留存 + 净利润 = 本年留存（预测年）",
     f'=IF(SUMPRODUCT(ABS(资产负债表!$C${BS["re"]}:$G${BS["re"]}-(资产负债表!$B${BS["re"]}:$F${BS["re"]}+利润表!$C${IS["ni"]}:$G${IS["ni"]})))<0.01,'
     f'"✓ 滚动正确","✗ 存在断点")'),
    ("⑤ 有息负债联动：资产负债表 = 债务排程期末余额（6 年）",
     f'=IF(SUMPRODUCT(ABS(资产负债表!$B${BS["debt"]}:$G${BS["debt"]}-{S}!$B${SUP["end"]}:$G${SUP["end"]}))<0.01,"✓ 完全联动","✗ 存在断点")'),
    ("⑥ 利息联动：利润表利息费用 = 债务排程利息（6 年）",
     f'=IF(SUMPRODUCT(ABS(利润表!$B${IS["int"]}:$G${IS["int"]}-{S}!$B${SUP["int"]}:$G${SUP["int"]}))<0.01,"✓ 完全联动","✗ 存在断点")'),
]
for i, (lab, f) in enumerate(chk_defs):
    r = 30 + i
    put(ws, f"A{r}", lab, size=9, align="left")
    put(ws, f"B{r}", f, bold=True, size=11, align="center", fill="C6EFCE")

# ------------------------- 模型地图 -------------------------
ws.merge_cells("A37:D37")
put(ws, "A37", "模型地图（Sheet 关系图 · 文字版）", bold=True, color=WHITE, fill=MID, align="left")
mmap = [
    "【假设】——情景切换 + 蓝色输入，是全簿唯一数据入口：驱动 →【利润表】【资产负债表】【现金流量表】",
    "【支持排程】——债务排程 / 固定资产排程：利息费用 → 利润表；有息负债、固定资产净值 → 资产负债表；偿付利息、新增借款 → 现金流量表",
    "【图表】← 读取 ——【利润表 / 资产负债表 / 现金流量表 / 支持排程】：4 张图（收入与净利润、现金跑道 vs 安全线、债务余额与利息保障倍数、资产负债结构）",
    "【敏感性分析】← 读取 —— 全簿：增长率 × 毛利率双变量（①）、边际敏感度（②）、股权价值分解（③）、三情景并排对比（第六节）",
    "【说明与检查】（本页）← 汇总 —— 全簿：30 秒速览 + 核心看板 + 模型地图 + 6 项勾稽",
    "数据流单向：假设 → 报表 → 排程 / 图表 / 敏感性；唯一天然回路“利息 ⇄ 现金”用平均余额法显式解开，全簿无循环引用。",
]
for i, t in enumerate(mmap):
    r = 38 + i
    ws.merge_cells(f"A{r}:D{r}")
    put(ws, f"A{r}", t, size=9, align="left")

ws.merge_cells("A46:D46")
put(ws, "A46", "使用方法与模型逻辑", bold=True, color=WHITE, fill=MID, align="left")
body = [
    "【使用方法】改「假设」页蓝色单元格 → 三张报表自动重算；底部勾稽校验应始终显示“平衡”。",
    "【情景切换】顶部下拉框 Base / Bull / Bear，自动切换收入增长率与毛利率（映射表见「假设」页第 26–28 行）。",
    "【收入】收入 = 上年收入 ×（1 + 增长率）；客户数 = 上年客户数 ×（1 + 增长率）——假设 ARPU 稳定（期望值口径）。",
    "【成本】毛利 = 收入 × 毛利率；运营成本 = 客户数 × 获客成本（CAC）。",
    "【债务排程】见「支持排程」页：期末有息负债 = 期初 + 新增借款 − 偿还本金；利息 = 平均有息负债 × 年利率（A-11），新增借款自放入年起生息。",
    "【利息口径】利息当年全额付现——经营活动加回利息费用、筹资活动列示偿付利息，两者对消；净利润 =（EBIT − 利息）×（1 − 税率），税盾自然体现，不存在循环引用。",
    "【利润】EBIT = 毛利 − 运营成本 − 折旧；税前利润 = EBIT − 利息费用；所得税 = MAX(税前, 0) × 税率；净利润 = 税前 − 所得税。",
    "【折旧口径】按固定资产期初净值 × 折旧率（A-12）计提，并以期初净值为上限（MIN），不会折成负值；原值 / 净值 / 累计折旧滚动见「支持排程」页。",
    "【现金流】经营 = 净利润 + 折旧 + 利息费用 − 营运资本变动（现金流量表行名“营运资本变动（增加 = 现金占用）”，正数表示现金被占用）；投资 = −资本支出；融资 = 新增借款 − 偿还本金 − 偿付利息。",
    "【ROIC】ROIC = EBIT ×（1 − 税率）÷（有息负债 + 总权益 − 现金），见「支持排程」页；衡量投入资本回报，不受杠杆结构影响，比 ROE 更适合跨资本结构比较。",
    "【现金】期末现金 = 期初现金 + 净现金流；资产负债表现金 = 上年现金 + 净现金流。",
    "【权益】留存收益 = 上年留存收益 + 当年净利润；总权益 = 股本 + 留存收益。",
    "【估值】简化 DCF：无杠杆自由现金流（经营 + 投资 − 利息税盾），永续增长终值；股权价值 = 企业价值 + 基年现金 − 有息负债。",
    "【数据来源与免责】模拟 fintech 公司“星链数科”技能演示模型；基年（2025A）数据为模拟实际数，非真实财报，参考 P4 月度经营分析包口径整理。仅供学习与技能展示，不构成任何投资建议。",
]
for i, t in enumerate(body):
    r = 47 + i
    ws.merge_cells(f"A{r}:D{r}")
    put(ws, f"A{r}", t, size=9, align="left")
page(ws, wide=True)

wb.calculation.fullCalcOnLoad = True
wb.save(OUT)
print("saved:", OUT, "| growth =", GROWTH)
