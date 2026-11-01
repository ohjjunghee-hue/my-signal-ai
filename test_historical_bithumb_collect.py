import io
import json
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from historical_bithumb_collect import collect

def row(ts):
    t=datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    return {'candle_date_time_utc':t,'opening_price':100,'high_price':102,
            'low_price':99,'trade_price':101,'candle_acc_trade_volume':10}
class Response(io.BytesIO):
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
class CollectorTests(unittest.TestCase):
    def test_closed_only_sorted(self):
        def opener(req,timeout):
            return Response(json.dumps([row(300),row(0)]).encode())
        with patch('historical_bithumb_collect.time.time',return_value=1000):
            result=collect('KRW-BTC',5,2,opener=opener,pause=0)
        self.assertEqual([x['ts'] for x in result],[0,300])
    def test_future_candle_excluded(self):
        def opener(req,timeout):
            return Response(json.dumps([row(900),row(0)]).encode())
        with patch('historical_bithumb_collect.time.time',return_value=1000):
            result=collect('KRW-BTC',5,2,opener=opener,pause=0)
        self.assertEqual(len(result),1)
    def test_utc_pagination_and_gap_rejection(self):
        calls=[]
        def opener(req,timeout):
            calls.append(req.full_url)
            if len(calls)==1:
                return Response(json.dumps([row(900),row(600)]).encode())
            return Response(json.dumps([row(300),row(0)]).encode())
        with patch('historical_bithumb_collect.time.time',return_value=2000):
            result=collect('KRW-BTC',5,4,opener=opener,pause=0)
        self.assertEqual([x['ts'] for x in result],[0,300,600,900])
        self.assertIn('to=1970-01-01T09%3A10%3A00',calls[1])
        def gapped(req,timeout):
            return Response(json.dumps([row(900),row(0)]).encode())
        with patch('historical_bithumb_collect.time.time',return_value=2000):
            sparse=collect('KRW-BTC',5,2,opener=gapped,pause=0)
        self.assertEqual([x['ts'] for x in sparse],[0,900])
    def test_rejects_invalid_requests(self):
        with self.assertRaises(ValueError):collect('BTC-KRW',5)
        with self.assertRaises(ValueError):collect('KRW-BTC',1)
if __name__=='__main__':unittest.main()
