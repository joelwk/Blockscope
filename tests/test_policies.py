import unittest
from feesentinel.policies import should_alert_spike, propose_adjustment

class TestPolicies(unittest.TestCase):
    
    def setUp(self):
        self.default_config = {
            "enabled": True,
            "spike_pct": 35,
            "min_alert_satvb": 15,
            "cooldown_minutes": 20,
            "adjustment_rules": {
                "target_sat_vb_floor": 12,
                "bump_pct_if_queue_backlog": 20,
                "drop_pct_if_clearing_fast": 15
            }
        }

    def test_should_alert_spike_basic(self):
        # No alert if disabled
        cfg = self.default_config.copy()
        cfg["enabled"] = False
        self.assertFalse(should_alert_spike(100, 10, cfg))
        
        # Alert if spike > pct
        # 20 -> 30 is 50% increase, > 35%
        self.assertTrue(should_alert_spike(30, 20, self.default_config))
        
        # No alert if spike < pct
        # 20 -> 25 is 25% increase, < 35%
        self.assertFalse(should_alert_spike(25, 20, self.default_config))

    def test_should_alert_spike_thresholds(self):
        # No alert if current < min_alert (even if huge spike)
        # 5 -> 10 is 100% spike, but 10 < 15 (min_alert)
        self.assertFalse(should_alert_spike(10, 5, self.default_config))
        
        # Alert if current >= min_alert
        # 10 -> 20 is 100% spike, 20 > 15
        self.assertTrue(should_alert_spike(20, 10, self.default_config))

    def test_should_alert_spike_edge_cases(self):
        # Division by zero protection (trail_avg <= 0)
        self.assertFalse(should_alert_spike(100, 0, self.default_config))
        self.assertFalse(should_alert_spike(100, -5, self.default_config))

    def test_propose_adjustment_backlog(self):
        # Backlog: current > trail_avg
        current = 20
        trail = 10
        # Bump 20%
        # 20 * 1.2 = 24
        proposal = propose_adjustment(current, trail, self.default_config)
        self.assertEqual(proposal["type"], "policy_adjustment_suggestion")
        self.assertEqual(proposal["suggested_target_sat_vb"], 24)
        self.assertTrue(proposal["basis"]["backlog"])

    def test_propose_adjustment_clearing(self):
        # Clearing: current <= trail_avg
        current = 10
        trail = 20
        # Drop 15%
        # 20 * 0.85 = 17
        proposal = propose_adjustment(current, trail, self.default_config)
        self.assertEqual(proposal["suggested_target_sat_vb"], 17)
        self.assertFalse(proposal["basis"]["backlog"])
        
    def test_propose_adjustment_floor(self):
        # Should never go below target_sat_vb_floor (12)
        current = 5
        trail = 10
        # Drop 15% from 10 = 8.5 -> 8
        # Floor is 12
        proposal = propose_adjustment(current, trail, self.default_config)
        self.assertEqual(proposal["suggested_target_sat_vb"], 12)

if __name__ == '__main__':
    unittest.main()

