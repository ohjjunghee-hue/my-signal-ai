import unittest
from historical_candle_integrity import validate_candles

def bar(ts=0,**changes):
    row={'ts':ts,'open':100,'high':105,'low':95,'close':102,'volume':2}
    row.update(changes)
    return row

class CandleIntegrityTests(unittest.TestCase):
    def test_valid_candle(self):
        self.assertEqual(validate_candles([bar()],5)['status'],'VALID')
    def test_impossible_high(self):
        self.assertIn('invalid_ohlc_range',validate_candles([bar(high=99)],5)['invalid'][0]['problems'])
    def test_negative_volume(self):
        self.assertIn('negative_volume',validate_candles([bar(volume=-1)],5)['invalid'][0]['problems'])
    def test_misaligned_timestamp(self):
        self.assertIn('misaligned_timestamp',validate_candles([bar(301)],5)['invalid'][0]['problems'])
    def test_nonfinite_value(self):
        self.assertIn('nonfinite_close',validate_candles([bar(close=float('nan'))],5)['invalid'][0]['problems'])
    def test_duplicate_timestamp(self):
        self.assertEqual(validate_candles([bar(),bar()],5)['invalid_count'],1)
if __name__=='__main__':unittest.main()
