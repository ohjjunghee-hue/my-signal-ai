import unittest
from historical_replay_readonly import replay,summarize

def bar(ts,o,h,l,c):
 return {"ts":ts,"open":o,"high":h,"low":l,"close":c,"volume":100}
def once(hist):
 return {"stop":95,"target":110} if len(hist)==1 else None

class ReplayTests(unittest.TestCase):
 def test_next_bar_open_no_lookahead(self):
  rows=[bar(1,100,100,100,100),bar(2,103,104,101,102),bar(3,102,112,101,111)]
  result=replay(rows,once)
  self.assertEqual(result[0]["entry"],103)
  self.assertEqual(result[0]["entry_ts"],2)
  self.assertEqual(result[0]["exit_reason"],"TARGET")
  self.assertFalse(result[0]["execution_verified"])
 def test_stop_priority_same_bar(self):
  rows=[bar(1,100,100,100,100),bar(2,100,112,90,100)]
  self.assertEqual(replay(rows,once)[0]["exit_reason"],"STOP")
 def test_gap_down_not_ideal_stop(self):
  rows=[bar(1,100,100,100,100),bar(2,90,92,88,91)]
  t=replay(rows,once)[0]
  self.assertEqual((t["exit_reason"],t["exit"] ),("STOP_GAP",90))
 def test_no_future_bars_to_signal(self):
  seen=[]
  def fn(hist):
   seen.append(len(hist))
   return None
  replay([bar(i,100,101,99,100) for i in range(5)],fn)
  self.assertEqual(seen,[1,2,3,4])
 def test_reject_duplicate_or_invalid(self):
  with self.assertRaises(ValueError):
   replay([bar(1,100,100,100,100)]*2,once)
  with self.assertRaises(ValueError):
   replay([bar(1,100,99,90,100)],once)
 def test_empty_summary(self):
  self.assertIsNone(summarize([])["win_rate_pct"])
if __name__=="__main__":unittest.main()
