import unittest
from historical_gate_failure_summary import summarize_missed_surge_gates

class GateSummaryTests(unittest.TestCase):
    def test_percentages_have_eligible_denominators(self):
        d={'3':{'records':[{'status':'BASE_BUY_MISSED','eligible_evaluations':13,
                           'failed_gate_counts':{'breakout':12,'volume':9}}]}}
        r=summarize_missed_surge_gates(d)
        self.assertEqual(r['rows'][0]['failed_pct'],92.31)
        self.assertEqual(r['rows'][1]['failed_pct'],69.23)
    def test_unevaluable_events_excluded(self):
        d={'3':{'records':[{'status':'NO_ELIGIBLE_LOOKBACK','eligible_evaluations':0,'failed_gate_counts':{}}]}}
        self.assertEqual(summarize_missed_surge_gates(d)['rows'],[])
    def test_invalid_counts_rejected(self):
        d={'3':{'records':[{'status':'BASE_BUY_MISSED','eligible_evaluations':2,'failed_gate_counts':{'x':3}}]}}
        with self.assertRaises(ValueError):summarize_missed_surge_gates(d)
if __name__=='__main__':unittest.main()
