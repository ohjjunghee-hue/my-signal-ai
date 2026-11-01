import unittest
from v49_forward_outcome import compare
class Tests(unittest.TestCase):
    def test_no_lookahead(self):
        events=[{"time":100,"market":"KRW-A","price":100,"allowed":True}]
        samples=[{"time":101,"market":"KRW-A","price":120},{"time":200,"market":"KRW-A","price":110}]
        r=compare(events,samples,horizon_seconds=100)
        self.assertEqual(r["allowed"]["count"],1)
        self.assertEqual(r["allowed"]["mean_net_pct"],9.6)
    def test_unresolved(self):
        r=compare([{"time":100,"market":"KRW-A","price":100,"allowed":False}],[],horizon_seconds=10)
        self.assertEqual(r["unresolved"],1)
        self.assertIsNone(r["blocked"]["win_rate_pct"])
    def test_late_price_is_not_a_valid_one_hour_outcome(self):
        r=compare([{'time':100,'market':'KRW-A','price':100,'allowed':True}],
                  [{'time':2000,'market':'KRW-A','price':200}],horizon_seconds=100,max_sample_delay_seconds=10)
        self.assertEqual(r['unresolved'],1)
    def test_invalid(self):
        with self.assertRaises(ValueError):compare([],[],0)
if __name__=="__main__":unittest.main()
