import sqlite3, tempfile, unittest
from pathlib import Path
import server

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.orig=server.DB
        server.DB=Path(self.tmp.name)/'test.sqlite'
        server.db_init()
        self.con=sqlite3.connect(server.DB)
        self.t=1800000000
        self.base={'market':'KRW-TEST','name':'테스트','price':100.0,'entry':100.0,'stop':95.0,'score':85,'change24':1.0,'status':'PRE','tier_rank':1,'decision_reason':'압축'}
        self.ticker=lambda p: [{'market':'KRW-TEST','trade_price':p,'signed_change_rate':0.01}]
    def tearDown(self):
        self.con.close();server.DB=self.orig;self.tmp.cleanup()
    def step(self,result,price,t):
        rows=server.maintain_setups(self.con,[dict(result,price=price)] if result else [],self.ticker(price),t)
        self.con.commit();return rows[0]
    def test_pre_survives_one_weak_analysis(self):
        self.assertEqual(self.step(self.base,100,self.t)['status'],'PRE')
        weak=dict(self.base,status='WATCH',score=63)
        self.assertEqual(self.step(weak,101,self.t+120)['status'],'PRE')
        self.assertEqual(self.step(weak,102,self.t+240)['status'],'WATCH')
        self.assertEqual(self.step(self.base,103,self.t+360)['status'],'PRE')
        self.assertEqual(self.con.execute('select first_seen from active_setups').fetchone()[0],self.t)
    def test_no_buy_from_ticker_only(self):
        self.step(self.base,100,self.t)
        x=self.step(None,104,self.t+60)
        self.assertEqual(x['status'],'PRE')
        self.assertEqual(x['peak_since_pct'],4)
        self.assertIsNone(x['last_signal'])
    def test_buy_then_hold_and_stop(self):
        buy=dict(self.base,status='BUY')
        self.assertEqual(self.step(buy,100,self.t)['status'],'BUY')
        self.assertEqual(self.step(dict(self.base,status='WATCH'),102,self.t+120)['status'],'HOLD')
        self.assertEqual(self.step(None,94,self.t+180)['status'],'STOP')
        self.assertEqual(self.step(buy,96,self.t+240)['status'],'STOP')
    def test_expiry_and_pinned_selection(self):
        self.step(self.base,100,self.t)
        self.assertEqual(server.tracked_priority(self.con,self.t),['KRW-TEST'])
        self.assertEqual(self.step(None,101,self.t+72*3600)['status'],'EXPIRED')
        self.assertEqual(server.tracked_priority(self.con,self.t+72*3600),[])
        tick=[{'market':f'KRW-{i}','acc_trade_price_24h':i,'signed_change_rate':0.01} for i in range(50)]
        tick.append({'market':'KRW-TEST','acc_trade_price_24h':0,'signed_change_rate':0})
        selected,source=server.select_deep_markets(tick,20,0,pinned=['KRW-TEST'])
        self.assertEqual(selected[0]['market'],'KRW-TEST')
        self.assertEqual(source['KRW-TEST'],'기존 후보 지속 추적')
    def test_late_signal_flag(self):
        self.step(dict(self.base,change24=14),100,self.t)
        self.assertTrue(server.read_setups(self.con,self.t)[0]['is_late'])
if __name__=='__main__':unittest.main()
