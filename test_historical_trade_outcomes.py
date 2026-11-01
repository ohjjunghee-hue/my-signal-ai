import unittest
from historical_trade_outcomes import evaluate_outcomes

def bar(ts, o=100, lo=99, hi=101, close=100):
    return {'ts':ts,'open':o,'low':lo,'high':hi,'close':close}
def event(start=300,stop=95,tp=110):
    return {'status':'RESOLVED','risk_levels_valid':True,'signal_close_ts':start,
            'entry_ts':start,'entry_reference':100,
            'stop_reference':stop,'tp1_reference':tp}
class TradeOutcomeTests(unittest.TestCase):
    def test_same_bar_stop_first_and_fee(self):
        r=evaluate_outcomes([event()], [bar(300,lo=94,hi=111)])
        self.assertEqual(r['trades'][0]['exit_reason'],'STOP')
        self.assertEqual(r['trades'][0]['net_pct'],-5.2)
    def test_gap_stop_uses_open(self):
        r=evaluate_outcomes([event()], [bar(300,o=90,lo=89,hi=110)])
        self.assertEqual(r['trades'][0]['exit_reason'],'STOP_GAP')
        self.assertEqual(r['trades'][0]['net_pct'],-10.2)
    def test_missing_future_candle_is_unresolved(self):
        r=evaluate_outcomes([event()], [bar(300),bar(900)],horizon_minutes=15)
        self.assertEqual(r['closed_count'],0)
        self.assertEqual(r['unresolved_count'],1)
    def test_repeated_signals_during_trade_are_skipped(self):
        candles=[bar(ts) for ts in (300,600,900)]
        r=evaluate_outcomes([event(300),event(600)],candles,horizon_minutes=15)
        self.assertEqual(r['closed_count'],1)
    def test_tp1_and_time_exit(self):
        tp=evaluate_outcomes([event()], [bar(300,lo=99,hi=111)])
        self.assertEqual(tp['trades'][0]['exit_reason'],'TP1')
        self.assertEqual(tp['trades'][0]['net_pct'],9.8)
        timed=evaluate_outcomes([event()], [bar(300,close=101),bar(600,close=102)],horizon_minutes=10)
        self.assertEqual(timed['trades'][0]['exit_reason'],'TIME')
        self.assertEqual(timed['trades'][0]['net_pct'],1.8)
    def test_no_trades_is_not_zero_percent(self):
        r=evaluate_outcomes([],[])
        self.assertIsNone(r['win_rate_pct'])
if __name__=='__main__':unittest.main()
