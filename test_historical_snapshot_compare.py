import unittest
from historical_snapshot_compare import compare_snapshots

def bar(ts,close=100):
    return {'ts':ts,'open':100,'high':101,'low':99,'close':close,'volume':1}

class SnapshotTests(unittest.TestCase):
    def test_identical_overlap_with_shifted_window(self):
        r=compare_snapshots([bar(0),bar(300)],[bar(300),bar(600)])
        self.assertEqual(r['overlap_count'],1)
        self.assertEqual(r['changed_count'],0)
        self.assertEqual(r['only_first_count'],1)
        self.assertEqual(r['comparison_status'],'MATCHED_OVERLAP')
    def test_changed_price_detected(self):
        r=compare_snapshots([bar(0)],[bar(0,101)])
        self.assertEqual(r['changed'][0]['fields'],['close'])
        self.assertEqual(r['comparison_status'],'CHANGED_OVERLAP')
    def test_no_overlap_is_not_match(self):
        self.assertEqual(compare_snapshots([bar(0)],[bar(300)])['comparison_status'],'NO_OVERLAP')
    def test_duplicate_timestamps_rejected(self):
        with self.assertRaises(ValueError):
            compare_snapshots([bar(0),bar(0)],[bar(0)])
if __name__=='__main__':
    unittest.main()
