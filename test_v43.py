import unittest
from server import diagnose_signals
class DiagnosticsTests(unittest.TestCase):
 def test_gate_counts_and_near_misses(self):
  rows=[{'market':'KRW-AAA','name':'AAA','status':'WAIT','score':81,'risk':[],'opportunity':{'eligible':False,'reason':'손익비 부족'},'buy_gates':{'돌파':True,'거래량':False,'추세':True}}, {'market':'KRW-BBB','status':'BUY','buy_gates':{'돌파':True,'거래량':True,'추세':True},'risk':[],'opportunity':{'eligible':True}}]
  d=diagnose_signals(rows,[])
  self.assertEqual(d['gate_evaluated'],2)
  self.assertEqual(d['gate_fail_counts']['거래량'],1)
  self.assertEqual(d['near_misses'][0]['market'],'KRW-AAA')
  self.assertEqual(d['status_counts']['BUY'],1)
 def test_missing_candles(self):
  d=diagnose_signals([{'status':'DATA','risk':[],'opportunity':{}}],['timeout'])
  self.assertEqual(d['gate_evaluated'],0)
  self.assertEqual(d['request_errors'],1)
