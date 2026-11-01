import unittest
from unittest.mock import patch
from datetime import datetime,timezone,timedelta
import server

class V49CalendarTests(unittest.TestCase):
    def test_excludes_current_day(self):
        now=datetime(2026,11,1,13,tzinfo=timezone.utc)
        rows=[{'candle_date_time_utc':(datetime(2026,11,1,tzinfo=timezone.utc)-timedelta(days=i)).strftime('%Y-%m-%dT%H:%M:%S'),'trade_price':str(100+i)} for i in range(23)]
        with patch.object(server,'get_json',return_value=rows),patch.object(server.time,'time',return_value=now.timestamp()):
            result=server.fetch_calendar('KRW-TEST','days')
        self.assertEqual(len(result),22)
        self.assertEqual(result[-1]['c'],101.0)
    def test_monthly_incomplete_excluded(self):
        now=datetime(2026,11,15,tzinfo=timezone.utc)
        rows=[]
        for i in range(25):
            year=2026-(11-i-1)//12
            month=(11-i-1)%12+1
            rows.append({'candle_date_time_utc':f'{year:04d}-{month:02d}-01T00:00:00','trade_price':'100'})
        with patch.object(server,'get_json',return_value=rows),patch.object(server.time,'time',return_value=now.timestamp()):
            result=server.fetch_calendar('KRW-TEST','months')
        self.assertEqual(len(result),24)
    def test_invalid_data_rejected(self):
        with patch.object(server,'get_json',return_value=[]):
            with self.assertRaises(ValueError):server.fetch_calendar('KRW-TEST','weeks')

if __name__=='__main__':unittest.main()
