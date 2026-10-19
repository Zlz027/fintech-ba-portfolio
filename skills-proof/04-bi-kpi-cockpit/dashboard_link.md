<!--
⚠️ 上传前待办：把本文件两处【yourname】/【FintechBADashboard】换成发布后地址栏的真实链接（与 README.md 保持一致）。
-->

# 看板直达链接

- **Tableau Public 链接**：
  https://public.tableau.com/app/profile/【yourname】/viz/【FintechBADashboard】/Overview
  （yourname = 你的 Tableau Public 用户名；直接用发布后地址栏复制的链接最稳）

## 打开方式
1. 电脑浏览器直接点上面的链接（推荐 Chrome / Edge）
2. 无需注册、无需登录，打开即看
3. 首次加载需几秒；公司网络受限时可用手机流量打开验证

## 看板内容导览

![看板全貌](images/dashboard_overview.png)

- 顶部指标卡：CV AUC / 挽留 ROI / 欺诈节省成本 / 融资缺口
- 第二排五图：P1 通过率-坏账率-利润率曲线、P3 成本-阈值曲线（对数轴）、P2 优先挽留散点、P4 13 周现金流（Base 口径）、三情景利润条形图
- 筛选器：风险分层、合同类型（作用于 P2 散点）、情景（作用于三情景条形图）

## 数据更新方式
1. 更新 `data/` 下 CSV，或重跑 `scripts/build_bi_tables.py`
2. Tableau Public 桌面版打开工作簿 → `数据 > 刷新所有数据源` → 核对数字
3. `文件 > 保存到 Tableau Public`（**标题不变即覆盖，链接不变**）→ 看板内容更新
