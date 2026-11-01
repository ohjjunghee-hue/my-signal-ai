import unittest
from historical_buy_adapter import historical_base_signal
def mk(n,d):
 return [{'ts':i*d,'duration_sec':d,'open':100.,'high':101.,'low':99.,'close':100.,'volume':10.} for i in range(n)]
class AdapterTests(unittest.TestCase):
 def test_only_closed_bars_and_full_day(self):
  a=mk(290,300);b=mk(40,900);c=mk(40,3600)
  called=[]
  def fn(x,y,z,p,change):
   called.append((len(x),len(y),len(z),p,change))
   return {'status':'BUY','entry':p,'stop':90.,'targets':[110.]}
  # 5m candle #288 closes at 86400, 15m #39 closes at 36000, 60m #23 closes at 86400.
  r=historical_base_signal(fn,a,b,c,86400)
  self.assertEqual(r['status'],'INSUFFICIENT_HISTORY') # 288 closed bars, 289 required
  self.assertFalse(called)
  r=historical_base_signal(fn,a,b,c,86700)
  self.assertEqual(r['status'],'INSUFFICIENT_HISTORY') # only 24 closed 60m bars
 def test_base_buy_is_not_live_buy(self):
  a=mk(310,300);b=mk(120,900);c=mk(120,3600)
  def fn(x,y,z,p,change):
   self.assertEqual(len(x),120)
   self.assertEqual(len(y),120)
   self.assertEqual(len(z),35)
   return {'status':'BUY','entry':p,'stop':90,'targets':[110]}
  r=historical_base_signal(fn,a,b,c,126000)
  self.assertTrue(r['base_buy_candidate'])
  self.assertFalse(r['full_live_buy_verified'])
  self.assertTrue(r['reconstructed'])
 def test_missing_five_minute_bar_rejected(self):
  a=mk(310,300);b=mk(120,900);c=mk(120,3600)
  for x in a[100:]:x['ts']+=300
  def fn(*args):raise AssertionError('must not evaluate sparse candles')
  r=historical_base_signal(fn,a,b,c,126000)
  self.assertEqual(r['status'],'INSUFFICIENT_HISTORY')
if __name__=='__main__':unittest.main()
