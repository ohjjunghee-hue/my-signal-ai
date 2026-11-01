import unittest
from paper_exit_audit_readonly import compare_exit

class ExitAuditTests(unittest.TestCase):
    def test_stop_gap_is_worse(self):
        result=compare_exit(6050,5965,6655,5890,"STOP")
        self.assertLess(result["sampled_price_net_pct"],result["ideal_threshold_net_pct"])
        self.assertFalse(result["execution_verified"])
    def test_stress_is_separate(self):
        result=compare_exit(100,95,110,93,"STOP",stress_pct=0.7)
        self.assertAlmostEqual(result["sampled_stress_net_pct"],result["sampled_price_net_pct"]-0.7)
    def test_tp1_is_not_a_fill(self):
        self.assertFalse(compare_exit(100,95,110,111,"TP1")["execution_verified"])
    def test_invalid_levels_rejected(self):
        with self.assertRaises(ValueError):
            compare_exit(100,101,110,90,"STOP")

if __name__=="__main__":
    unittest.main()
