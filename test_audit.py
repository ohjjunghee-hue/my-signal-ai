import unittest,sqlite3,tempfile
import server
class AuditTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old_db=server.DB
  server.DB=__import__('pathlib').Path(self.temp.name)/'test.db';server.db_init()
  self.con=sqlite3.connect(server.DB)
 def tearDown(self):self.con.close();server.DB=self.old_db;self.temp.cleanup()
 def test_first_signal_preserved(self):
  r=[dict(market='KRW-Q',entry=100,status='WATCH',change24=1.2,score=88,selection_source='순환 분석')]
  server.record_outcomes(self.con,r,100000)
  r[0].update(entry=300,change24=200,score=99)
  server.record_outcomes(self.con,r,100100)
  row=server.get_audit_rows(self.con)[0]
  self.assertEqual(row['entry'],100)
  self.assertEqual(row['first_change24'],1.2)
  self.assertEqual(row['verdict'],'초기 관찰 · 성과 미확정')
 def test_late_not_success(self):
  server.record_outcomes(self.con,[dict(market='KRW-Q',entry=300,status='WATCH',change24=211.43)],100000)
  self.assertEqual(server.get_audit_rows(self.con)[0]['verdict'],'후행 발견')
 def test_legacy_record_not_claimed(self):
  self.con.execute("INSERT INTO signal_outcomes(market,day,first_seen,last_seen,entry,last_price,max_pct,min_pct,status,signal_type) VALUES('KRW-Q','2026-01-01',1,1,100,100,50,0,'COMPLETE','관찰')")
  self.assertEqual(server.get_audit_rows(self.con)[0]['verdict'],'기록 부족')
 def test_market_audit_missing_deep(self):
  ticks=[dict(market='KRW-Q',trade_price=200,signed_change_rate=2.11,acc_trade_price_24h=1000),dict(market='KRW-B',trade_price=100,signed_change_rate=.01,acc_trade_price_24h=1000)]
  out=server.audit_market_tickers(self.con,ticks,[],12345)
  self.assertEqual(out[0]['market'],'KRW-Q');self.assertFalse(out[0]['deep_analyzed'])
 def test_no_future_gain(self):
  server.record_outcomes(self.con,[dict(market='KRW-A',entry=100,status='WATCH',change24=1)],100000)
  server.update_outcomes(self.con,[dict(market='KRW-A',trade_price=150)],100000)
  self.assertEqual(server.get_audit_rows(self.con)[0]['max_pct'],0)
if __name__=='__main__':unittest.main()
