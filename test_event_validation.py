import unittest
from event_validation import evaluate_trade, report
class ValidationTests(unittest.TestCase):
 def bars(self,values):
  return [dict(t=i*900,c=100 if i==0 else v[2],h=v[0],l=v[1]) for i,v in enumerate(values)]
 def test_target_before_stop(self):
  a=self.bars([(100,100,100),(111,99,110),(102,95,97)])
  self.assertEqual(evaluate_trade(a,0,2)['targets']['10']['status'],'target_first')
 def test_stop_before_target(self):
  a=self.bars([(100,100,100),(101,95,96),(111,99,110)])
  self.assertEqual(evaluate_trade(a,0,2)['targets']['10']['status'],'stop_first')
 def test_same_candle_ambiguous(self):
  a=self.bars([(100,100,100),(111,95,105)])
  self.assertEqual(evaluate_trade(a,0,1)['targets']['10']['status'],'ambiguous_same_candle')
 def test_missing_data_incomplete(self):
  a=self.bars([(100,100,100),(111,99,110)])
  self.assertFalse(evaluate_trade(a,0,2)['complete'])
 def test_gap_incomplete(self):
  a=self.bars([(100,100,100),(111,99,110),(111,99,110)]);a[2]['t']+=900
  self.assertFalse(evaluate_trade(a,0,2)['complete'])
 def test_empty_report(self):
  r,e,m=report({});self.assertIsNone(r['target_10']['target_first_rate_pct'])
if __name__=='__main__':unittest.main()
