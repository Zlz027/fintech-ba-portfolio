# Fintech BA 作品集 · 一键运行入口
#
# 常用命令：
#   make help        显示全部命令
#   make check       检查环境与数据是否就绪（不跑模型）
#   make test        跑 74 个回归测试（约 1 秒，无需数据）
#   make all         依次执行四个项目的 Notebook + 敏感性脚本（约 80 秒）
#   make p1          只跑 P1 信用风险-定价联动
#   make p2          只跑 P2 客户流失-留存经济性
#   make p3          只跑 P3 欺诈检测-阈值优化
#   make p4          只跑 P4 月度经营分析包（无外部数据依赖，最快）
#   make clean       清理执行产物（保留 outputs/ 结果表）
#
# 说明：P1-P3 需要公开数据集，文件已 gitignore，首次使用请先 make fetch-data
#       或按 scripts/download_data.sh 的说明手动放入 data/raw/。

PYTHON ?= python3
PIP    ?= pip3
NBCONV = jupyter nbconvert --to notebook --execute --inplace

P1 := 01-python-credit-scoring
P2 := 02-python-churn-ltv
P3 := 03-python-fraud-threshold
P4 := 04-fp-a-monthly-review

.DEFAULT_GOAL := help
.PHONY: help check test all p1 p2 p3 p4 clean fetch-data install-deps

help: ## 显示可用命令
	@echo ""
	@echo "  Fintech BA 作品集 —— 可用命令"
	@echo "  ────────────────────────────────────────────────"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36mmake %-12s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  首次使用建议：make check → make install-deps → make p4 → make all"
	@echo ""

check: ## 检查环境、依赖与数据是否就绪
	@echo "▌ Python 与依赖"
	@$(PYTHON) --version
	@$(PYTHON) -c "import pandas, numpy, sklearn, matplotlib, seaborn; print('  ✅ 核心依赖已安装')" \
		2>/dev/null || echo "  ❌ 缺少核心依赖，请先执行：make install-deps"
	@echo ""
	@echo "▌ 数据集状态（P1-P3 需公开数据，文件已 gitignore；P4 为模拟数据无需外部文件）"
	@for d in $(P1) $(P2) $(P3); do \
		if [ -n "$$(find $$d/data/raw -type f ! -name .gitkeep 2>/dev/null)" ]; then \
			echo "  ✅ $$d  数据就绪"; \
		else \
			echo "  ⬜ $$d  缺少数据（执行 make fetch-data 获取）"; \
		fi \
	done
	@if [ -n "$$(find $(P4)/data/raw -type f ! -name .gitkeep 2>/dev/null)" ]; then \
		echo "  ✅ $(P4)  数据就绪"; \
	else \
		echo "  ✅ $(P4)  模拟数据（固定种子，无需外部文件，可直接 make p4）"; \
	fi
	@echo ""
	@echo "▌ Notebook 状态"
	@for d in $(P1) $(P2) $(P3) $(P4); do \
		nb=$$(ls $$d/notebooks/*.ipynb 2>/dev/null | head -1); \
		if [ -n "$$nb" ]; then \
			echo "  ✅ $$d/$$(basename $$nb)"; \
		fi; \
	done

install-deps: ## 安装四个项目的依赖（取并集）
	$(PIP) install pandas numpy scikit-learn matplotlib seaborn xgboost shap \
		lifelines imbalanced-learn jupyter nbformat

fetch-data: ## 获取公开数据集（交互式指引，见 scripts/download_data.sh）
	@bash scripts/download_data.sh

test: ## 运行回归测试（74 用例，无需数据，约 1 秒）
	$(PYTHON) -m pytest tests/ -v

all: p1 p2 p3 p4 ## 依次运行四个项目（约 80 秒）
	@echo ""
	@echo "✅ 四个项目全部执行完成，产物见各项目 images/ 与 outputs/"

p1: ## P1 信用风险评分卡 × 风险-定价联动（约 26 秒）
	@cd $(P1) && echo "▌ P1 Notebook…" && $(NBCONV) notebooks/credit_risk_pricing.ipynb
	@cd $(P1) && echo "▌ P1 敏感性脚本…" && $(PYTHON) src/analysis.py

p2: ## P2 客户流失预测 × 留存经济性（约 10 秒）
	@cd $(P2) && echo "▌ P2 Notebook…" && $(NBCONV) notebooks/churn_economics.ipynb
	@cd $(P2) && echo "▌ P2 敏感性脚本…" && $(PYTHON) src/analysis.py

p3: ## P3 欺诈检测 × 成本-收益阈值优化（约 30 秒）
	@cd $(P3) && echo "▌ P3 Notebook…" && $(NBCONV) notebooks/fraud_threshold_optimization.ipynb

p4: ## P4 月度经营分析包（约 9 秒，无外部数据依赖）
	@cd $(P4) && echo "▌ P4 Notebook…" && $(NBCONV) notebooks/monthly_business_pack.ipynb
	@cd $(P4) && echo "▌ P4 敏感性脚本…" && $(PYTHON) src/analysis.py

clean: ## 清理执行缓存（保留 outputs/ 结果表与 images/）
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache 2>/dev/null || true
	@echo "✅ 已清理 Python 缓存（outputs/ 与 images/ 保留）"
