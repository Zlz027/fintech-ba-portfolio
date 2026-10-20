# 数据说明 · P1 信用风险评分卡（Give Me Some Credit）

> 本目录存放**原始数据**（已 gitignore，不随仓库分发）。数据来源、获取方式、字段含义见本文；
> 拿到文件后按下方路径放置即可复跑 Notebook，无需改任何代码。

## 1. 数据来源

| 项 | 内容 |
|---|---|
| 数据集 | **Give Me Some Credit（GMSC）**，Kaggle 竞赛公开数据集 |
| 原始出处 | Kaggle `GiveMeSomeCredit`（cs-training.csv / cs-test.csv） |
| 本仓库使用版本 | **OpenML / TabArena 清洗版**（`data_id=46929`，150,000 行 × 11 列，无缺失异常值），约 7MB |
| 许可与版权 | 版权归原作者（Kaggle / OpenML）；仅作学习与方法论演示，不作商业用途 |

## 2. 获取方式（二选一）

**方式 A（推荐，无需注册）——OpenML 官方接口：**

```bash
python3 -c "from sklearn.datasets import fetch_openml; \
d = fetch_openml(data_id=46929, as_frame=True); \
d.frame.to_csv('data/raw/givesomecredit.arff', index=False)"
```

**方式 B——Kaggle 原版（需 Kaggle 账号 + API token）：**

```bash
pip install kaggle          # 先配置 ~/.kaggle/kaggle.json
kaggle competitions download -c GiveMeSomeCredit -p data/raw/
# Kaggle 原版为 cs-training.csv / cs-test.csv，需自行合并；原版含缺失值与极端值，
# 与本项目 README 第 2 节"数据质量"描述的口径不同，建议用方式 A。
```

或直接运行仓库根目录的 `make fetch-data`（交互式指引，不自动下载）。

## 3. 字段含义（11 列）

| 字段（清洗版 snake_case） | Kaggle 原版字段 | 含义 | 本项目口径 |
|---|---|---|---|
| `serious_dlqin2yrs` | SeriousDlqin2yrs | 两年内严重财务困境（1=是） | **目标变量 y**，违约率 6.68% |
| `revolving_utilization` | RevolvingUtilizationOfUnsecuredLines | 循环额度利用率（总额度使用比例） | 入模前按 p99.9 截尾（>1 为超额） |
| `age` | age | 年龄 | 与违约率呈 U 型，被 PAV 单调约束合并为单箱（IV=0） |
| `number_of_time_30_59_days_past_due_not_worse` | NumberOfTime30-59DaysPastDueNotWorse | 逾期 30-59 天次数 | IV=0.49，第一驱动 |
| `debt_ratio` | DebtRatio | 债务收入比 | 按 p99.9 截尾 |
| `monthly_income` | MonthlyIncome | 月收入 | 清洗版无缺失（Kaggle 原版缺失 19.8%） |
| `number_of_open_credit_lines_and_loans` | NumberOfOpenCreditLinesAndLoans | 未结清信用账户/贷款数 | — |
| `number_of_times_90_days_late` | NumberOfTimes90DaysLate | 逾期 90 天以上次数 | IV=0.48 |
| `number_real_estate_loans_or_lines` | NumberRealEstateLoansOrLines | 房地产贷款/额度数 | — |
| `number_of_time_60_89_days_past_due_not_worse` | NumberOfTime60-89DaysPastDueNotWorse | 逾期 60-89 天次数 | IV=0.26，与另两组逾期高度共线 |
| `number_of_dependents` | NumberOfDependents | 供养人数 | 清洗版无缺失（Kaggle 原版缺失 2.6%） |

## 4. 放置路径与自检

```
data/raw/givesomecredit.arff    ← 文件名须一致（Notebook 按此路径读取）
```

放置后执行 `make check`（仓库根目录）应显示 `✅ 01-python-credit-scoring 数据就绪`；
或直接运行 Notebook，首行输出应为 `(150000, 11) | default rate = 0.0668` 量级。

## 5. 注意事项

- 文件约 7MB，已 gitignore——**不要提交到仓库**（版权归原作者）；
- Notebook 读取的是 ARFF 格式（方式 A 直接得到）；方式 B 得到的是 CSV，需先转换；
- 数据为 2011 年静态样本、无时间戳，无法做严格 OOT 验证（详见项目 README 第 8 节）。
