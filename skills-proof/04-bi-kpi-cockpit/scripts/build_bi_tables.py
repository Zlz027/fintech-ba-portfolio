#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fintech-ba-portfolio 四项目 outputs → Tableau「金融科技 BA 核心指标看板」数据表。

输入：--root 指向 fintech-ba-portfolio 仓库（含 01-python-credit-scoring / 02-python-churn-ltv /
      03-python-fraud-threshold / 04-fp-a-monthly-review 四个项目的 outputs/）。
输出（--out 指定，默认 ./data；全部 utf-8-sig 带 BOM，Excel 双击不乱码、Tableau 正确识别中文）：
      1) kpi_summary.csv             一行 20 列 KPI 宽表
      2) time_series_and_curves.csv  Tidy 长表（P1 80 行 + P3 4600 行 + P4 26 行）
      3) p2_priority_scatter.csv     200 行优先挽留名单 + risk_tier 风险分层列
      4) p4_scenarios.csv            三情景（Base/Bull/Bear）12 个月利润，供情景筛选器联动

约定：仅用 Python 标准库；关键数字全部由源文件计算，脚本末尾「交叉验证报告」与人工
      核实的期望值逐条比对，任一不一致即 assert 失败并给出清晰错误信息。
用法：python build_bi_tables.py --root /path/to/fintech-ba-portfolio --out ./data
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

BUFFER_LINE = 3000.0  # P4 现金流安全缓冲线（万元），全脚本唯一常量

# ---------------------------------------------------------------------------
# 人工核实过的期望值（交叉验证用；若源数据更新，需同步改这里）
# ---------------------------------------------------------------------------
EXP = {
    "p1_cv_auc": 0.8628,      # metrics.json XGBoost cv_auc="0.8628±0.0037" 左半
    "p1_ks": 0.5794,          # metrics.json XGBoost test_ks=0.5793940687
    "p1_threshold": 529.345,  # policy_curve.csv margin_book 最大行 threshold=529.3452
    "p1_approval": 0.90613,   # 同上 approval_rate
    "p1_bad_rate": 0.03362,   # 同上 bad_rate
    "p1_margin": 0.01747,     # 同上 margin_book（全组合利润率，非绝对利润）
    "p2_auc": 0.8422,         # metrics.json LogisticRegression AUC
    "p2_roi": 2.62,           # uplift_sensitivity.csv 挽留成功率=30% 行 毛ROI
    "p2_n": 550,              # 同上行 最优触达N*
    "p3_auprc": 0.7993,       # model_comparison.csv class_weight 行 AUPRC
    "p3_threshold": 0.5388,   # threshold_curve.csv cost 最小行 threshold
    "p3_cost": 4309.27,       # 同上行 cost（与 strategy_cost 最优点一致）
    "p3_no_block": 11479.26,  # strategy_cost.csv「不拦截」总成本
    "p4_w58": 2690.7,         # cash_forecast_13w.csv week=58 cash_balance
    "p4_final": 80.4,         # week=65 cash_balance（见底）
    "p4_lo80": -4434.1,       # week=65 cash_lo80（80% 悲观下界）
    "p4_base": 337.2,         # scenarios.csv Base 经营利润合计（万元）
    "p4_bear": -179.4,        # scenarios.csv Bear 经营利润合计（万元）
    "p4_gap": 2920,           # round(3000-80.4)，与 funding_advice「¥2920 万」互证
    "save_ratio": 0.6246,     # (11479.26-4309.27)/11479.26
}


# ---------------------------------------------------------------------------
# 通用 IO 工具
# ---------------------------------------------------------------------------
def load_csv(path: Path) -> list[dict[str, str]]:
    """读取 CSV 为 dict 列表；utf-8-sig 读取以容忍中文表头自带 BOM。"""
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> Any:
    """读取 JSON（utf-8-sig，容忍 BOM）。"""
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def pick(rows: list, pred, what: str):
    """从行列表中取满足条件的首行；找不到就以友好错误退出（替代裸 next()）。"""
    hit = [r for r in rows if pred(r)]
    if not hit:
        sys.exit(f"源数据缺少预期内容：{what}。请检查 outputs 文件是否被改动。")
    return hit[0]


