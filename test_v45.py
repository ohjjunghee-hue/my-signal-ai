import sqlite3,unittest
import outcome_validation as ov
class TrialTests(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:');ov.init(self.db)
 def tearDown(self):self.db.close()
 def seed(self,ts=1000000,market='KRW-X',signal='BUY'):
  ov.record(self.db,[{'market':market,'name':'시험','status':signal,'price':100,'stop':97,'change24':1,'score':75,'buy_suitability':100}],ts)
 def test_first_price_immutable(self):
  self.seed();ov.record(self.db,[{'market':'KRW-X','status':'BUY','price':130}],1000100)
  self.assertEqual(ov.report(self.db)['rows'][0]['entry'],100)
 def test_no_same_scan_hit(self):
  self.seed();self.assertEqual(ov.report(self.db)['rows'][0]['observations'],0)
 def test_threshold_and_stop(self):
  self.seed();ov.observe(self.db,[{'market':'KRW-X','trade_price':110}],1000120)
  ov.observe(self.db,[{'market':'KRW-X','trade_price':96}],1000240)
  row=ov.report(self.db)['rows'][0];self.assertEqual(row['first_event'],'TP3');self.assertIsNotNone(row['hits']['10']);self.assertIsNotNone(row['stop_ts'])
 def test_milestone_first_after(self):
  self.seed();ov.observe(self.db,[{'market':'KRW-X','trade_price':102}],1000299)
  ov.observe(self.db,[{'market':'KRW-X','trade_price':103}],1000305)
  ov.observe(self.db,[{'market':'KRW-X','trade_price':110}],1000400)
  self.assertEqual(ov.report(self.db)['rows'][0]['milestones']['5m']['price'],103)
 def test_gap_flag(self):
  self.seed();ov.observe(self.db,[{'market':'KRW-X','trade_price':101}],1000600)
  self.assertTrue(ov.report(self.db)['rows'][0]['gap_warning'])
 def test_separate_pre_buy(self):
  self.seed(signal='PRE');self.seed(signal='BUY')
  self.assertEqual(len(ov.report(self.db)['rows']),2)
 def test_complete(self):
  self.seed();ov.observe(self.db,[{'market':'KRW-X','trade_price':110}],1000000+72*3600)
  self.assertEqual(ov.report(self.db)['summary']['completed_returned'],1)
 def test_no_fake_hit_on_missing_price(self):
  self.seed();ov.observe(self.db,[],1000600)
  self.assertIsNone(ov.report(self.db)['rows'][0]['hits']['3'])
 def test_invalid_entry(self):
  ov.record(self.db,[{'market':'KRW-X','status':'BUY','price':float('nan')}],1000000)
  self.assertEqual(len(ov.report(self.db)['rows']),0)
if __name__=='__main__':unittest.main()
