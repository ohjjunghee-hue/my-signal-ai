import json
import tempfile
import unittest
from pathlib import Path
from historical_candidate_audit import evaluate_market

def bars(unit,n,price=100):
    d=unit*60
    return [{'ts':i*d,'duration_sec':d,'open':price,'high':price+1,
             'low':price-1,'close':price,'volume':10} for i in range(n)]
class AuditTests(unittest.TestCase):
    def test_future_high_uses_next_bar_not_signal_bar(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            f=bars(5,320)
            f[290]['high']=300
            for u,series in ((5,f),(15,bars(15,120)),(60,bars(60,120))):
                (root/f'KRW-TEST_{u}m.json').write_text(json.dumps(series))
            def analyzer(a,b,c,p,change):
                return {'status':'BUY' if len(a)==120 and a[-1]['t']==289*300 else 'WAIT',
                        'entry':p,'stop':90,'targets':[110]}
            result=evaluate_market('KRW-TEST',root,analyzer,horizon_minutes=10)
            self.assertEqual(result['resolved'],1)
            self.assertEqual(result['hit_counts']['50'],1)
            self.assertFalse(result['events'][0]['final_live_buy_verified'])
    def test_no_signal_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for u in (5,15,60):
                (root/f'KRW-TEST_{u}m.json').write_text(json.dumps(bars(u,310)))
            result=evaluate_market('KRW-TEST',root,lambda *args:{'status':'WAIT'})
            self.assertEqual(result['base_buy_events'],0)
            self.assertEqual(result['hit_counts']['3'],0)
if __name__=='__main__':unittest.main()
