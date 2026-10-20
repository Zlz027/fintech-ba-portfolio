# 数据说明 · P2 客户流失预测（IBM Telco Customer Churn）

> 本目录存放**原始数据**（已 gitignore，不随仓库分发）。数据来源、获取方式、字段含义见本文；
> 拿到文件后按下方路径放置即可复跑 Notebook，无需改任何代码。

## 1. 数据来源

| 项 | 内容 |
|---|---|
| 数据集 | **IBM Telco Customer Churn**（IBM 公开样本数据集） |
| 原始出处 | IBM Business Analytics 社区博客（Steven Macko，2019-07-11）；Kaggle `blastchar/telco-customer-churn` 为同源副本 |
| 规模 | 7,043 名客户 × 21 字段，约 1MB |
| 许可与版权 | 版权归 IBM / Kaggle；仅作学习与方法论演示，不作商业用途 |

## 2. 获取方式（二选一）

**方式 A——Kaggle（需账号 + API token）：**

```bash
pip install kaggle          # 先配置 ~/.kaggle/kaggle.json
kaggle datasets download -d blastchar/telco-customer-churn -p data/raw/
# 解压后确认文件名为 Telco-Customer-Churn.csv
```

**方式 B——IBM 原始源：** 从 [IBM 社区博客页面](https://community.ibm.com/community/user/businessanalytics/blogs/steven-macko/2019/07/11/telco-customer-churn-1113) 下载 `Telco-Customer-Churn.xlsx` 后另存为 CSV。

或直接运行仓库根目录的 `make fetch-data`（交互式指引，不自动下载）。

## 3. 字段含义（21 列）

| 字段 | 含义 | 本项目口径 |
|---|---|---|
| `customerID` | 客户编号 | 主键，不入模 |
| `gender` | 性别 | One-Hot |
| `SeniorCitizen` | 是否老年客户（0/1） | One-Hot |
| `Partner` | 是否有伴侣 | One-Hot |
| `Dependents` | 是否有被抚养人 | One-Hot |
| `tenure` | 在网月数 | Cox PH 的时长变量；RFM 的 R 代理；cohort 划分依据 |
| `PhoneService` | 是否开通电话服务 | One-Hot |
| `MultipleLines` | 是否多线 | One-Hot |
| `InternetService` | 互联网服务类型（DSL/Fiber/None） | One-Hot；Fiber optic 风险比 1.54 |
| `OnlineSecurity` 等 6 个增值服务字段 | 增值服务订阅情况 | One-Hot；RFM 的 F 代理（订阅数） |
| `Contract` | 合同类型（月约/年约/两年约） | 第一驱动；月约客户留存曲线最陡 |
| `PaperlessBilling` | 是否电子账单 | One-Hot |
| `PaymentMethod` | 付费方式 | Electronic check 风险比 1.41 |
| `MonthlyCharges` | 月费（元） | RFM 的 M 代理（ARPU）；LTV 计算基数 |
| `TotalCharges` | 累计总费用 | **11 条空值均为在网 0 个月新客户，按 0 处理** |
| `Churn` | 是否流失（Yes/No） | **目标变量**（转 0/1），整体流失率 26.54% |

## 4. 放置路径与自检

```
data/raw/Telco-Customer-Churn.csv    ← 文件名须一致（Notebook 按此路径读取）
```

放置后执行 `make check`（仓库根目录）应显示 `✅ 02-python-churn-ltv 数据就绪`；
或直接运行 Notebook，首行输出应为 `(7043, 21) | churn rate = 0.2654` 量级。

## 5. 注意事项

- 数据集为**观察期末快照、无事件时间戳**：主切分为分层随机 80/20，另按在网月数分 cohort
  报告 AUC/KS 作为时序稳定性代理（详见项目 README 第 2、4 节）；
- 文件约 1MB，已 gitignore——**不要提交到仓库**；
- `TotalCharges` 在原始 CSV 中以空字符串表示缺失，Notebook 已按 0 处理，无需手工清洗。
