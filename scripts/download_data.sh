#!/usr/bin/env bash
# 公开数据集获取指引（P1-P3）
#
# 为什么需要手动做：三个数据集合计约 106MB，且版权与许可属于原作者，
# 故不随仓库分发（.gitignore 已排除 data/raw/* 下的大文件）。
# P4 为固定种子模拟数据，无需任何外部文件。
#
# 用法：bash scripts/download_data.sh
# 作用：检查数据是否就绪，未就绪时打印获取指引（不自动下载，见下方说明）。

set -euo pipefail
cd "$(dirname "$0")/.."

echo "▌ 数据集状态检查"
echo ""

declare -A EXPECTED=(
  ["01-python-credit-scoring/data/raw/givesomecredit.arff"]="P1 Give Me Some Credit（150,000 行 × 11 列，约 7MB）"
  ["02-python-churn-ltv/data/raw/Telco-Customer-Churn.csv"]="P2 IBM Telco Customer Churn（7,043 行 × 21 列，约 1MB）"
  ["03-python-fraud-threshold/data/raw/creditcard.csv"]="P3 Credit Card Fraud Detection（284,807 行 × 30 列，约 144MB）"
)

missing=0
for path in "${!EXPECTED[@]}"; do
  if [ -f "$path" ]; then
    size=$(du -h "$path" | cut -f1)
    echo "  ✅ $path（$size）— ${EXPECTED[$path]}"
  else
    echo "  ⬜ $path — ${EXPECTED[$path]}"
    missing=$((missing + 1))
  fi
done

if [ "$missing" -eq 0 ]; then
  echo ""
  echo "✅ 全部数据就绪，可执行：make all"
  exit 0
fi

echo ""
echo "──────────────────────────────────────────────────────────────"
echo "数据获取指引（$missing 项待获取）"
echo "──────────────────────────────────────────────────────────────"
echo ""
echo "【P1】Give Me Some Credit（Kaggle 竞赛数据集）"
echo "  方式 A（推荐，无需注册）：OpenML 官方接口"
echo "    python3 -c \"from sklearn.datasets import fetch_openml; \\"
echo "      d = fetch_openml(data_id=46929, as_frame=True); \\"
echo "      d.frame.to_csv('01-python-credit-scoring/data/raw/givesomecredit.arff', index=False)\""
echo "    说明：data_id=46929 为 TabArena 清洗版（150,000 行、无缺失异常值），"
echo "          与项目 README 第 2 节口径一致。"
echo ""
echo "  方式 B（Kaggle 原版，需 Kaggle 账号 + API token）："
echo "    pip install kaggle"
echo "    # 把 ~/.kaggle/kaggle.json 放好后执行："
echo "    kaggle competitions download -c GiveMeSomeCredit -p 01-python-credit-scoring/data/raw/"
echo "    注意：Kaggle 原版为 cs-training.csv / cs-test.csv，需自行合并为 arff。"
echo ""
echo "【P2】IBM Telco Customer Churn（公开样本）"
echo "  Kaggle: kaggle datasets download -d blastchar/telco-customer-churn \\"
echo "            -p 02-python-churn-ltv/data/raw/"
echo "  IBM 原始源: https://community.ibm.com/community/user/businessanalytics/blogs/steven-macko/2019/07/11/telco-customer-churn-1113"
echo ""
echo "【P3】Credit Card Fraud Detection（Kaggle，144MB）"
echo "  Kaggle: kaggle datasets download -d mlg-ulb/creditcardfraud \\"
echo "            -p 03-python-fraud-threshold/data/raw/"
echo "  注意：这是三个数据集中最大的一个，下载后确认文件名为 creditcard.csv。"
echo ""
echo "──────────────────────────────────────────────────────────────"
echo "网络受限时的替代方案"
echo "──────────────────────────────────────────────────────────────"
echo ""
echo "  如果无法访问 Kaggle / OpenML（国内网络常见），三条路："
echo ""
echo "  1. 先看结果：GitHub 仓库的 README 已嵌入 16 张图与全部结论数字，"
echo "     images/ 与 outputs/ 目录下的产物都已随仓库分发，不跑也能看完。"
echo ""
echo "  2. 用归档版：解压 fintech-ba-portfolio.zip 后，直接双击打开"
echo "     fintech-ba-portfolio-完整版.html（图片已内嵌，无需数据、无需环境）。"
echo ""
echo "  3. 只跑 P4：P4 为固定种子模拟数据，完全不需要下载任何文件，"
echo "     执行 make p4 即可完整体验「分析 → 图 → 结论」的完整链路。"
echo ""
