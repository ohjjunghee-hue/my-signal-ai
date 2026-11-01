import unittest
from historical_gap_crossframe import cross_timeframe_gap_evidence

class CrossframeTests(unittest.TestCase):
    def test_15m_present_does_not_reconstruct_missing_5m(self):
        r=cross_timeframe_gap_evidence([300],[{'ts':0},{'ts':600}],
                                       [{'ts':0,'volume':100}])
        x=r['results'][0]
        self.assertEqual(x['status'],'15M_PRESENT_5M_INCOMPLETE')
        self.assertEqual(x['known_5m_count'],2)
        self.assertFalse(x['proof_of_missing_cause'])
    def test_absent_15m_is_unresolved(self):
        r=cross_timeframe_gap_evidence([300],[{'ts':0}],[])
        self.assertEqual(r['results'][0]['status'],'NO_15M_AGGREGATE')
    def test_unaligned_rejected(self):
        with self.assertRaises(ValueError):
            cross_timeframe_gap_evidence([301],[],[])
if __name__=='__main__':unittest.main()
