# -*- coding: utf-8 -*-
"""面试速查卡：A4 单页，关键数字 + 高频追问一句话答案。数字从 key_metrics.json 注入。"""
import json
import os

from weasyprint import HTML

# 可移植路径：脚本位于 <项目>/code/ 时定位项目根；notebook 环境下 cwd 即根目录
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _HERE = os.path.abspath(os.getcwd())
ROOT = os.path.dirname(_HERE) if os.path.basename(_HERE) == "code" else _HERE
km = json.load(open(f"{ROOT}/outputs/key_metrics.json", encoding="utf-8"))
s = {r["scenario"]: r for r in km["scenarios"]}
ts = {r["take_delta_pp"]: r for r in km["take_sensitivity"]}
f = lambda x, d=2: f"{x:,.{d}f}"
pct = lambda x, d=1: f"{x*100:.{d}f}%"

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@page {{ size: A4 portrait; margin: 8mm 9mm 7mm 9mm; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Noto Sans CJK SC', sans-serif; color: #1B2631; font-size: 8.6pt; line-height: 1.42; }}

.hdr {{ display: flex; justify-content: space-between; align-items: flex-end;
       border-bottom: 2pt solid #1B2631; padding-bottom: 1.6mm; }}
.hdr h1 {{ font-size: 13pt; font-weight: 700; }}
.hdr h1 span {{ color: #1F618D; }}
.hdr .meta {{ text-align: right; font-size: 6.6pt; color: #566573; line-height: 1.4; }}

.sec {{ margin-top: 3mm; }}
.sec h2 {{ font-size: 9.6pt; color: #1F618D; border-bottom: 0.8pt solid #1F618D;
          padding-bottom: 0.6mm; margin-bottom: 1.4mm; }}

table {{ width: 100%; border-collapse: collapse; font-size: 7.8pt; }}
th {{ background: #1F618D; color: #fff; font-weight: 600; padding: 0.8mm 1.2mm;
     text-align: left; }}
td {{ padding: 0.7mm 1.2mm; border-bottom: 0.4pt solid #E5E8E8; vertical-align: top; }}
tr:nth-child(even) td {{ background: #F8F9F9; }}
td.k {{ font-weight: 700; color: #1B2631; white-space: nowrap; }}
td.v {{ color: #212F3D; }}
.num {{ font-weight: 700; color: #C0392B; }}
.num.g {{ color: #1E8449; }}
.num.b {{ color: #1F618D; }}

.qa {{ margin-top: 3mm; }}
.qa h2 {{ font-size: 9.6pt; color: #1F618D; border-bottom: 0.8pt solid #1F618D;
         padding-bottom: 0.6mm; margin-bottom: 1.4mm; }}
.q {{ margin-bottom: 1.9mm; }}
.q .qt {{ font-size: 8.2pt; font-weight: 700; color: #1B2631; margin-bottom: 0.4mm; }}
.q .qt em {{ color: #C0392B; font-style: normal; }}
.q .qa-a {{ font-size: 7.8pt; color: #212F3D; padding-left: 2.6mm; border-left: 1.6pt solid #D5DBDB; }}

.ftr {{ border-top: 0.5pt solid #D5DBDB; margin-top: 2.4mm; padding-top: 1mm;
      font-size: 6.2pt; color: #7B7D7D; line-height: 1.35; }}
</style></head><body>

<div class="hdr">
  <h1>面试速查卡 <span>· 星联金科 2026–2028 财务规划（MVP2）</span></h1>
  <div class="meta">FP&A 案例面试｜2026-10-19｜配合一页纸 PDF + notebook 使用<br>
  数据为模拟演示（虚构公司）｜全部数字可一键复现</div>
</div>

<div class="sec">
  <h2>① 三句话结论（脱稿）</h2>
  <table>
    <tr><td class="k" style="width:22%">盈利拐点</td><td class="v">2026E 收入 <span class="num">{f(km['rev26'])}亿（YoY {pct(km['rev26_yoy'])}）</span>、EBITDA <span class="num">{f(km['ebitda26'])}亿、利润率 {km['ebitda26_margin']:.1f}%</span>（2025 年 1.8%）；2027E 基准 {f(km['rev27'])}亿 / {f(km['ebitda27'])}亿</td></tr>
    <tr><td class="k">增长质量</td><td class="v">收入增量 79% 规模 / 21% 变现率；EBITDA 改善 <span class="num">95% 靠利润率提升</span>——规模效应仅 +{f(km['eff_split']['from_growth'])}亿，单位经济已跑通</td></tr>
    <tr><td class="k">现金约束</td><td class="v">低点 {km['trough_q']} <span class="num">{f(km['trough_cash'])}亿</span>（红线 {km['min_cash']:.1f}，缺口 {f(km['gap'])}）→ 建议融资 <span class="num">5.0 亿</span>：股权 3.0＋授信 2.0</td></tr>
  </table>
</div>

<div class="sec">
  <h2>② 关键数字速查</h2>
  <table>
    <tr><th style="width:24%">类别</th><th>数字</th></tr>
    <tr><td class="k">量价分解 2026E</td><td class="v">规模 +{f(km['vol_effect'])}（79%）＋变现率 +{f(km['price_effect'])}（21%）＝ +{f(km['rev26']-km['rev25'])}亿；take {km['p25']:.2f}%→{km['p26']:.2f}%</td></tr>
    <tr><td class="k">EBITDA 归因</td><td class="v">规模 +{f(km['eff_split']['from_growth'])}＋利润率 +{f(km['eff_split']['from_margin'])}（95%）＝ +{f(km['eff_split']['total'])}亿（可加和口径）</td></tr>
    <tr><td class="k">成本率变化</td><td class="v">信用 1.09→1.02%｜风险分担 0.60→0.55%｜获客 29.2→26.5%｜运营 23.2→21.2%</td></tr>
    <tr><td class="k">HW 基准</td><td class="v">α={km['hw_alpha']:.2f} β={km['hw_beta']:.2f} γ={km['hw_gamma']:.2f}｜季节因子 1.00/1.06/1.08/1.15｜敏感性 23.5–24.8 亿｜区间固定 random_state=42</td></tr>
    <tr><td class="k">2027E 三情景</td><td class="v">悲观 {f(s['悲观']['revenue'])}亿/{f(s['悲观']['ebitda'])}亿｜<b>基准 {f(s['基准']['revenue'])}/{f(s['基准']['ebitda'])}</b>｜乐观 {f(s['乐观']['revenue'])}/{f(s['乐观']['ebitda'])}（增速 8.8%/20.8%/32.8%）</td></tr>
    <tr><td class="k">变现率敏感度</td><td class="v">固定规模增速，take ±0.10pp → EBITDA ±{f(ts[0.1]['ebitda']-ts[0.0]['ebitda'])}亿；±0.20pp → {f(ts[-0.2]['ebitda'])}–{f(ts[0.2]['ebitda'])}亿</td></tr>
    <tr><td class="k">融资后低点</td><td class="v">基准 <span class="num">{f(km['trough_post'])}</span>（授信提款 0、利息 0）｜乐观 {f(km['trough_bull_post'])}｜悲观 {f(km['trough_bear_post'])}（授信 2.0 提尽、利息 {f(km['interest_paid_bear'])}亿）｜+成本触发 <span class="num">{f(km['trough_bear_trigger'])}</span></td></tr>
    <tr><td class="k">成本触发</td><td class="v">连续两季收入增速&lt;10% → 获客 −30%/运营 −15%，年化释放 {f(km['trigger_release'])}亿，季度线性累积</td></tr>
  </table>
</div>

<div class="qa">
  <h2>③ 高频追问 · 一句话答案（完整版见《演示话术与QA.md》8 问）</h2>
  <div class="q"><div class="qt"><em>Q1</em> 数据是真的吗？</div>
    <div class="qa-a">模拟数据、虚构公司，页脚已声明；案例展示的是方法论与可复现工程链路，换真实数据只改第 0 节假设数组。</div></div>
  <div class="q"><div class="qt"><em>Q2</em> 为什么 HW 不用 ARIMA/Prophet？</div>
    <div class="qa-a">15 个季度小样本 + 强季节性；HW 参数少可解释、边界可约束；ARIMA 同样本量易过拟合，Prophet 需更长历史。代码内含无约束 MLE 退化对照（弃用）。</div></div>
  <div class="q"><div class="qt"><em>Q3</em> 参数顶在边界上，凭什么信？</div>
    <div class="qa-a">三档替代边界 2027E 收入 23.49–24.79 亿（中枢 -5%~+0.3%），决策在整个区间稳健；不确定性用 80% 区间 + 三情景 + 触发条款管理，不假装精确。</div></div>
  <div class="q"><div class="qt"><em>Q4</em> 规模贡献几乎零，增长没价值？</div>
    <div class="qa-a">那是按 2025 年旧成本结构的反事实口径；规模贡献收入增量 79% 与风控数据飞轮——我们不为增长付费，只为验证过的单位经济扩张。</div></div>
  <div class="q"><div class="qt"><em>Q5</em> 为什么融 5 亿？授信一次性到账吗？</div>
    <div class="qa-a">缺口 0.77 亿是下限，金额为悲观情景可生存性定价（触发后 {f(km['trough_bear_trigger'])} 亿）；<b>授信按需提款</b>——现金&lt;4.0 亿才补足、按 4.5% 计息、闲置不计息，基准情景零提款零利息。</div></div>
  <div class="q"><div class="qt"><em>Q6</em> 最大风险？预测错了怎么办？</div>
    <div class="qa-a">变现率不及预期 / 信用成本反弹 / 融资窗口关闭；每个都有先行指标与对冲动作——不为单一预测下注，为"错了也能活"设计结构。</div></div>
  <div class="q"><div class="qt"><em>Q7</em> 能上线吗？怎么维护？</div>
    <div class="qa-a">notebook 与脚本产物逐字节一致（回归校验）；数字单一事实源 JSON 注入、assert 保加和；每月改假设数组重跑，十分钟出新版。</div></div>
  <div class="q"><div class="qt"><em>Q8</em> 触发条款真能执行吗？</div>
    <div class="qa-a">触发条件客观（财报增速）、动作预先约定（−30%/−15%）、效果已量化（+2.46 亿/年）——把砍预算的谈判前置到协议里。</div></div>
</div>

<div class="sec">
  <h2>④ 3 分钟演示时间轴</h2>
  <table>
    <tr><td class="k" style="width:18%">0:00–0:30</td><td class="v">三句话结论脱稿：拐点确认 → 增长质量 → 现金约束要融资 5 亿</td></tr>
    <tr><td class="k">0:30–1:15</td><td class="v">手指图1：EBITDA 改善 95% 靠利润率；"按 2025 年利润率规模只贡献 0.1 亿"</td></tr>
    <tr><td class="k">1:15–2:10</td><td class="v">手指图2：不融资全年在红线下；股权 3 亿到账低点 5.2 亿；悲观+触发回 3.9 亿</td></tr>
    <tr><td class="k">2:10–3:00</td><td class="v">收尾三句：5 亿 / 2027Q1 前交割 / 协议写触发条款；"在能融到钱的时候系安全带"</td></tr>
  </table>
</div>

<div class="sec">
  <h2>⑤ 演示前 60 秒自检</h2>
  <table>
    <tr><td class="k" style="width:18%">脱稿</td><td class="v">三句话结论不念稿；数字咬实（19.3 / 40% / 2.3 / 12%）</td></tr>
    <tr><td class="k">手指图</td><td class="v">讲利润手指图1小字；讲现金手指图2低点与红线</td></tr>
    <tr><td class="k">被动严谨</td><td class="v">不主动讲 α/β/γ；被问再答方法论（显得 rigorous 不 defensiveness）</td></tr>
    <tr><td class="k">锚点</td><td class="v">5 亿是锚点：压价回到"为悲观情景可生存性定价"；授信按需提款主动说清</td></tr>
    <tr><td class="k">禁忌</td><td class="v">不说"大概"；每个数字有出处，不确定的说"回 notebook 核实后回复"</td></tr>
  </table>
</div>

<div class="ftr">
  口径：管理会计（税前、不含联营），人民币亿元｜复现：P4_analysis.ipynb 一键重跑，outputs/ 6 个 CSV/JSON + 2 图｜
  完整话术与 QA：演示话术与QA.md｜业务背景与验收：docs/BRD.md｜本卡数据为模拟演示，不构成投资建议。
</div>

</body></html>"""

open(f"{ROOT}/cheatcard.html", "w", encoding="utf-8").write(html)
HTML(string=html, base_url=ROOT).write_pdf(f"{ROOT}/面试速查卡_A4.pdf")
print("cheatcard pdf written")
