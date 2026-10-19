# -*- coding: utf-8 -*-
"""财务设计师：从 key_metrics.json 注入确切数字，生成一页纸 A4 HTML 并渲染 PDF。"""
import json
import os
from weasyprint import HTML

# 可移植路径：脚本位于 <项目>/code/ 时定位项目根；notebook 环境下 cwd 即根目录
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _HERE = os.path.abspath(os.getcwd())
ROOT = os.path.dirname(_HERE) if os.path.basename(_HERE) == "code" else _HERE
OUT = os.path.join(ROOT, "outputs")
DOC = ROOT
km = json.load(open(f"{OUT}/key_metrics.json", encoding="utf-8"))
s = {r["scenario"]: r for r in km["scenarios"]}
f = lambda x, d=2: f"{x:,.{d}f}"
pct = lambda x, d=1: f"{x*100:.{d}f}%"
sens_vals = [v["rev2027"] for v in km["hw_sensitivity"].values() if "rev2027" in v]

kpi = [
    ("2026E 净收入", f"{f(km['rev26'])}<small>亿</small>", f"YoY {pct(km['rev26_yoy'])}", "up"),
    ("2026E EBITDA", f"{f(km['ebitda26'])}<small>亿</small>", f"利润率 {km['ebitda26_margin']:.1f}%", "up"),
    ("2027E 净收入(基准)", f"{f(km['rev27'])}<small>亿</small>", f"YoY {pct(km['rev27_yoy'])}", "up"),
    ("2027E EBITDA(基准)", f"{f(km['ebitda27'])}<small>亿</small>", f"利润率 {km['ebitda27_margin']:.1f}%", "up"),
    ("现金低点·未融资", f"{f(km['trough_cash'])}<small>亿</small>", f"{km['trough_q']}｜红线 {km['min_cash']:.1f}", "down"),
    ("建议融资", f"{f(km['raise_amount'],1)}<small>亿</small>", "股权3.0＋授信2.0", "flat"),
]
kpi_html = "".join(
    f'<div class="kpi"><div class="kpi-t">{t}</div><div class="kpi-v {c}">{v}</div>'
    f'<div class="kpi-s">{sub}</div></div>' for t, v, sub, c in kpi)

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@page {{ size: A4 portrait; margin: 6mm 7mm 5mm 7mm; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Noto Sans CJK SC', sans-serif; color: #1B2631; font-size: 7.4pt; line-height: 1.3; }}

/* ---------- 页眉 ---------- */
.hdr {{ display: flex; justify-content: space-between; align-items: flex-end;
       border-bottom: 2pt solid #1B2631; padding-bottom: 1.8mm; }}
.hdr h1 {{ font-size: 13pt; font-weight: 700; letter-spacing: 0.2pt; }}
.hdr h1 span {{ color: #1F618D; }}
.hdr .meta {{ text-align: right; font-size: 6.4pt; color: #566573; line-height: 1.42; }}
.hdr .meta b {{ color: #1B2631; }}

/* ---------- 结论先行 ---------- */
.concl {{ background: #EBF2F8; border-left: 3pt solid #1F618D; padding: 1.7mm 2.6mm;
         margin: 1.9mm 0; border-radius: 0 1.2mm 1.2mm 0; }}
.concl h2 {{ font-size: 8.5pt; color: #1F618D; margin-bottom: 1mm; }}
.concl li {{ margin: 0 0 0.75mm 4mm; }}
.concl li:last-child {{ margin-bottom: 0; }}
.concl b {{ color: #C0392B; }}
.concl .act b {{ color: #1E8449; }}

/* ---------- KPI 卡片 ---------- */
.kpis {{ display: flex; gap: 1.8mm; margin: 1.8mm 0; }}
.kpi {{ flex: 1; border: 0.5pt solid #D5DBDB; border-top: 1.8pt solid #1F618D;
       border-radius: 1mm; padding: 1.5mm 1.2mm 1.2mm; text-align: center; background: #FDFEFE; }}
.kpi-t {{ font-size: 6.2pt; color: #566573; }}
.kpi-v {{ font-size: 12.5pt; font-weight: 700; margin: 0.5mm 0 0.3mm; }}
.kpi-v small {{ font-size: 7pt; font-weight: 400; }}
.kpi-v.up {{ color: #C0392B; }} .kpi-v.down {{ color: #1E8449; }} .kpi-v.flat {{ color: #1F618D; }}
.kpi-s {{ font-size: 6pt; color: #566573; }}

/* ---------- 图表行 ---------- */
.charts {{ display: flex; gap: 2.6mm; margin: 1.5mm 0; }}
.chart {{ flex: 1; }}
.chart img {{ width: 100%; }}
.cap {{ font-size: 6.2pt; color: #424949; line-height: 1.25; margin-top: 0.6mm;
       border-top: 0.5pt solid #D5DBDB; padding-top: 0.6mm; }}
.cap b {{ color: #1B2631; }}

/* ---------- 底部三栏 ---------- */
.bottom {{ display: flex; gap: 2.4mm; margin-top: 1.6mm; }}
.col {{ flex: 1; }}
.col.wide {{ flex: 1.1; }}
.box {{ border: 0.5pt solid #D5DBDB; border-radius: 1mm; padding: 1.4mm 1.8mm; height: 100%; }}
.box h3 {{ font-size: 7.7pt; color: #1B2631; border-bottom: 0.8pt solid #1F618D;
          padding-bottom: 0.7mm; margin-bottom: 1.2mm; }}
table {{ width: 100%; border-collapse: collapse; font-size: 6.5pt; }}
th {{ background: #F2F4F4; color: #424949; font-weight: 600; padding: 0.65mm 1mm;
     border: 0.4pt solid #D5DBDB; text-align: right; }}
th:first-child {{ text-align: left; }}
td {{ padding: 0.6mm 1mm; border: 0.4pt solid #E5E8E8; text-align: right; }}
td:first-child {{ text-align: left; color: #424949; }}
tr.hl td {{ background: #EBF2F8; font-weight: 700; }}
.up {{ color: #C0392B; }} .down {{ color: #1E8449; }}
.note {{ font-size: 5.8pt; color: #7B7D7D; line-height: 1.24; margin-top: 0.8mm; }}

.fin li {{ margin: 0 0 1mm 3.4mm; }}
.fin b {{ color: #1F618D; }}
.fin .amt {{ font-size: 10pt; font-weight: 700; color: #C0392B; }}

/* ---------- 页脚 ---------- */
.ftr {{ border-top: 0.5pt solid #D5DBDB; margin-top: 0.9mm; padding-top: 0.6mm;
      font-size: 5.8pt; color: #7B7D7D; line-height: 1.26; }}
</style></head><body>

<div class="hdr">
  <h1>星联金科 <span>· 2026–2028 财务规划一页纸</span></h1>
  <div class="meta"><b>FP&A · MVP2 决策摘要</b>｜2026年10月19日｜单位：人民币亿元<br>
  口径：管理会计（税前）｜历史 2023Q1–2026Q3｜预测 Holt-Winters</div>
</div>

<div class="concl">
  <h2>结论先行（Executive Summary）</h2>
  <ol>
    <li><b>盈利拐点确认</b>：2026E 净收入 <b>{f(km['rev26'])}亿（YoY {pct(km['rev26_yoy'])}）</b>，EBITDA <b>{f(km['ebitda26'])}亿、利润率 {km['ebitda26_margin']:.1f}%</b>（2025 年仅 1.8%）；基准预测 2027E 收入 {f(km['rev27'])}亿（YoY {pct(km['rev27_yoy'])}）、EBITDA {f(km['ebitda27'])}亿（{km['ebitda27_margin']:.1f}%）。</li>
    <li><b>增长质量高于增长速度</b>：收入增量 {pct(km['vol_share'],0)} 来自规模、{pct(km['price_share'],0)} 来自变现率（{km['p25']:.2f}%→{km['p26']:.2f}%）；EBITDA 改善的 <b>{pct(km['eff_split']['from_margin']/km['eff_split']['total'],0)} 来自利润率提升</b>——按 2025 年利润率、规模增长仅贡献 +{km['eff_split']['from_growth']:.2f}亿，单位经济已跑通。</li>
    <li class="act"><b>现金是唯一约束，建议 2027Q1 前融资 5.0亿（股权 3.0＋授信 2.0）</b>：基准现金低点 {km['trough_q']} <b>{f(km['trough_cash'])}亿</b>，击穿 {km['min_cash']:.1f}亿运营红线 {f(km['gap'])}亿；融资后低点抬至 {f(km['trough_post'])}亿，悲观情景叠加成本触发仍守红线。</li>
  </ol>
</div>

<div class="kpis">{kpi_html}</div>

<div class="charts">
  <div class="chart">
    <img src="outputs/fig1_ebitda_bridge.png">
    <div class="cap"><b>图1｜EBITDA 差异桥：</b>改善 +{km['eff_split']['total']:.2f}亿＝规模增长 +{km['eff_split']['from_growth']:.2f}＋利润率提升 +{km['eff_split']['from_margin']:.2f}（95%）。成本率全面改善：信用 {km['bridge_notes']['信用成本']}、风险分担 {km['bridge_notes']['风险分担成本']}、获客 {km['bridge_notes']['获客成本']}、运营 {km['bridge_notes']['运营成本']}。</div>
  </div>
  <div class="chart">
    <img src="outputs/fig2_cashflow.png">
    <div class="cap"><b>图2｜现金流：</b>未融资时 2027 年现金持续低于红线；股权 3.0亿 2027Q1 到账后低点 {f(km['trough_post'])}亿、无需动用授信；悲观情景低点 {f(km['trough_bear_post'])}亿（授信提尽），叠加成本触发后 {f(km['trough_bear_trigger'])}亿，守红线。</div>
  </div>
</div>

<div class="bottom">
  <div class="col">
    <div class="box">
      <h3>量价分解（2025A → 2026E）</h3>
      <table>
        <tr><th>指标</th><th>2025A</th><th>2026E</th><th>变化</th></tr>
        <tr><td>放款规模（亿）</td><td>{f(km['orig25'],1)}</td><td>{f(km['orig26'],1)}</td><td class="up">+{pct(km['orig26_yoy'])}</td></tr>
        <tr><td>变现率</td><td>{km['p25']:.2f}%</td><td>{km['p26']:.2f}%</td><td class="up">+{(km['p26']-km['p25'])*100:.0f}bp</td></tr>
        <tr class="hl"><td>净收入（亿）</td><td>{f(km['rev25'])}</td><td>{f(km['rev26'])}</td><td class="up">+{pct(km['rev26_yoy'])}</td></tr>
        <tr><td>├ 规模贡献</td><td colspan="2"></td><td class="up">+{f(km['vol_effect'])}（{pct(km['vol_share'],0)}）</td></tr>
        <tr><td>└ 变现率贡献</td><td colspan="2"></td><td class="up">+{f(km['price_effect'])}（{pct(km['price_share'],0)}）</td></tr>
        <tr><td>规模对 EBITDA 贡献*</td><td colspan="2"></td><td>+{f(km['eff_split']['from_growth'])}</td></tr>
      </table>
      <div class="note">* EBITDA 改善的可加和分解：规模效应 = Δ收入×2025 年利润率 = +{f(km['eff_split']['from_growth'])}亿；利润率提升 = +{f(km['eff_split']['from_margin'])}亿（95%）。</div>
    </div>
  </div>
  <div class="col">
    <div class="box">
      <h3>三情景假设（2027E）</h3>
      <table>
        <tr><th>指标</th><th>悲观</th><th>基准</th><th>乐观</th></tr>
        <tr><td>放款增速</td><td>+{pct(s['悲观']['orig_growth'],1)}</td><td>+{pct(s['基准']['orig_growth'],1)}</td><td>+{pct(s['乐观']['orig_growth'],1)}</td></tr>
        <tr><td>变现率</td><td>{s['悲观']['take_rate']:.2f}%</td><td>{s['基准']['take_rate']:.2f}%</td><td>{s['乐观']['take_rate']:.2f}%</td></tr>
        <tr><td>净收入（亿）</td><td>{f(s['悲观']['revenue'])}</td><td>{f(s['基准']['revenue'])}</td><td>{f(s['乐观']['revenue'])}</td></tr>
        <tr class="hl"><td>EBITDA（亿）</td><td>{f(s['悲观']['ebitda'])}</td><td>{f(s['基准']['ebitda'])}</td><td>{f(s['乐观']['ebitda'])}</td></tr>
        <tr><td>利润率</td><td>{s['悲观']['margin']:.1f}%</td><td>{s['基准']['margin']:.1f}%</td><td>{s['乐观']['margin']:.1f}%</td></tr>
        <tr><td>现金低点(融资后)</td><td>{f(km['trough_bear_post'])}</td><td>{f(km['trough_post'])}</td><td>{f(km['trough_bull_post'])}</td></tr>
      </table>
      <div class="note">注：悲观为压力口径（增速较基准 −12pp、变现率 −0.20pp），2027 年现金持续低于红线、授信提尽后低点仍 {f(km['trough_bear_post'])}亿，故须绑定成本触发条款（触发后 {f(km['trough_bear_trigger'])}亿）。</div>
    </div>
  </div>
  <div class="col wide">
    <div class="box fin">
      <h3>融资建议：5.0亿（2027Q1 前交割）</h3>
      <ul>
        <li><b>结构</b>：股权 <span class="amt">3.0亿</span>＋银行授信 <span class="amt">2.0亿</span>——授信提款灵活、按 4.5% 计价、闲置不计息，股权占比保控制权。</li>
        <li><b>测算</b>：覆盖基准缺口 {f(km['gap'])}亿后低点 {f(km['trough_cash'])}→{f(km['trough_post'])}亿（运营红线的 {km['trough_post']/km['min_cash']:.1f} 倍）；悲观情景低点 {f(km['trough_bear_post'])}亿（授信提尽 2.0亿、按 4.5% 计息合计 {f(km['interest_paid_bear'])}亿），绑定成本触发条款（连续两季收入增速&lt;10% 即获客−30%／运营−15%，年化释放 {f(km['trigger_release'])}亿）后 {f(km['trough_bear_trigger'])}亿，守住红线。</li>
        <li><b>时点</b>：窗口期足额融资——悲观情景中融资窗口反而关闭；2026Q4 已递延 0.1亿非关键资本开支过渡。</li>
      </ul>
    </div>
  </div>
</div>

<div class="ftr">
  口径与来源：管理会计口径（税前、不含联营）。历史 2023Q1–2026Q3 与全部预测为<b>模拟数据</b>（"星联金科"为虚构演示公司），不构成投资建议。预测采用 Holt-Winters 指数平滑（有界 MLE：α={km['hw_alpha']:.2f}、β={km['hw_beta']:.2f}、γ={km['hw_gamma']:.2f}，季节因子 {km['hw_seasonal'][0]:.2f}/{km['hw_seasonal'][1]:.2f}/{km['hw_seasonal'][2]:.2f}/{km['hw_seasonal'][3]:.2f}；2027E 收入敏感性 {f(min(sens_vals))}–{f(max(sens_vals))}亿）。三情景以 HW 为中枢（规模增速 ±12pp、变现率 −0.20/+0.12pp）。数字可复现：P4_analysis.ipynb 与 outputs/（6 个 CSV/JSON）。
</div>

</body></html>"""

open(f"{DOC}/onepager.html", "w", encoding="utf-8").write(html)
HTML(string=html, base_url=DOC).write_pdf(f"{DOC}/MVP2_一页纸_A4.pdf")
print("pdf written")
