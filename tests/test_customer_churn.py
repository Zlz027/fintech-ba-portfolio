"""P2 客户流失-留存经济性：财务函数库不变量测试。

覆盖 KM 生存函数、折现 LTV、挽留 ROI 曲线、收入风险敞口（RaR）。
所有用例基于合成数据，不依赖 Notebook 产物。
"""
import numpy as np

from conftest import load_finance

fin = load_finance("02-customer-churn")


def _km_sample(seed=1, n=800, max_time=72):
    """生成一组合成生存数据并返回 KM 曲线。"""
    rng = np.random.default_rng(seed)
    times = rng.integers(1, max_time + 1, size=n)
    events = rng.integers(0, 2, size=n)
    return fin.km_survival(times, events)


class TestKMSurvival:
    """Kaplan-Meier 生存函数：单调不增、起点接近 1。"""

    def test_starts_near_one(self):
        t, s = _km_sample()
        assert s[0] <= 1.0 and s[0] > 0.8

    def test_monotone_nonincreasing(self):
        _, s = _km_sample(seed=42)
        assert np.all(np.diff(s) <= 1e-12)

    def test_all_censored_stays_flat(self):
        """全部删失（无流失事件）时生存率应恒为 1。"""
        times = np.arange(1, 11)
        events = np.zeros(10, dtype=int)
        _, s = fin.km_survival(times, events)
        assert np.allclose(s, 1.0)


class TestExpectedRemainingMonths:
    """期望剩余留存月数：随 tenure 增加而非增（越老越接近 horizon 上限）。"""

    def test_bounded_by_horizon(self):
        t, s = _km_sample()
        tenure = np.array([0, 12, 36, 60])
        e = fin.expected_remaining_months(tenure, t, s, horizon=36)
        assert np.all(e >= 0) and np.all(e <= 36 + 1e-9)

    def test_nonincreasing_in_tenure(self):
        t, s = _km_sample()
        e = fin.expected_remaining_months(np.array([0, 24, 48, 72]), t, s, horizon=36)
        assert np.all(np.diff(e) <= 1e-9)


class TestDiscountedLTV:
    """折现期望 LTV：随折现率上升而下降、随毛利率上升而上升。"""

    def _ltv(self, **kw):
        t, s = _km_sample(seed=1, n=300)
        tenure = np.arange(1, 301) % 72 + 1
        revenue = np.full(300, 70.0)
        args = dict(monthly_revenue=revenue, tenure=tenure, surv_times=t, surv_probs=s,
                    gross_margin=0.60, annual_discount=0.10, horizon=36)
        args.update(kw)
        return float(np.mean(fin.discounted_ltv(**args)))

    def test_positive(self):
        assert self._ltv() > 0

    def test_decreasing_in_discount_rate(self):
        assert self._ltv(annual_discount=0.25) < self._ltv(annual_discount=0.05)

    def test_increasing_in_margin(self):
        assert self._ltv(gross_margin=0.80) > self._ltv(gross_margin=0.40)


class TestCampaignROI:
    """挽留 ROI 曲线：净收益在拐点见顶、成本线性、ROI 递减。"""

    def setup_method(self):
        rng = np.random.default_rng(7)
        self.p = rng.uniform(0.05, 0.95, size=800)
        self.ltv = rng.uniform(300.0, 2000.0, size=800)

    def test_shapes_consistent(self):
        roi, cost, net = fin.campaign_roi(self.p, self.ltv, uplift=0.30)
        assert roi.shape == cost.shape == net.shape
        assert cost.shape[0] == self.p.shape[0]

    def test_cost_monotone_increasing(self):
        _, cost, _ = fin.campaign_roi(self.p, self.ltv, uplift=0.30)
        assert np.all(np.diff(cost) >= -1e-9)

    def test_cost_step_equals_contact_plus_benefit(self):
        """每多触达一人，成本增加 ¥20+¥50=¥70。"""
        _, cost, _ = fin.campaign_roi(self.p, self.ltv, uplift=0.30,
                                      contact_cost=20.0, benefit_cost=50.0)
        assert abs(cost[0] - 70.0) < 1e-9
        assert abs((cost[10] - cost[9]) - 70.0) < 1e-9

    def test_net_peaks_interior(self):
        """净收益应在中段见顶（存在最优触达规模，而非越多越好）。"""
        _, _, net = fin.campaign_roi(self.p, self.ltv, uplift=0.30)
        peak = int(np.argmax(net))
        assert 0 < peak < len(net) - 1

    def test_roi_decreasing(self):
        """ROI 按收益降序触达必然递减。"""
        roi, _, _ = fin.campaign_roi(self.p, self.ltv, uplift=0.30)
        assert roi[0] >= roi[len(roi) // 2] - 1e-9

    def test_higher_uplift_gives_higher_net(self):
        _, _, net_lo = fin.campaign_roi(self.p, self.ltv, uplift=0.10)
        _, _, net_hi = fin.campaign_roi(self.p, self.ltv, uplift=0.40)
        assert net_hi.max() > net_lo.max()

    def test_zero_uplift_loses_money(self):
        """uplift=0 时无任何保住的客户，净收益恒为负。"""
        _, _, net = fin.campaign_roi(self.p, self.ltv, uplift=0.0)
        assert np.all(net < 0)


class TestRevenueAtRisk:
    """收入风险敞口 RaR = Σ 月费 × 流失概率 × horizon。"""

    def test_formula_identity(self):
        rev = np.array([70.0, 80.0, 90.0])
        p = np.array([0.5, 0.2, 0.1])
        assert abs(fin.revenue_at_risk(rev, p, horizon=12)
                   - float((rev * p * 12).sum())) < 1e-6

    def test_scale_with_horizon(self):
        rev = np.array([100.0])
        p = np.array([0.3])
        assert abs(fin.revenue_at_risk(rev, p, 12)
                   - 2 * fin.revenue_at_risk(rev, p, 6)) < 1e-9
