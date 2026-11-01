import unittest
from historical_missed_surge_diagnostics import missed_surge_gate_diagnostics

class MissedSurgeTests(unittest.TestCase):
    def test_failed_gates_without_buy(self):
        r=missed_surge_gate_diagnostics([{'hit_ts':1200}],
          [{'close_ts':900,'status':'PRE','base_buy_candidate':False,'buy_gates':{'volume':False,'trend':True}}])
        self.assertEqual(r['records'][0]['status'],'BASE_BUY_MISSED')
        self.assertEqual(r['records'][0]['failed_gate_counts'],{'volume':1})
    def test_insufficient_history_is_not_missed_signal(self):
        r=missed_surge_gate_diagnostics([{'hit_ts':1200}],
          [{'close_ts':900,'status':'INSUFFICIENT_HISTORY'}])
        self.assertEqual(r['records'][0]['status'],'NO_ELIGIBLE_LOOKBACK')
    def test_lead_time_excludes_late_buy(self):
        r=missed_surge_gate_diagnostics([{'hit_ts':1200}],
          [{'close_ts':1200,'status':'BUY','base_buy_candidate':True}])
        self.assertEqual(r['records'][0]['status'],'NO_ELIGIBLE_LOOKBACK')
if __name__=='__main__':unittest.main()
