"""P3 欺诈检测：成本敏感阈值优化的不变量测试。

覆盖期望成本函数、最优阈值的精确解性质、误杀成本敏感性方向、规则评估、
评分 PSI。所有用例基于合成数据。
"""
import numpy as np

from conftest import load_finance

fin = load_finance("03-python-fraud-threshold")


def _fraud_sample(seed=42, n=5000, fraud_rate=0.005, small_amount=True):
    """构造合成欺诈样本：欺诈概率与标签正相关，欺诈金额偏小。"""
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < fraud_rate).astype(int)
    # 让欺诈样本倾向更高预测概率（AUC>0.5 的可用信号）
    p = np.clip(rng.beta(2, 20, size=n) + y * rng.uniform(0.2, 0.7, size=n), 0, 1)
    amount = rng.uniform(1, 50, size=n) if small_amount else rng.uniform(50, 500, size=n)
    return y, p, amount


class TestExpectedCost:
    """总成本 = FP 数 × fp_cost + Σ漏判 (amount + miss_fixed)。"""

    def test_no_flag_equals_missed_total(self):
        """阈值=1.01（不拦截）时成本 = 全部欺诈金额 + 固定漏判成本。"""
        y, p, amt = _fraud_sample()
        c = fin.expected_cost(y, p, amt, threshold=1.01, fp_cost=120.0, miss_fixed=50.0)
        expect = amt[y == 1].sum() + (y == 1).sum() * 50.0
        assert abs(c - expect) < 1e-6

    def test_flag_all_includes_fp_cost(self):
        """阈值=0（全拦截）时成本至少包含所有好交易的误杀成本。"""
        y, p, amt = _fraud_sample()
        c = fin.expected_cost(y, p, amt, threshold=0.0, fp_cost=120.0, miss_fixed=50.0)
        assert c >= (y == 0).sum() * 120.0 - 1e-6

    def test_cost_nonnegative(self):
        y, p, amt = _fraud_sample()
        for th in [0.0, 0.3, 0.5, 0.9, 1.01]:
            assert fin.expected_cost(y, p, amt, th) >= 0


class TestOptimalThreshold:
    """最优阈值是分段常数成本函数的精确全局最小。"""

    def test_returns_three_tuple(self):
        y, p, amt = _fraud_sample()
        th, cost, curve = fin.optimal_threshold(y, p, amt)
        assert 0.0 <= th <= 1.01
        assert cost >= 0
        assert not curve.empty
        assert {"threshold", "cost", "recall", "flag_rate"}.issubset(curve.columns)

    def test_optimal_beats_neighbors(self):
        """最优阈值处的成本应不高于任意邻近候选阈值。"""
        y, p, amt = _fraud_sample(seed=3)
        th, cost, _ = fin.optimal_threshold(y, p, amt)
        for th2 in np.linspace(0.05, 0.95, 19):
            assert cost <= fin.expected_cost(y, p, amt, th2) + 1e-6

    def test_higher_fp_cost_raises_threshold(self):
        """误杀越贵，越不愿拦截 → 最优阈值应更高（换一组样本避免持平巧合）。"""
        y, p, amt = _fraud_sample(seed=11, n=20000, small_amount=False)
        th_lo, _, _ = fin.optimal_threshold(y, p, amt, fp_cost=10.0)
        th_hi, _, _ = fin.optimal_threshold(y, p, amt, fp_cost=5000.0)
        assert th_hi >= th_lo

    def test_extreme_fp_cost_blocks_nothing(self):
        """误杀成本极高时，最优阈值应落到样本概率的近上界（几乎不拦截）。"""
        y, p, amt = _fraud_sample(seed=5)
        th, _, _ = fin.optimal_threshold(y, p, amt, fp_cost=1e9)
        assert th >= float(np.quantile(p, 0.99)) - 1e-9

    def test_never_raises_above_no_flag_cost(self):
        """最优成本不应超过"完全不拦截"的基准成本。"""
        y, p, amt = _fraud_sample(seed=6)
        _, cost, _ = fin.optimal_threshold(y, p, amt)
        no_flag = fin.expected_cost(y, p, amt, threshold=1.01)
        assert cost <= no_flag + 1e-6

    def test_curve_consistent_with_cost_fn(self):
        """阈值-成本曲线上每一点的成本应与 expected_cost 一致。"""
        y, p, amt = _fraud_sample(seed=8, n=8000)
        _, _, curve = fin.optimal_threshold(y, p, amt)
        row = curve.iloc[len(curve) // 2]
        c = fin.expected_cost(y, p, amt, float(row["threshold"]))
        assert abs(c - float(row["cost"])) < 1e-6


class TestThresholdSensitivity:
    """误杀成本敏感性表：行数匹配、阈值单调不减。"""

    def test_shape_and_monotone(self):
        y, p, amt = _fraud_sample(seed=13, n=10000, small_amount=False)
        costs = [10.0, 120.0, 1000.0]
        tab = fin.threshold_sensitivity(y, p, amt, costs)
        assert len(tab) == 3
        assert {"fp_cost", "best_threshold", "total_cost", "recall"}.issubset(tab.columns)
        assert np.all(np.diff(tab["best_threshold"].values) >= -1e-9)


class TestRuleEval:
    """规则评估：精确率/召回/提升度的定义恒等。"""

    def test_perfect_rule(self):
        y = np.array([0, 0, 1, 1])
        mask = np.array([False, False, True, True])
        r = fin.rule_eval(mask, y)
        assert r["precision"] == 1.0 and r["recall"] == 1.0

    def test_empty_rule(self):
        y = np.array([0, 1, 1])
        r = fin.rule_eval(np.zeros(3, dtype=bool), y)
        assert r["n_flagged"] == 0 and r["tp"] == 0

    def test_lift_identity(self):
        y = np.array([0, 0, 0, 1, 1, 1, 1, 1, 1, 1])
        mask = y == 1
        r = fin.rule_eval(mask, y)
        assert abs(r["lift"] - r["precision"] / y.mean()) < 1e-9


class TestScorePSI:
    """评分 PSI：同分布趋近 0，漂移显著为正。"""

    def test_same_distribution_small(self):
        rng = np.random.default_rng(0)
        x = rng.beta(2, 5, size=5000)
        assert fin.score_psi(x, rng.beta(2, 5, size=5000)) < 0.02

    def test_shifted_large(self):
        rng = np.random.default_rng(1)
        assert fin.score_psi(rng.beta(2, 5, 5000), rng.beta(5, 2, 5000)) > 0.25

    def test_nonnegative(self):
        rng = np.random.default_rng(2)
        assert fin.score_psi(rng.random(2000), rng.random(2000)) >= 0
