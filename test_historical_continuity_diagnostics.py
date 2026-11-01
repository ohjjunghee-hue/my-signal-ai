import unittest
from historical_continuity_diagnostics import continuous_segments, coverage_report

class ContinuityTests(unittest.TestCase):
    def test_gaps_split_real_segments(self):
        rows=[{'ts':t} for t in (0,300,600,1500,1800,3600)]
        r=coverage_report(rows,5,3)
        self.assertEqual(r['segment_count'],3)
        self.assertEqual(r['observed_span_intervals'],13)
        self.assertEqual(r['missing_intervals_in_span'],7)
        self.assertEqual(r['longest_segment_bars'],3)
        self.assertEqual(r['eligible_rolling_windows'],1)
        self.assertEqual(r['top_5_segment_lengths'],[3,2,1])
        self.assertEqual(r['insufficient_contiguous_bars'],0)
    def test_empty_history_has_no_eligible_windows(self):
        r=coverage_report([],5,289)
        self.assertEqual(r['eligible_rolling_windows'],0)
        self.assertEqual(r['segments'],[])
        self.assertEqual(r['observed_span_intervals'],0)
        self.assertEqual(r['missing_intervals_in_span'],0)
        self.assertEqual(r['insufficient_contiguous_bars'],289)
    def test_unsorted_rows_are_sorted_without_filling(self):
        segments=continuous_segments([{'ts':600},{'ts':0},{'ts':300}],5)
        self.assertEqual(segments[0]['bars'],3)
    def test_duplicates_are_rejected(self):
        with self.assertRaises(ValueError):
            continuous_segments([{'ts':0},{'ts':0}],5)
if __name__=='__main__':unittest.main()
