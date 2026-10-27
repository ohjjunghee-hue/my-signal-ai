import unittest,time
from server import parse_rule,chart_signals,build_chart
class TestIntegrated(unittest.TestCase):
 def test_rules(self):
  self.assertEqual(parse_rule('거래량 3배')['kind'],'volume')
  self.assertEqual(parse_rule('5일선이 20일선 돌파')['kind'],'cross')
  self.assertEqual(parse_rule('5일 이격도 103 돌파')['kind'],'disparity')
 def test_invalid(self):
  for x in ['파이썬 실행해','거래량 1000배','3일선이 2일선 돌파']:
   with self.assertRaises(ValueError):parse_rule(x)
 def test_no_future(self):
  bars=[]
  for i in range(80):
   c=100+i*.2;bars.append({'t':i*300,'o':c-.1,'h':c+.4,'l':c-.4,'c':c,'v':100})
  first=chart_signals(bars[:60]);last=chart_signals(bars)
  self.assertEqual(first,[x for x in last if x['t']<bars[60]['t']])
 def test_market_validation(self):
  for m in ['KRW-BTC/../../x','BTC','KRW-!!!']:
   with self.assertRaises(ValueError):build_chart(m,15)
if __name__=='__main__':unittest.main()
