import unittest, tempfile, sqlite3
from server import select_deep_markets,db_init,update_outcomes,record_outcomes,summarize_outcomes
class V35Tests(unittest.TestCase):
 def setUp(self):
  self.t=[{'market':'KRW-'+str(i),'trade_price':100,'acc_trade_price_24h':1000-i,'signed_change_rate':i/1000} for i in range(30)]
 def test_midnight_included(self):
  selected,sources=select_deep_markets(self.t,12,0,[{'market':'KRW-29'}]);self.assertIn('KRW-29',[x['market'] for x in selected]);self.assertEqual(sources['KRW-29'],'자정 급등 감시')
 def test_unique_and_bounded(self):
  a,b=select_deep_markets(self.t,12,0,[{'market':'KRW-0'},{'market':'KRW-0'}]);self.assertEqual(len(a),12);self.assertEqual(len({x['market'] for x in a}),12)
 def test_rotation(self):
  a,_=select_deep_markets(self.t,12,0);b,_=select_deep_markets(self.t,12,1);self.assertNotEqual({x['market'] for x in a},{x['market'] for x in b})
 def test_outcomes_no_future_and_dedupe(self):
  con=sqlite3.connect(':memory:');con.execute('CREATE TABLE signal_outcomes(id INTEGER PRIMARY KEY,market TEXT,day TEXT,first_seen INTEGER,last_seen INTEGER,entry REAL,last_price REAL,max_pct REAL,min_pct REAL,status TEXT,signal_type TEXT,first_change24 REAL,first_score INTEGER,first_source TEXT,first_class TEXT,observations INTEGER DEFAULT 0,UNIQUE(market,day))')
  result=[{'market':'KRW-A','entry':100,'status':'WATCH','opportunity_tier':'관찰'}]
  record_outcomes(con,result,100000);record_outcomes(con,result,100000)
  self.assertEqual(con.execute('select count(*) from signal_outcomes').fetchone()[0],1)
  update_outcomes(con,[{'market':'KRW-A','trade_price':150}],100000)
  self.assertEqual(con.execute('select max_pct from signal_outcomes').fetchone()[0],0)
  update_outcomes(con,[{'market':'KRW-A','trade_price':150}],100001)
  self.assertEqual(con.execute('select max_pct from signal_outcomes').fetchone()[0],50)
  update_outcomes(con,[{'market':'KRW-A','trade_price':90}],100000+73*3600)
  summary=summarize_outcomes(con);self.assertEqual(summary['hit_50'],1);self.assertEqual(summary['completed'],1)
if __name__=='__main__':unittest.main()
