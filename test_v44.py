import unittest
from server import analyze, diagnose_signals

class V44Tests(unittest.TestCase):
    def candles(self, n=45, volume=1.0):
        return [{'o':100,'h':101,'l':99,'c':100,'v':volume} for _ in range(n)]
    def test_low_volume_is_not_high_suitability(self):
        r=analyze(self.candles(),self.candles(),self.candles(),100)
        self.assertLessEqual(r['buy_suitability'],39)
        self.assertIn('확정봉 거래량 1.3배 미만',r['suitability_reasons'])
        self.assertEqual(r['status']!='BUY',True)
    def test_score_separate(self):
        r=analyze(self.candles(),self.candles(),self.candles(),100)
        self.assertIn('score',r)
        self.assertIn('buy_suitability',r)
        self.assertEqual(r['buy_gate_total'],9)
    def test_summary(self):
        r=analyze(self.candles(),self.candles(),self.candles(),100)
        r['market']='KRW-TEST'
        d=diagnose_signals([r],[])
        self.assertEqual(d['suitability_summary']['low_volume'],1)
