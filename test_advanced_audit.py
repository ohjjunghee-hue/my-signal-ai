import unittest
from advanced_audit import audit
class AuditTests(unittest.TestCase):
 def test_empty(self):
  r,e=audit([]);self.assertEqual(r['nonoverlapping_signals'],0)
 def test_overlap_removed(self):
  rows=[dict(market='KRW-A',t=t,horizon_bars=48,max_gain_pct=11,max_drawdown_pct=-2,signal=1) for t in (1000,1900,46000)]
  r,e=audit(rows);self.assertEqual(len(e),2)
 def test_stop_order_unknown(self):
  r,e=audit([dict(market='KRW-A',t=1000,horizon_bars=48,max_gain_pct=12,max_drawdown_pct=-5,signal=1)])
  self.assertEqual(e[0]['target_10_before_stop'],'unknown')
 def test_cost(self):
  r,e=audit([dict(market='KRW-A',t=1000,horizon_bars=48,max_gain_pct=5,max_drawdown_pct=-1,signal=1)],fee_bps=25)
  self.assertEqual(r['target_3']['net_target_after_cost_pct'],2.5)
 def test_bad_data(self):
  r,e=audit([{'market':'KRW-A'}]);self.assertEqual(r['invalid_rows'],1)
 def test_not_claiming_profit(self):
  r,e=audit([dict(market='KRW-A',t=1000,horizon_bars=48,max_gain_pct=50,max_drawdown_pct=-40,signal=1)])
  self.assertEqual(r['target_50']['unambiguous_possible'],0)
if __name__=='__main__':unittest.main()
