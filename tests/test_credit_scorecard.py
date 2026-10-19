"""P1 信用风险-定价联动：财务函数库不变量测试。

覆盖 blocks：
- 评分刻度（PDO 定义、锚点）
- 盈亏平衡利率公式（口径 A）
- 风险定价 + 上限截断
- PSI 稳定性
- 统一定价的交叉补贴方向
"""
import numpy as np
import pytest

from conftest import load_finance

fin = load_finance("01-credit-scorecard")

# 与 analysis.py / README 5.2 保持一致的基准假设
LGD, FUND, OPEX, TGT, CAP, EAD = 0.75, 0.03, 0.02, 0.02, 0.24, 10_000.0


class TestScoreMapping:
    """评分刻度：Score = offset + factor × ln(odds_good)。"""

    def test_anchor_maps_to_base(self):
        """好坏比 50:1 应恰好映射到 600 分。"""
        factor, offset = fin.score_mapping(50, 600, 20)
        score = fin.prob_to_score(np.array([1 / 51]), factor, offset)
        assert abs(score[0] - 600) < 1e-6

    def test_pdo_doubles_odds(self):
        """每 PDO=20 分，好坏比翻一倍。"""
        factor, offset = fin.score_mapping(50, 600, 20)
        p1 = 1 / 51                      # odds 50
        p2 = 1 / 101                     # odds 100（翻倍）
        s1 = fin.prob_to_score(np.array([p1]), factor, offset)[0]
        s2 = fin.prob_to_score(np.array([p2]), factor, offset)[0]
        assert abs((s2 - s1) - 20) < 1e-6

    def test_score_monotone_decreasing_in_pd(self):
        """PD 越高，得分越低。"""
        factor, offset = fin.score_mapping(50, 600, 20)
        s = fin.prob_to_score(np.array([0.01, 0.05, 0.2, 0.5]), factor, offset)
        assert np.all(np.diff(s) < 0)


class TestBreakevenRate:
    """盈亏平衡利率 r* = (PD×LGD + funding + opex) / (1 − PD)。"""

    def test_formula_identity(self):
        pd_ = np.array([0.01, 0.05, 0.20])
        r = fin.breakeven_rate(pd_, LGD, FUND, OPEX)
        expect = (pd_ * LGD + FUND + OPEX) / (1 - pd_)
        assert np.allclose(r, expect)

    def test_zero_pd_equals_cost_floor(self):
        """PD=0 时 r* 应等于资金+运营成本（无风险至少覆盖成本）。"""
        r = fin.breakeven_rate(np.array([1e-9]), LGD, FUND, OPEX)[0]
        assert abs(r - (FUND + OPEX)) < 1e-6

    def test_increasing_in_pd(self):
        r = fin.breakeven_rate(np.array([0.01, 0.1, 0.3, 0.6]), LGD, FUND, OPEX)
        assert np.all(np.diff(r) > 0)

    def test_high_pd_explodes(self):
        """PD→1 时保本利率爆炸，佐证"不可定价尾部"的存在。"""
        r = fin.breakeven_rate(np.array([0.97]), LGD, FUND, OPEX)[0]
        assert r > 10                     # >1000%


class TestPriceBook:
    """风险定价与单客户损益（口径 A）。"""

    def test_rate_capped(self):
        """建议利率不得超过合规上限 24%。"""
        pd_ = np.array([0.01, 0.3, 0.9])
        r, _ = fin.price_book(pd_, np.full(3, EAD), LGD, FUND, OPEX, TGT, CAP)
        assert np.all(r <= CAP + 1e-12)

    def test_untouched_rate_equals_star_plus_margin(self):
        """未触顶客户的利率 = r* + 目标利润率。"""
        pd_ = np.array([0.001])
        r, _ = fin.price_book(pd_, np.array([EAD]), LGD, FUND, OPEX, TGT, CAP)
        star = fin.breakeven_rate(pd_, LGD, FUND, OPEX)[0]
        assert abs(r[0] - (star + TGT)) < 1e-12

    def test_profit_positive_when_not_capped(self):
        """未触顶时客户应盈利（目标利润率按生存概率折算）。"""
        pd_ = np.array([0.01, 0.02, 0.05])
        _, profit = fin.price_book(pd_, np.full(3, EAD), LGD, FUND, OPEX, TGT, CAP)
        assert np.all(profit > 0)

    def test_capped_customer_loses_money(self):
        """触顶的高 PD 客户应亏损——这正是要拒贷的尾部。"""
        pd_ = np.array([0.9])
        r, profit = fin.price_book(pd_, np.array([EAD]), LGD, FUND, OPEX, TGT, CAP)
        assert abs(r[0] - CAP) < 1e-12
        assert profit[0] < 0


class TestFlatRateBaseline:
    """统一定价基准：应体现交叉补贴（高 PD 亏、低 PD 赚）。"""

    def test_flat_rate_uses_pool_mean_pd(self):
        pd_ = np.array([0.01, 0.05, 0.20])
        r_flat, _ = fin.flat_rate_baseline(pd_, LGD, FUND, OPEX, TGT, CAP)
        star = fin.breakeven_rate(np.array([pd_.mean()]), LGD, FUND, OPEX)[0]
        assert abs(r_flat - min(CAP, star + TGT)) < 1e-12

    def test_cross_subsidy_direction(self):
        """统一定价下，低 PD 客户盈利、高 PD 客户亏损。"""
        pd_ = np.array([0.005, 0.5])
        _, profit = fin.flat_rate_baseline(pd_, LGD, FUND, OPEX, TGT, CAP)
        assert profit[0] > profit[1]


class TestPSI:
    """PSI 稳定性：同分布 PSI≈0，漂移分布 PSI 显著为正。"""

    def test_same_distribution_near_zero(self):
        rng = np.random.default_rng(42)
        x = rng.normal(size=5000)
        val, _ = fin.psi(x, rng.normal(size=5000))
        assert val < 0.02

    def test_shifted_distribution_large(self):
        rng = np.random.default_rng(42)
        expected = rng.normal(0, 1, size=5000)
        actual = rng.normal(2, 1, size=5000)      # 均值平移 2σ
        val, _ = fin.psi(expected, actual)
        assert val > 0.25                          # 显著漂移告警线

    def test_nonnegative(self):
        rng = np.random.default_rng(0)
        val, _ = fin.psi(rng.normal(size=2000), rng.normal(size=2000))
        assert val >= 0
