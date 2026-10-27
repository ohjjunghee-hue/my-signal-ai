import unittest, tempfile, sqlite3
from unittest.mock import patch
import server
class PulseTest(unittest.TestCase):
 def test_no_lookahead(self):
  self.assertIsNone(server.momentum_from_samples(None,(100,200),1))
  self.assertIsNone(server.momentum_from_samples((100,100),(101,200),0))
 def test_rising(self):
  x=server.momentum_from_samples((100,100000),(101,110000),2)
  self.assertEqual(x['change_pct'],1.0)
  self.assertEqual(x['acceleration_pct_per_min'],.5)
 def test_falling(self):
  self.assertLess(server.momentum_from_samples((100,100),(99,200),1)['change_pct'],0)
 def test_integration(self):
  with tempfile.TemporaryDirectory() as d:
   with patch.object(server,'DB',__import__('pathlib').Path(d)/'test.db'):
    server.db_init()
    def fake(url):
     if 'market/all' in url:return [{'market':'KRW-ABC'}]
     return [{'market':'KRW-ABC','trade_price':100 if self.counter==0 else 101,'acc_trade_price_24h':100000 if self.counter==0 else 120000,'signed_change_rate':.03}]
    self.counter=0
    self.assertEqual(server.pulse_once(1000,fake),[])
    self.counter=1
    found=server.pulse_once(1060,fake)
    self.assertEqual(found[0]['market'],'KRW-ABC')
    self.assertEqual(found[0]['change_pct'],1)
if __name__=='__main__':unittest.main()
