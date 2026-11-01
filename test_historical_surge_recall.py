import unittest
from historical_surge_recall import surge_events,compare_candidates,surge_window_coverage
def candles(n=50):
 return [{'ts':i*300,'close':100,'high':100,'open':100,'low':99} for i in range(n)]
class RecallTests(unittest.TestCase):
 def test_independent_denominator(self):
  rows=candles()
  rows[8]['high']=112
  events=surge_events(rows,threshold_pct=10,horizon_bars=10,cooldown_bars=20)
  self.assertGreaterEqual(len(events),1)
  hit=events[0]['hit_ts']
  result=compare_candidates(events,[hit-600],lead_minutes=5)
  self.assertEqual(result['detected'],1)
  self.assertEqual(result['recall_pct'],100)
 def test_late_signal_is_not_early_detection(self):
  rows=candles();rows[8]['high']=112
  events=surge_events(rows,threshold_pct=10,horizon_bars=10,cooldown_bars=20)
  hit=events[0]['hit_ts']
  self.assertEqual(compare_candidates(events,[hit])['detected'],0)
 def test_no_event_is_not_perfect_recall(self):
  self.assertIsNone(compare_candidates([],[])['recall_pct'])
 def test_gap_not_confirmed_event(self):
  rows=candles(12);rows[5]['high']=150
  for x in rows[5:]:x['ts']+=300
  self.assertEqual(surge_events(rows,threshold_pct=10,horizon_bars=10),[])
 def test_coverage_contiguous_windows(self):
  r=surge_window_coverage(candles(12),horizon_bars=10)
  self.assertEqual(r['assessable_windows'],2)
  self.assertEqual(r['unresolved_gap_windows'],0)
 def test_coverage_gap_windows(self):
  rows=candles(12)
  for x in rows[5:]:x['ts']+=300
  r=surge_window_coverage(rows,horizon_bars=10)
  self.assertEqual(r['assessable_windows'],0)
  self.assertEqual(r['unresolved_gap_windows'],2)
  self.assertEqual(r['status'],'NOT_EVALUABLE_HISTORY')
if __name__=='__main__':unittest.main()
