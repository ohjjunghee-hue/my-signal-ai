import inspect
import unittest
from unittest.mock import patch
import server
from v49_forward_outcome import compare

class ForwardIntegrationTests(unittest.TestCase):
    def test_api_wired_to_persisted_gate_and_pulse_samples(self):
        source=inspect.getsource(server.Handler.do_GET)
        self.assertIn("path=='/api/forward-validation'",source)
        self.assertIn('FROM buy_gate_audit',source)
        self.assertIn('FROM pulse_samples',source)
        self.assertIn('v49_forward_outcome.compare(events,samples,horizon_seconds=3600)',source)
    def test_allowed_and_blocked_observations(self):
        events=[{'time':100,'market':'KRW-A','price':100,'allowed':True},
                {'time':100,'market':'KRW-B','price':100,'allowed':False}]
        prices=[{'time':3700,'market':'KRW-A','price':105},
                {'time':3700,'market':'KRW-B','price':90}]
        result=compare(events,prices,horizon_seconds=3600)
        self.assertEqual(result['allowed']['mean_net_pct'],4.6)
        self.assertEqual(result['blocked']['mean_net_pct'],-10.4)
        self.assertEqual(result['unresolved'],0)
    def test_late_sample_is_unresolved(self):
        r=compare([{'time':100,'market':'KRW-A','price':100,'allowed':True}],
                  [{'time':9000,'market':'KRW-A','price':200}],horizon_seconds=3600)
        self.assertEqual(r['unresolved'],1)

if __name__=='__main__':unittest.main()
