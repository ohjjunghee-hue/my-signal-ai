import io
import json
import unittest
from datetime import datetime,timezone
from urllib.parse import parse_qs,urlparse
from historical_gap_requery import gap_timestamps,sampled_gap_timestamps,requery_gap

class Response(io.BytesIO):
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

def opener_for(ts,seen):
    def opener(req,timeout):
        seen.append(req.full_url)
        return Response(json.dumps([{'candle_date_time_utc':datetime.fromtimestamp(t,timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')} for t in ts]).encode())
    return opener

class GapRequeryTests(unittest.TestCase):
    def test_gap_enumeration_limit(self):
        self.assertEqual(gap_timestamps([{'ts':0},{'ts':1200}],limit=2),[300,600])
    def test_distributed_missing_interval_sample(self):
        rows=[{'ts':t} for t in (0,900,1200,2400,2700,3900)]
        self.assertEqual(sampled_gap_timestamps(rows,limit=3),[300,1500,3000])
    def test_no_gaps_returns_empty(self):
        self.assertEqual(sampled_gap_timestamps([{'ts':0},{'ts':300}],limit=3),[])
    def test_exact_timestamp_recovered(self):
        seen=[]
        r=requery_gap('KRW-SUI',300,opener=opener_for([300,0],seen))
        self.assertEqual(r['status'],'RECOVERED_BY_REQUERY')
        self.assertEqual(parse_qs(urlparse(seen[0]).query)['to'],['1970-01-01T09:10:00'])
    def test_other_candle_is_not_proof_of_absence(self):
        r=requery_gap('KRW-APT',300,opener=opener_for([0],[]))
        self.assertEqual(r['status'],'UNRESOLVED_AFTER_REQUERY')
    def test_misaligned_timestamp_rejected(self):
        with self.assertRaises(ValueError):requery_gap('KRW-SUI',301)
if __name__=='__main__':unittest.main()
