import unittest
from research_engine import feature_at,examples,evaluate,metrics
class ResearchTests(unittest.TestCase):
    def candles(self,n=500):
        return [{'t':i*900,'o':100+i*.01,'h':101+i*.01,'l':99+i*.01,'c':100+i*.01,'v':100} for i in range(n)]
    def test_no_future_leak(self):
        a=self.candles();before=feature_at(a,150)
        for x in a[151:]:x.update(c=100000,h=100001,l=99999,v=999999)
        self.assertEqual(before,feature_at(a,150))
    def test_first_future_candle_not_decision(self):
        a=self.candles();a[97]['h']=200
        r=examples('KRW-TEST',a,1,1)
        self.assertEqual(r[0]['hit_50pct'],1)
    def test_missing_bars_excluded(self):
        a=self.candles();a[110]['t']+=5
        self.assertIsNone(feature_at(a,111))
    def test_embargo(self):
        r=examples('KRW-TEST',self.candles(),48)
        report=evaluate(r)
        self.assertLess(report['train']['samples']+report['test']['samples'],len(r))
    def test_zero_signal(self):
        r=[{'signal':0,'t':0,'horizon_bars':48,'max_gain_pct':0,'hit_3pct':0,'hit_10pct':0,'hit_50pct':0}]
        self.assertIsNone(metrics(r)['3pct_signal_hit_rate'])
if __name__=='__main__':unittest.main()
