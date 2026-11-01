import base64
import json
import unittest
from unittest.mock import patch
import account_readonly as a

class AccountTests(unittest.TestCase):
    def test_no_keys_no_request(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(a.read_balances()["connected"])

    def test_jwt_signature(self):
        token = a._jwt("access", "secret", nonce="fixed", timestamp_ms=123)
        header, payload, signature = token.split(".")
        self.assertEqual(json.loads(base64.urlsafe_b64decode(payload+"=="))["timestamp"], 123)
        self.assertTrue(signature)

    def test_normalization(self):
        rows = [{"currency":"KRW","balance":"1000.25","locked":"5","avg_buy_price":"0"}]
        self.assertEqual(a.normalize_balances(rows)[0]["total"], "1005.25")

    def test_negative_rejected(self):
        with self.assertRaises(a.AccountError):
            a.normalize_balances([{"currency":"BTC","balance":"-1","locked":"0","avg_buy_price":"1"}])

    def test_no_trade_api_in_module(self):
        import inspect
        source = inspect.getsource(a)
        self.assertNotIn("/v1/orders", source)
        self.assertNotIn('method="POST"', source)

if __name__ == "__main__":
    unittest.main()
