import unittest
from server import diagnose_signals,select_deep_markets

class TestV42(unittest.TestCase):
 def test_acceleration_prioritized(self):
  rows=[{'market':f'KRW-{i}','acc_trade_price_24h':100-i,'signed_change_rate':0} for i in range(20)]
  chosen,sources=select_deep_markets(rows,8,0,accelerators=[{'market':'KRW-19'}])
  self.assertIn('KRW-19',[x['market'] for x in chosen])
  self.assertEqual(sources['KRW-19'],'단기 가격 가속 감시')
 def test_no_duplicate_markets(self):
  rows=[{'market':f'KRW-{i}','acc_trade_price_24h':100-i,'signed_change_rate':0} for i in range(20)]
  chosen,_=select_deep_markets(rows,8,0,pinned=['KRW-19'],accelerators=[{'market':'KRW-19'}])
  self.assertEqual(len(chosen),len(set(x['market'] for x in chosen)))
 def test_diagnostics_counts(self):
  rows=[{'status':'WAIT','risk':['과열'],'opportunity':{'eligible':False,'reason':'저항'}},{'status':'BUY','risk':[],'opportunity':{'eligible':True}}]
  d=diagnose_signals(rows,[])
  self.assertEqual(d['status_counts']['BUY'],1)
  self.assertEqual(d['rejection_reasons']['과열'],1)
  self.assertEqual(d['rejection_reasons']['저항'],1)
 def test_empty(self):
  self.assertEqual(diagnose_signals([],[])['analyzed'],0)
if __name__=='__main__':unittest.main()
