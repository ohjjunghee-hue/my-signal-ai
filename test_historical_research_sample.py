import unittest
from historical_research_sample import classify_recall

class RecallValidityTests(unittest.TestCase):
    def test_no_eligible_evaluations_is_not_zero_recall(self):
        result=classify_recall({'events':4,'detected':0,'recall_pct':0.0},0)
        self.assertIsNone(result['recall_pct'])
        self.assertEqual(result['evaluation_status'],'NOT_EVALUABLE_HISTORY')
        self.assertEqual(result['surge_events'],4)
    def test_evaluable_zero_recall_preserved(self):
        result=classify_recall({'events':1,'detected':0,'recall_pct':0.0},711)
        self.assertEqual(result['recall_pct'],0.0)
        self.assertEqual(result['evaluation_status'],'PARTIALLY_EVALUABLE')
    def test_no_surge_event_is_not_failure(self):
        result=classify_recall({'events':0,'detected':0,'recall_pct':None},711)
        self.assertIsNone(result['recall_pct'])
        self.assertEqual(result['evaluation_status'],'NO_SURGE_EVENTS')
    def test_no_assessable_surge_windows_is_not_zero_recall(self):
        result=classify_recall({'events':0,'detected':0,'recall_pct':None},711,{'assessable_windows':0})
        self.assertIsNone(result['recall_pct'])
        self.assertEqual(result['evaluation_status'],'NOT_EVALUABLE_HISTORY')
    def test_assessable_surge_windows_preserve_zero_recall(self):
        result=classify_recall({'events':1,'detected':0,'recall_pct':0.0},711,{'assessable_windows':5})
        self.assertEqual(result['recall_pct'],0.0)
if __name__=='__main__':unittest.main()
