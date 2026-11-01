import unittest
from v49_risk_audit import evaluate_trades
class Tests(unittest.TestCase):
    def test_costs_and_blocked(self):
        r=evaluate_trades([{"market":"A","entry":100,"exit":102,"blocked":False},{"market":"B","entry":100,"exit":95,"blocked":True}],10,10)
        self.assertEqual(r["all_signals"]["count"],2)
        self.assertEqual(r["gate_passed"]["avg_net_pct"],1.6)
        self.assertEqual(r["gate_blocked"]["avg_net_pct"],-5.4)
    def test_invalid_excluded(self):
        r=evaluate_trades([{"entry":0,"exit":1},{"entry":100,"exit":float("nan")}])
        self.assertEqual(r["all_signals"]["count"],0)
        self.assertIsNone(r["all_signals"]["win_rate_pct"])
    def test_no_cost_arbitrage(self):
        with self.assertRaises(ValueError):evaluate_trades([],fee_bps=-1)
if __name__=="__main__":unittest.main()
