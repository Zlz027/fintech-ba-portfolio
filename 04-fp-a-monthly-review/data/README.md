# 数据说明 · P4 月度经营分析包（模拟数据，无需下载）

> **本项目不依赖任何外部数据文件**——全部数据由 `src/finance.py` 的 `simulate_company()`
> 以固定种子（seed=42）程序化生成，"星链数科"为虚构的场景消费金融科技公司。
> 本文说明数据是如何生成的、字段含义是什么，便于面试官在不运行代码时理解数据基础。

## 1. 数据性质

| 项 | 内容 |
|---|---|
| 数据性质 | **固定种子模拟数据**（`np.random.default_rng(42)`），非真实公司 |
| 生成入口 | `src/finance.py::simulate_company(n_months=24, n_weeks=52, seed=42, recovery_rate=0.92)` |
| 调用链 | Notebook 第 1 单元格调用 → 月度损益 + 周度现金流 → 全部分析模块 |
| 可复现性 | 同种子跨运行逐位一致；改变 `recovery_rate` 即得敏感性四情景（唯一差异参数） |

## 2. 生成逻辑（业务含义）

**月度口径（万元，24 个月：2023-01 ~ 2024-12）**

```
放款量 volume   = 6000 × 1.018^t × (1 + 季节) × (1 + 噪声)    # 月增 1.8%，1/2 月 −15%、11/12 月 +10%
净收入率 nim   = clip(0.0195 − 0.00002×t + 噪声, 1.55%, 2.10%)
获客成本率 cac = clip(0.0050 + 0.00001×t + 噪声, 0.45%, 0.60%)
信用损失率 loss= clip(0.0062 + 噪声, 0.45%, 0.80%)；2024-06 +0.15pp（风险事件）
运营成本 opex  = 45 × 1.003^t + volume × 0.12%
净收入 revenue = volume × nim
经营利润 op_profit = revenue − volume×(cac+loss) − opex
```

**预算口径（最新月 2024-12）**：`budget_volume = volume/1.05`（实际超目标 5%）、
`budget_nim = nim + 0.02pp`（实际价更低）——刻意构造"以价换量"场景供中值法分解。

**周度口径（万元，52 周）**：`inflow = 存量回收（≈周放款 × 回收系数 0.92）`；
`outflow = 新放款 + 获客 + 运营 + 信用损失 + 季度末营销脉冲（每 13 周 +300）`。
回收系数 < 1 → 本金净投放 → 经营现金流结构性为负——**融资需求的来源**。

## 3. 字段含义

**monthly（月度损益，24 行）**：`month`（年月）、`volume`（放款量）、`nim`（月净收入率）、
`revenue`（净收入）、`acquisition`（获客成本）、`opex`（运营成本）、`credit_loss`（信用损失）、
`op_profit`（经营利润）、`budget_volume` / `budget_nim`（最新月预算）。

**weekly（周度现金流，52 行）**：`week`（周序号 1-52）、`inflow`（流入）、
`outflow`（流出）、`net_cf`（净现金流）。

**常量**：期初现金 ¥4,500 万、流动性缓冲线 ¥3,000 万（约 6 周净流出）。

## 4. 如何"获取"数据

无需下载——直接运行即生成：

```bash
cd 04-fp-a-monthly-review
python3 -c "import sys; sys.path.insert(0, 'src'); import finance; \
m, w, c = finance.simulate_company(); print(m.shape, w.shape, c)"
# 预期输出：(24, 9) (52, 4) 4500.0
```

或执行仓库根目录 `make p4`（约 9 秒，完整跑通"分析 → 图 → 结论"链路）。

## 5. 注意事项

- 数据量级参考行业经验值，**不代表任何真实公司**；生产环境应以实际总账/流水复算；
- 模拟参数集中在 `src/finance.py::simulate_company` 顶部，改任意参数全链路自动重算；
- 局限性与声明详见项目 README 第 10 节。
