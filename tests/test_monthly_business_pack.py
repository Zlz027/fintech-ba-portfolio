"""P4 月度经营分析包：模拟平台财务函数库不变量测试。

覆盖量价分解恒等式、Holt 预测、预测区间、现金跑道、融资缺口、三情景损益。
所有用例基于固定种子，不依赖 Notebook 产物（P4 本身无需外部数据）。
"""
import numpy as np

from conftest import load_finance

fin = load_finance("04-monthly-business-pack")


class TestPVVariance:
    """中值法量价分解：恒等式 价差 + 量差 = 总收入差异。"""

    def test_identity_holds(self):
        p_b, q_b, p_a, q_a = 100.0, 1000.0, 95.0, 1100.0
        d = fin.pv_variance(p_b, q_b, p_a, q_a)
        assert abs((d["price_effect"] + d["volume_effect"]) - (p_a * q_a - p_b * q_b)) < 1e-6
        assert abs(d["total"] - (p_a * q_a - p_b * q_b)) < 1e-6

    def test_pure_price_change(self):
        """量不变时，全部差异归价差。"""
        d = fin.pv_variance(100.0, 1000.0, 110.0, 1000.0)
        assert abs(d["volume_effect"]) < 1e-6
        assert d["price_effect"] > 0

    def test_pure_volume_change(self):
        """价不变时，全部差异归量差。"""
        d = fin.pv_variance(100.0, 1000.0, 100.0, 1200.0)
        assert abs(d["price_effect"]) < 1e-6
        assert d["volume_effect"] > 0

    def test_sign_reflects_direction(self):
        d = fin.pv_variance(100.0, 1000.0, 90.0, 1000.0)
        assert d["price_effect"] < 0


class TestHoltForecast:
    """Holt 线性指数平滑：形状、可复现、与常数序列的一致性。"""

    def test_returns_point_and_resid(self):
        """holt_forecast 返回 (点预测, 残差序列)。"""
        y = np.arange(1, 53, dtype=float)
        point, resid = fin.holt_forecast(y, alpha=0.1, beta=0.25, h=13)
        assert len(point) == 13
        assert len(resid) == len(y) - 1

    def test_constant_series_flat(self):
        """常数序列的水平分量应完全平滑，预测值等于该常数。"""
        y = np.full(52, 100.0)
        point, _ = fin.holt_forecast(y, alpha=0.3, beta=0.1, h=5)
        assert np.allclose(point, 100.0, atol=1e-6)

    def test_fit_holt_reproducible(self):
        _, weekly, _ = fin.simulate_company(seed=42)
        a1 = fin.fit_holt(weekly["net_cf"].values, h=13)
        a2 = fin.fit_holt(weekly["net_cf"].values, h=13)
        assert np.allclose(a1[0], a2[0])
        assert a1[2] == a2[2] and a1[3] == a2[3]

    def test_fit_holt_returns_four(self):
        """fit_holt 返回 (点预测, 残差, alpha, beta)。"""
        _, weekly, _ = fin.simulate_company(seed=42)
        out = fin.fit_holt(weekly["net_cf"].values, h=13)
        assert len(out) == 4
        assert 0 < out[2] < 1 and 0 < out[3] < 1

    def test_trend_follows_direction(self):
        """下降序列的预测应继续下降。"""
        y = np.linspace(100, 50, 52)
        point, _ = fin.holt_forecast(y, alpha=0.5, beta=0.5, h=10)
        assert point[-1] < point[0]


class TestForecastBand:
    """80% 预测区间 = ±z·σ√h，随提前期扩大。"""

    def test_width_grows_with_horizon(self):
        point = np.zeros(13)
        lo, hi = fin.forecast_band(point, sigma=100.0)
        widths = hi - lo
        assert np.all(np.diff(widths) > 0)

    def test_symmetric(self):
        point = np.full(5, 50.0)
        lo, hi = fin.forecast_band(point, sigma=10.0)
        assert np.allclose(hi - point, point - lo)

    def test_z_factor(self):
        point = np.zeros(1)
        lo, hi = fin.forecast_band(point, sigma=100.0, z=1.2816)
        assert abs(hi[0] - 1.2816 * 100.0) < 1e-9