def dump_csv(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    """写 CSV：utf-8-sig 带 BOM；None 统一写空串，保证 Excel/Tableau 不报错。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows([["" if v is None else v for v in row] for row in rows])
    print(f"  已写出 {path}（{len(rows)} 行数据 × {len(header)} 列）")


def detect_root(cli_root: str | None) -> Path:
    """定位仓库根目录（含 01-python-credit-scoring/outputs 的目录）。

    顺序：--root 参数 → 环境变量 PORTFOLIO_ROOT → ./fintech-ba-portfolio →
    当前工作目录及其最多 6 层祖先（含各自的直接子目录）→ 脚本所在目录及其
    最多 6 层祖先（含各自的直接子目录）。
    向上追溯 6 层是为了兼容 scripts/build_bi_tables.py 放在
    skills-proof/04-bi-kpi-cockpit/scripts/ 这类深层子目录的用法。
    找到多个候选时打印警告并按优先级用第一个（显式指定 --root/环境变量时不警告）。
    """
    def expand(base: Path) -> list[Path]:
        return [base, *sorted(p for p in base.glob("*") if p.is_dir())]

    candidates: list[Path] = []
    explicit = bool(cli_root) or bool(os.environ.get("PORTFOLIO_ROOT"))
    if cli_root:
        candidates.append(Path(cli_root))
    env = os.environ.get("PORTFOLIO_ROOT")
    if env:
        candidates.append(Path(env))
    candidates.append(Path.cwd() / "fintech-ba-portfolio")
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for base in [start, *list(start.parents)[:6]]:
            candidates.extend(expand(base))

    seen: set[Path] = set()
    found: list[Path] = []
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        if (c / "01-python-credit-scoring" / "outputs").is_dir():
            found.append(c.resolve())
    if not found:
        sys.exit("未找到 fintech-ba-portfolio 根目录（缺 01-python-credit-scoring/outputs），"
                 "请用 --root 指定，或设置环境变量 PORTFOLIO_ROOT")
    if len(found) > 1 and not explicit:
        print(f"警告：找到 {len(found)} 个候选根目录，按优先级使用第一个；"
              f"如需指定请用 --root：")
        for p in found:
            print(f"  - {p}")
    return found[0]


# ---------------------------------------------------------------------------
# 开跑前检查：必需源文件清单（缺失时一次性列全，提示先跑哪个项目）
# ---------------------------------------------------------------------------
REQUIRED_FILES: dict[str, list[str]] = {
    "P1 信用风险": ["01-python-credit-scoring/outputs/metrics.json",
                    "01-python-credit-scoring/outputs/policy_curve.csv"],
    "P2 客户流失": ["02-python-churn-ltv/outputs/metrics.json",
                    "02-python-churn-ltv/outputs/uplift_sensitivity.csv",
                    "02-python-churn-ltv/outputs/priority_retention_list.csv"],
    "P3 欺诈检测": ["03-python-fraud-threshold/outputs/threshold_curve.csv",
                    "03-python-fraud-threshold/outputs/strategy_cost.csv",
                    "03-python-fraud-threshold/outputs/model_comparison.csv",
                    "03-python-fraud-threshold/outputs/threshold_sensitivity.csv"],
    "P4 经营分析": ["04-fp-a-monthly-review/outputs/cash_forecast_13w.csv",
                    "04-fp-a-monthly-review/outputs/scenarios.csv",
                    "04-fp-a-monthly-review/outputs/funding_advice.csv"],
}


def preflight(root: Path) -> None:
    """检查四个项目的必需源文件是否齐全；缺失时列出全部缺项并友好退出。"""
    missing = [f"[{proj}] {f}"
               for proj, files in REQUIRED_FILES.items()
               for f in files if not (root / f).exists()]
    if missing:
        sys.exit("以下源文件缺失，请先运行对应项目的 notebook 生成 outputs/ 再重试：\n  "
                 + "\n  ".join(missing))


# ---------------------------------------------------------------------------
# 四个项目的 extract 函数
# ---------------------------------------------------------------------------
def extract_p1(root: Path) -> dict[str, Any]:
    """P1 信用风险。

    - metrics.json：列表，取 model=="XGBoost" 的 cv_auc（字符串 "0.8629±0.0036"，
      按 '±' 拆分取左半得 0.8629；注意 LR 那条 cv_auc 是 null，不能取）与 test_ks；
    - policy_curve.csv：threshold,approval_rate,bad_rate,margin_approved,margin_book，
      共 40 行；取 margin_book 最大的一行为最优策略（阈值/通过率/坏账率/组合利润率）。
    """
    out = root / "01-python-credit-scoring" / "outputs"
    metrics = load_json(out / "metrics.json")
    xgb = pick(metrics, lambda m: m.get("model") == "XGBoost",
               "P1 metrics.json 中 model='XGBoost' 的行")
    cv_auc = float(str(xgb["cv_auc"]).split("±")[0])  # "0.8629±0.0036" → 0.8629
    ks = float(xgb["test_ks"])

    curve = [
        {
            "threshold": float(r["threshold"]),
            "approval_rate": float(r["approval_rate"]),
            "bad_rate": float(r["bad_rate"]),
            "margin_book": float(r["margin_book"]),
        }
        for r in load_csv(out / "policy_curve.csv")
    ]
    best = max(curve, key=lambda r: r["margin_book"])
    return {"cv_auc": cv_auc, "ks": ks, "curve": curve, "best": best}


def extract_p2(root: Path) -> dict[str, Any]:
    """P2 客户流失。

    - metrics.json：取 model=="LogisticRegression" 的 AUC；
    - uplift_sensitivity.csv（中文表头 挽留成功率,最优触达N*,触达预算,净收益,毛ROI）：
      取挽留成功率=30% 的基准情景行，得毛 ROI 与最优触达人数 N*；
    - priority_retention_list.csv：表头 customerID,tenure,MonthlyCharges,Contract,
      churn_prob,LTV,expected_save（注意字段名是 LTV 不是 clv），200 行按 expected_save
      降序的优先挽留名单；按 churn_prob 分三档：>=0.80 高 / 0.65-0.80 中 / <0.65 低。
    """
    out = root / "02-python-churn-ltv" / "outputs"
    metrics = load_json(out / "metrics.json")
    lr = pick(metrics, lambda m: m.get("model") == "LogisticRegression",
              "P2 metrics.json 中 model='LogisticRegression' 的行")
    auc = float(lr["AUC"])

    sens = load_csv(out / "uplift_sensitivity.csv")
    base = pick(sens, lambda r: float(r["挽留成功率"].strip().rstrip("%")) == 30.0,
                "P2 uplift_sensitivity.csv 中 挽留成功率=30% 的行")
    roi = float(base["毛ROI"])
    best_n = int(float(base["最优触达N*"]))

    tiers = {"高": 0, "中": 0, "低": 0}
    customers: list[dict[str, Any]] = []
    for r in load_csv(out / "priority_retention_list.csv"):
        p = float(r["churn_prob"])
        tier = "高" if p >= 0.80 else ("中" if p >= 0.65 else "低")
        tiers[tier] += 1
        customers.append({**r, "risk_tier": tier})
    return {"auc": auc, "roi": roi, "best_n": best_n,
            "customers": customers, "tiers": tiers}


def extract_p3(root: Path) -> dict[str, Any]:
    """P3 欺诈检测。

    - threshold_curve.csv：threshold,flagged,flag_rate,caught,recall,cost，2300 行、
      按 threshold 降序存储；取 cost 最小一行为成本最优点，同时输出按 threshold
      升序重排的曲线（否则 Tableau 折线会乱）；
    - strategy_cost.csv（策略,拦截笔数,总成本）：取「不拦截」与含「成本最优」两行，
      与曲线最低点交叉断言；
    - model_comparison.csv：取方法含 class_weight 行的 AUPRC；
    - threshold_sensitivity.csv：取 fp_cost=120 行的 best_threshold，与曲线最低点阈值
      交叉断言（两处独立计算应一致）。
    """
    out = root / "03-python-fraud-threshold" / "outputs"
    curve = [
        {
            "threshold": float(r["threshold"]),
            "flag_rate": float(r["flag_rate"]),
            "recall": float(r["recall"]),
            "cost": float(r["cost"]),
        }
        for r in load_csv(out / "threshold_curve.csv")
    ]
    best = min(curve, key=lambda r: r["cost"])
    curve_sorted = sorted(curve, key=lambda r: r["threshold"])

    costs = load_csv(out / "strategy_cost.csv")
    no_block = float(pick(costs, lambda r: r["策略"].strip() == "不拦截",
                          "P3 strategy_cost.csv 中「不拦截」行")["总成本"])
    optimal = float(pick(costs, lambda r: "成本最优" in r["策略"],
                         "P3 strategy_cost.csv 中含「成本最优」行")["总成本"])

    cmp_rows = load_csv(out / "model_comparison.csv")
    auprc = float(pick(cmp_rows, lambda r: "class_weight" in r["方法"],
                       "P3 model_comparison.csv 中 class_weight 行")["AUPRC"])

    sens = load_csv(out / "threshold_sensitivity.csv")
    sens_thr = float(pick(sens, lambda r: abs(float(r["fp_cost"]) - 120.0) < 1e-9,
                          "P3 threshold_sensitivity.csv 中 fp_cost=120 行")["best_threshold"])
    return {"curve_sorted": curve_sorted, "best": best, "auprc": auprc,
            "optimal_cost": optimal, "no_block_cost": no_block, "sens_threshold": sens_thr}


def extract_p4(root: Path) -> dict[str, Any]:
    """P4 经营分析。

    - cash_forecast_13w.csv：week,net_cf,cash_balance,cash_lo80，13 行（week 53-65），
      单位万元；注意只有 80% 悲观下界 cash_lo80，没有上界；
    - scenarios.csv：情景,12个月收入合计,经营利润合计,利润率,年末月利润，共 3 行
      （Base/Bull/Bear）；取 Base 与 Bear 两行的经营利润合计（万元）进 KPI 宽表，
      三行全量进 p4_scenarios.csv 供看板「情景」筛选器联动；
    - funding_advice.csv：拼接全部「结论」文本，其中「¥2920 万」用于融资缺口交叉断言。
    """
    out = root / "04-fp-a-monthly-review" / "outputs"
    cash = sorted(
        (
            {
                "week": int(float(r["week"])),
                "cash_balance": float(r["cash_balance"]),
                "cash_lo80": float(r["cash_lo80"]),
            }
            for r in load_csv(out / "cash_forecast_13w.csv")
        ),
        key=lambda r: r["week"],
    )
    scenarios = load_csv(out / "scenarios.csv")
    base = float(pick(scenarios, lambda r: r["情景"].strip().startswith("Base"),
                      "P4 scenarios.csv 中 Base 行")["经营利润合计"])
    bear = float(pick(scenarios, lambda r: r["情景"].strip().startswith("Bear"),
                      "P4 scenarios.csv 中 Bear 行")["经营利润合计"])
    advice = " ".join(r["结论"] for r in load_csv(out / "funding_advice.csv"))
    return {"cash": cash, "by_week": {c["week"]: c for c in cash},
            "scenarios": scenarios,
            "base_profit": base, "bear_profit": bear, "advice": advice,
            "final_cash": cash[-1]["cash_balance"]}


# ---------------------------------------------------------------------------
# 四个 write 函数
# ---------------------------------------------------------------------------
KPI_HEADER = [
    # 列名只放指标名，数值在数据行里；数据更新时不用改列名（verify 会断言数值）
    "数据生成日期", "信用风险CV_AUC", "测试集KS", "最优阈值分",
    "最优通过率", "最优坏账率", "最优组合利润率",
    "流失模型AUC", "挽留ROI", "最优触达人数",
    "欺诈检测AUPRC", "欺诈成本最优阈值", "最优阈值总成本",
    "不拦截总成本", "成本节省比例", "融资缺口_万元",
    "Base情景12个月经营利润_万元", "Bear情景12个月经营利润_万元",
    "现金见底_万元", "安全缓冲线_万元",
]


def write_kpi_summary(out_dir: Path, kpi: dict[str, Any]) -> None:
    """写 kpi_summary.csv：一行 20 列宽表，列顺序固定，Tableau 可直接做 KPI 卡片。

    数值规则：比率 4 位小数；成本列保留源文件 2 位（与 strategy_cost 钩稽）；
    万元金额 1 位小数；人数/缺口为整数。
    """
    row = [
        kpi["gen_date"],
        f"{kpi['cv_auc']:.4f}", f"{kpi['ks']:.4f}",
        f"{kpi['best_threshold']:.2f}", f"{kpi['best_approval']:.4f}",
        f"{kpi['best_bad_rate']:.4f}", f"{kpi['best_margin']:.4f}",
        f"{kpi['churn_auc']:.4f}", f"{kpi['roi']:.2f}", kpi["best_n"],
        f"{kpi['auprc']:.4f}", f"{kpi['fraud_threshold']:.4f}",
        f"{kpi['optimal_cost']:.2f}", f"{kpi['no_block_cost']:.2f}",
        f"{kpi['save_ratio']:.4f}", kpi["gap"],
        f"{kpi['base_profit']:.1f}", f"{kpi['bear_profit']:.1f}",
        f"{kpi['final_cash']:.1f}", str(int(BUFFER_LINE)),
    ]
    dump_csv(out_dir / "kpi_summary.csv", KPI_HEADER, [row])


TS_HEADER = ["series_type", "x_label", "x_value", "metric_name", "metric_value",
             "aux_label", "aux_value", "is_optimal", "note"]

NOTE_P1 = "最优：通过率90.6%/坏账率3.4%/利润率1.75%（阈值529分）"
NOTE_P3 = "成本最优阈值0.5388：总成本¥4,309/召回74.7%/仅拦截0.11%交易"
NOTE_P4 = {58: "第6周击穿¥3,000万缓冲线",
           65: "第13周见底¥80万/80%下界-¥4,434万"}


def write_time_series(out_dir: Path, p1: dict[str, Any], p3: dict[str, Any],
                      p4: dict[str, Any]) -> None:
    """写 time_series_and_curves.csv：Tidy 长表，Tableau 友好。

    每行 = 一个横坐标点 × 一个指标。Tableau 里按 series_type 筛选后，
    x_value→列、metric_value→行、metric_name→颜色即可出折线/面积图；
    is_optimal=1 用于高亮最优点；aux_* 列携带标注信息（P1 评分阈值、P4 缓冲线）。
    """
    rows: list[list[Any]] = []

    # P1：40 点 × 2 指标 = 80 行；仅 margin_book 最大行（组合利润率行）置 is_optimal=1
    best_thr = p1["best"]["threshold"]
    for pt in p1["curve"]:
        is_opt = 1 if abs(pt["threshold"] - best_thr) < 1e-9 else 0
        rows.append(["P1_通过率-坏账率-利润率曲线", "通过率", pt["approval_rate"],
                     "坏账率", pt["bad_rate"], "评分阈值", pt["threshold"], 0, ""])
        rows.append(["P1_通过率-坏账率-利润率曲线", "通过率", pt["approval_rate"],
                     "组合利润率", pt["margin_book"], "评分阈值", pt["threshold"],
                     is_opt, NOTE_P1 if is_opt else ""])

    # P3：2300 点 × 2 指标 = 4600 行；按 threshold 升序（源文件降序必须重排）；
    # 仅 cost 最小行（总成本行）置 is_optimal=1，aux 留空
    best_thr = p3["best"]["threshold"]
    for pt in p3["curve_sorted"]:
        is_opt = 1 if abs(pt["threshold"] - best_thr) < 1e-12 else 0
        rows.append(["P3_成本-阈值曲线", "判定阈值", pt["threshold"],
                     "总成本(元)", pt["cost"], "", "", is_opt,
                     NOTE_P3 if is_opt else ""])
        rows.append(["P3_成本-阈值曲线", "判定阈值", pt["threshold"],
                     "召回率", pt["recall"], "", "", 0, ""])

    # P4：13 点 × 2 指标 = 26 行；aux 恒为安全缓冲线 3000；note 描述整周事件，故该周两行都带
    for pt in p4["cash"]:
        note = NOTE_P4.get(pt["week"], "")
        rows.append(["P4_13周现金流预测", "周序号", pt["week"],
                     "现金余额(万元)", pt["cash_balance"],
                     "安全缓冲线(万元)", int(BUFFER_LINE), 0, note])
        rows.append(["P4_13周现金流预测", "周序号", pt["week"],
                     "80%悲观下界(万元)", pt["cash_lo80"],
                     "安全缓冲线(万元)", int(BUFFER_LINE), 0, note])

    dump_csv(out_dir / "time_series_and_curves.csv", TS_HEADER, rows)


def write_p2_scatter(out_dir: Path, p2: dict[str, Any]) -> None:
    """写 p2_priority_scatter.csv：200 行优先挽留名单原样透传 + risk_tier 分层列。"""
    header = ["customerID", "tenure", "MonthlyCharges", "Contract",
              "churn_prob", "LTV", "expected_save", "risk_tier"]
    rows = [[c["customerID"], c["tenure"], c["MonthlyCharges"], c["Contract"],
             c["churn_prob"], c["LTV"], c["expected_save"], c["risk_tier"]]
            for c in p2["customers"]]
    dump_csv(out_dir / "p2_priority_scatter.csv", header, rows)


SCEN_HEADER = ["情景", "12个月收入合计_万元", "经营利润合计_万元", "利润率", "年末月利润_万元"]


def write_p4_scenarios(out_dir: Path, p4: dict[str, Any]) -> None:
    """写 p4_scenarios.csv：三情景（Base/Bull/Bear）12 个月收入与利润。

    用途：看板「情景」筛选器的数据源——筛选器筛选本表，联动三情景利润条形图；
    注意 13 周现金流预测只有 Base 一条路径（源数据如此），现金流图固定为 Base 口径，
    不得用情景筛选器去"过滤"现金流图（会得到虚假联动）。
    """
    rows = []
    for r in p4["scenarios"]:
        rows.append([
            r["情景"].strip(),
            f"{float(r['12个月收入合计']):.1f}",
            f"{float(r['经营利润合计']):.1f}",
            f"{float(r['利润率']):.4f}",
            f"{float(r['年末月利润']):.1f}",
        ])
    dump_csv(out_dir / "p4_scenarios.csv", SCEN_HEADER, rows)


# ---------------------------------------------------------------------------
# verify：交叉验证报告
# ---------------------------------------------------------------------------
def verify(kpi: dict[str, Any], p1: dict[str, Any], p2: dict[str, Any],
           p3: dict[str, Any], p4: dict[str, Any]) -> None:
    """交叉验证报告：逐条打印「计算来源 → 计算值 vs 期望值」，不一致即报错退出。

    注意：本函数禁止改用 assert——python -O / PYTHONOPTIMIZE=1 会在编译期
    静默剔除 assert 语句，导致全部检查被跳过却仍打印「全部交叉验证通过」，
    验证形同虚设。必须用显式 raise，任何运行模式下都 fail-fast。
    """

    def chk(name: str, got: Any, exp: Any, tol: float = 1e-4) -> None:
        """比对计算值与期望值；容差按数据类型在调用处显式指定或取默认。

        容差策略：
        - 比率类（AUC/KS/ROI/AUPRC/节省比例）：默认 1e-4
        - 阈值类（评分阈值/欺诈阈值）：5e-3
        - 成本类（元）：5e-3
        - 金额类（万元）：0.1（浮点表示/四舍五入不应误报）
        - 人数/整数：0（精确相等）
        """
        ok = abs(float(got) - float(exp)) <= tol
        print(f"  {'[OK]' if ok else '[FAIL]'} {name:<24} 计算={got:<16.6g} 期望={exp:<12.6g}")
        if not ok:
            raise AssertionError(
                f"交叉验证失败：{name} 计算值 {got} 与期望值 {exp} 不一致（容差 {tol}）")

    def chk_text(name: str, ok: bool, detail: str) -> None:
        print(f"  {'[OK]' if ok else '[FAIL]'} {name:<24} {detail}")
        if not ok:
            raise AssertionError(f"交叉验证失败：{name}（{detail}）")

    print("\n================ 交叉验证报告 ================")

    print("[P1 信用风险] 来源：metrics.json（cv_auc 按 '±' 拆分）+ policy_curve.csv")
    chk("XGBoost CV_AUC", p1["cv_auc"], EXP["p1_cv_auc"])
    chk("XGBoost 测试集 KS", p1["ks"], EXP["p1_ks"])
    chk("最优阈值分", p1["best"]["threshold"], EXP["p1_threshold"], 5e-3)
    chk("最优通过率", p1["best"]["approval_rate"], EXP["p1_approval"], 1e-4)
    chk("最优坏账率", p1["best"]["bad_rate"], EXP["p1_bad_rate"], 1e-4)
    chk("最优组合利润率", p1["best"]["margin_book"], EXP["p1_margin"], 1e-4)
    chk_text("policy_curve 共 40 行", len(p1["curve"]) == 40, f"实际 {len(p1['curve'])} 行")
    chk_text("best 行确为 margin_book 最大值",
             p1["best"]["margin_book"] == max(r["margin_book"] for r in p1["curve"]),
             f"max={max(r['margin_book'] for r in p1['curve'])}")
    chk_text("P1 注释数字与计算一致",
             round(p1["best"]["approval_rate"] * 100, 1) == 90.6
             and round(p1["best"]["bad_rate"] * 100, 1) == 3.4
             and round(p1["best"]["margin_book"] * 100, 2) == 1.75
             and round(p1["best"]["threshold"]) == 529, "90.6%/3.4%/1.75%/529 分")

    print("[P2 客户流失] 来源：metrics.json + uplift_sensitivity.csv + priority_retention_list.csv")
    chk("LogisticRegression AUC", p2["auc"], EXP["p2_auc"])
    chk("挽留 ROI（30% 情景）", p2["roi"], EXP["p2_roi"], 5e-3)
    chk("最优触达人数 N*", p2["best_n"], EXP["p2_n"], 0)
    chk_text("名单共 200 行", len(p2["customers"]) == 200, f"实际 {len(p2['customers'])} 行")
    t = p2["tiers"]
    chk_text("风险分层 高/中/低 = 67/85/48",
             (t["高"], t["中"], t["低"]) == (67, 85, 48), f"实际 {t['高']}/{t['中']}/{t['低']}")

    print("[P3 欺诈检测] 来源：threshold_curve.csv + strategy_cost.csv + "
          "model_comparison.csv + threshold_sensitivity.csv")
    chk("class_weight AUPRC", p3["auprc"], EXP["p3_auprc"])
    chk("成本最优阈值", p3["best"]["threshold"], EXP["p3_threshold"])
    chk("最优阈值总成本", p3["optimal_cost"], EXP["p3_cost"], 5e-3)
    chk("不拦截总成本", p3["no_block_cost"], EXP["p3_no_block"], 5e-3)
    chk("成本节省比例", kpi["save_ratio"], EXP["save_ratio"])
    chk_text("曲线最低成本 == strategy_cost 最优点",
             abs(p3["best"]["cost"] - p3["optimal_cost"]) < 5e-3,
             f"{p3['best']['cost']:.2f} vs {p3['optimal_cost']:.2f}")
    chk_text("曲线最低阈值 == sensitivity(fp=120)",
             abs(p3["best"]["threshold"] - p3["sens_threshold"]) < 1e-6,
             f"{p3['best']['threshold']:.10f} vs {p3['sens_threshold']:.10f}")
    chk_text("threshold_curve 2300 行且已升序",
             len(p3["curve_sorted"]) == 2300 and all(
                 a["threshold"] <= b["threshold"]
                 for a, b in zip(p3["curve_sorted"], p3["curve_sorted"][1:])),
             f"实际 {len(p3['curve_sorted'])} 行")
    chk_text("P3 注释数字与计算一致",
             round(p3["best"]["recall"] * 100, 1) == 74.7
             and round(p3["best"]["flag_rate"] * 100, 2) == 0.11, "召回 74.7%/拦截 0.11%")

    print("[P4 经营分析] 来源：cash_forecast_13w.csv + scenarios.csv + funding_advice.csv")
    chk("第 6 周现金余额", p4["by_week"][58]["cash_balance"], EXP["p4_w58"], 0.1)
    chk("第 13 周现金见底", p4["final_cash"], EXP["p4_final"], 0.1)
    chk("第 13 周 80% 悲观下界", p4["by_week"][65]["cash_lo80"], EXP["p4_lo80"], 0.1)
    chk("Base 经营利润合计", p4["base_profit"], EXP["p4_base"], 0.1)
    chk("Bear 经营利润合计", p4["bear_profit"], EXP["p4_bear"], 0.1)
    chk("融资缺口 = 3000 - 见底", kpi["gap"], EXP["p4_gap"], 0)
    chk_text("funding_advice 含『2920』", "2920" in p4["advice"],
             "与 round(3000-80.4)=2920 互证")
    chk_text("现金预测 13 行且末周 week 65",
             len(p4["cash"]) == 13 and p4["cash"][-1]["week"] == 65,
             f"实际 {len(p4['cash'])} 行，末周 week {p4['cash'][-1]['week']}")

    print("================ 全部交叉验证通过 ================")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="fintech-ba-portfolio → Tableau 看板数据表（零依赖）")
    ap.add_argument("--root", default=None,
                    help="fintech-ba-portfolio 目录；缺省依次尝试 PORTFOLIO_ROOT 环境变量、"
                         "./fintech-ba-portfolio、脚本所在目录及父目录自动探测")
    ap.add_argument("--out", default="./data", help="输出目录，默认 ./data（自动创建）")
    args = ap.parse_args()

    root = detect_root(args.root)
    preflight(root)
    out_dir = Path(args.out)
    print(f"仓库根目录：{root}\n输出目录：{out_dir.resolve()}")

    p1 = extract_p1(root)
    p2 = extract_p2(root)
    p3 = extract_p3(root)
    p4 = extract_p4(root)

    # 派生指标：融资缺口与成本节省比例（公式计算，不硬编码）
    gap = int(round(BUFFER_LINE - p4["final_cash"]))
    save_ratio = (p3["no_block_cost"] - p3["optimal_cost"]) / p3["no_block_cost"]

    kpi = {
        "gen_date": os.environ.get("BUILD_DATE") or date.today().isoformat(),
        # 默认当天日期；设 BUILD_DATE=YYYY-MM-DD 可固定（可复现构建/避免重跑产生 git diff）
        "cv_auc": p1["cv_auc"], "ks": p1["ks"],
        "best_threshold": p1["best"]["threshold"],
        "best_approval": p1["best"]["approval_rate"],
        "best_bad_rate": p1["best"]["bad_rate"],
        "best_margin": p1["best"]["margin_book"],
        "churn_auc": p2["auc"], "roi": p2["roi"], "best_n": p2["best_n"],
        "auprc": p3["auprc"], "fraud_threshold": p3["best"]["threshold"],
        "optimal_cost": p3["optimal_cost"], "no_block_cost": p3["no_block_cost"],
        "save_ratio": save_ratio, "gap": gap,
        "base_profit": p4["base_profit"], "bear_profit": p4["bear_profit"],
        "final_cash": p4["final_cash"],
    }

    print("\n正在写出四张表：")
    write_kpi_summary(out_dir, kpi)
    write_time_series(out_dir, p1, p3, p4)
    write_p2_scatter(out_dir, p2)
    write_p4_scenarios(out_dir, p4)

    t = p2["tiers"]
    print(f"\nP2 风险分层人数：高 {t['高']} / 中 {t['中']} / 低 {t['低']}"
          f"（分层线 churn_prob >=0.80 / 0.65-0.80 / <0.65）")

    verify(kpi, p1, p2, p3, p4)
    print("\n完成。四张表已就绪，可导入 Tableau Public 搭建看板。")


if __name__ == "__main__":
    main()
