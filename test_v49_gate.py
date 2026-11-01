import unittest
import v49_gate

def candles(prices):
    return [{"c":p} for p in prices]

class GateTests(unittest.TestCase):
    def test_missing_fails_closed(self):
        self.assertEqual(v49_gate.evaluate({})["verdict"],"DATA")
    def test_downtrend_blocks(self):
        frames={k:candles(list(range(100,60,-1))) for k in ("4h","day","week","month")}
        self.assertFalse(v49_gate.evaluate(frames)["allowed"])
    def test_uptrend_passes(self):
        frames={k:candles(list(range(1,41))) for k in ("4h","day","week","month")}
        self.assertTrue(v49_gate.evaluate(frames)["allowed"])
    def test_nan_blocks(self):
        frames={k:candles(list(range(1,41))) for k in ("4h","day","week","month")}
        frames["day"][-1]["c"]=float("nan")
        self.assertEqual(v49_gate.evaluate(frames)["verdict"],"DATA")

if __name__=="__main__":
    unittest.main()