class TestCashRunwayAndGap:
    """现金跑道（累计）与融资缺口（缓冲 − 最低现金，下限 0）。"""

    def test_runway_cumulative(self):
        """cash_runway 返回 起点 + 逐周累计（长度 = len(cf) + 1）。"""
        cf = np.array([100.0, -50.0, -50.0])
        bal = fin.cash_runway(cf, opening_cash=1000.0)
        assert np.allclose(bal, [1000.0, 1100.0, 1050.0, 1000.0])
        assert len(bal) == len(cf) + 1

    def test_gap_positive_when_below_buffer(self):
        assert abs(fin.funding_gap(80.0, 3000.0) - 2920.0) < 1e-9

    def test_gap_zero_when_above_buffer(self):
        assert fin.funding_gap(5000.0, 3000.0) == 0.0

    def test_gap_nonnegative(self):
        assert fin.funding_gap(-100.0, 3000.0) >= 0


class TestScenarioPL:
    """三情景损益：Bull > Base > Bear。"""

    # 取自 Notebook 末月真实基准（模拟 seed=42 的 2024-12）：
    # 放款量 9902、净收入率 1.906%、获客 50.9/9902、信用损失 55.7/9902、运营 60.1（单位：万元）
    BASE = dict(q0=9902.0, p0=0.01906, cac0=50.9 / 9902, loss0=55.7 / 9902,
                opex0=60.1, months=12)

    def _pl(self, g_q, mults):
        return fin.scenario_pl(g_q=g_q, mults=mults, **self.BASE)

    def test_returns_dataframe_with_months(self):
        df = self._pl(0.015, {"volume": 1.0, "nim": 1.0, "cac": 1.0, "loss": 1.0})
        assert len(df) == 12
        assert {"month", "volume", "revenue", "opex", "op_profit"}.issubset(df.columns)

    def test_base_positive_profit(self):
        df = self._pl(0.015, {"volume": 1.0, "nim": 1.0, "cac": 1.0, "loss": 1.0})
        assert df["op_profit"].sum() > 0

    def test_ordering(self):
        bull = self._pl(0.025, {"volume": 1.0, "nim": 1.05, "cac": 0.9, "loss": 0.85})
        base = self._pl(0.015, {"volume": 1.0, "nim": 1.0, "cac": 1.0, "loss": 1.0})
        bear = self._pl(0.005, {"volume": 1.0, "nim": 0.92, "cac": 1.1, "loss": 1.3})
        assert bull["op_profit"].sum() > base["op_profit"].sum() > bear["op_profit"].sum()

    def test_bear_weaker_than_base(self):
        base = self._pl(0.015, {"volume": 1.0, "nim": 1.0, "cac": 1.0, "loss": 1.0})
        bear = self._pl(0.005, {"volume": 1.0, "nim": 0.92, "cac": 1.1, "loss": 1.3})
        assert bear["op_profit"].sum() < base["op_profit"].sum()

    def test_higher_growth_raises_revenue(self):
        lo = self._pl(0.005, {"volume": 1.0, "nim": 1.0, "cac": 1.0, "loss": 1.0})
        hi = self._pl(0.030, {"volume": 1.0, "nim": 1.0, "cac": 1.0, "loss": 1.0})
        assert hi["revenue"].sum() > lo["revenue"].sum()

    def test_nim_multiplier_moves_profit(self):
        """NIM 收紧（<1）应压低利润。"""
        base = self._pl(0.015, {"volume": 1.0, "nim": 1.0, "cac": 1.0, "loss": 1.0})
        tight = self._pl(0.015, {"volume": 1.0, "nim": 0.90, "cac": 1.0, "loss": 1.0})
        assert tight["op_profit"].sum() < base["op_profit"].sum()


class TestSimulateCompany:
    """模拟平台：固定种子可复现、回收系数影响现金。"""

    def test_reproducible(self):
        _, w1, _ = fin.simulate_company(seed=42)
        _, w2, _ = fin.simulate_company(seed=42)
        assert np.allclose(w1["net_cf"].values, w2["net_cf"].values)

    def test_different_seed_differs(self):
        _, w1, _ = fin.simulate_company(seed=42)
        _, w2, _ = fin.simulate_company(seed=43)
        assert not np.allclose(w1["net_cf"].values, w2["net_cf"].values)

    def test_lower_recovery_lowers_cash(self):
        """回收系数越低，13 周后的现金余额越低。"""
        _, w_hi, op_hi = fin.simulate_company(seed=42, recovery_rate=0.95)
        _, w_lo, op_lo = fin.simulate_company(seed=42, recovery_rate=0.88)
        pt_hi, _, _, _ = fin.fit_holt(w_hi["net_cf"].values, h=13)
        pt_lo, _, _, _ = fin.fit_holt(w_lo["net_cf"].values, h=13)
        assert fin.cash_runway(pt_lo, op_lo)[-1] < fin.cash_runway(pt_hi, op_hi)[-1]
