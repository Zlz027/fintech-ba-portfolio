# 数据说明 · P3 欺诈检测（Credit Card Fraud Detection）

> 本目录存放**原始数据**（已 gitignore，不随仓库分发）。数据来源、获取方式、字段含义见本文；
> 拿到文件后按下方路径放置即可复跑 Notebook，无需改任何代码。

## 1. 数据来源

| 项 | 内容 |
|---|---|
| 数据集 | **Credit Card Fraud Detection**（Kaggle 公开版） |
| 原始出处 | Kaggle `mlg-ulb/creditcardfraud`（ULB 机器学习小组发布） |
| 规模 | 284,807 笔交易 × 30 字段，约 **144MB**（三个数据集中最大的一个） |
| 许可与版权 | 版权归 ULB / Kaggle；仅作学习与方法论演示，不作商业用途 |

## 2. 获取方式

```bash
pip install kaggle          # 先配置 ~/.kaggle/kaggle.json
kaggle datasets download -d mlg-ulb/creditcardfraud -p data/raw/
# 解压后确认文件名为 creditcard.csv
```

或直接运行仓库根目录的 `make fetch-data`（交互式指引，不自动下载）。

> **网络受限时的替代**：不看数据也能评估项目——README 已嵌 4 张图与全部结论数字，
> `images/` 与 `outputs/` 产物随仓库分发；离线版可直接打开 `fintech-ba-portfolio-完整版.html`。

## 3. 字段含义（30 列）

| 字段 | 含义 | 本项目口径 |
|---|---|---|
| `Time` | 交易发生秒数（跨度约 48 小时，2013 年欧洲持卡人） | **时序切分依据**（前 80% 训练 / 后 20% 测试）；禁随机切分 |
| `V1`–`V28` | PCA 脱敏特征（28 个主成分） | 无业务含义；V14/V4/V12 为 SHAP 三大因子 |
| `Amount` | 交易金额（欧元） | 成本矩阵输入（漏判成本 = 金额 + ¥50） |
| `Class` | 是否欺诈（1=是） | **目标变量**，492 笔、占比 0.172% |

## 4. 放置路径与自检

```
data/raw/creditcard.csv    ← 文件名须一致（Notebook 按此路径读取）
```

放置后执行 `make check`（仓库根目录）应显示 `✅ 03-python-fraud-threshold 数据就绪`；
或直接运行 Notebook，首行输出应为 `(284807, 31) | fraud rate = 0.0017` 量级
（31 列为原始 30 列 + Notebook 生成的标签列）。

## 5. 注意事项

- 文件约 144MB，已 gitignore——**不要提交到仓库**；
- 欺诈金额集中于极小值（大量 ¥1 交易，测试集欺诈均值仅 ¥103），这是最优阈值高达
  0.5388 的直接原因（详见项目 README 第 5 节）；
- 数据集为 2013 年欧洲两天交易，PCA 特征无业务含义，SHAP 规则仅作方法演示。
