import unittest
from pathlib import Path
from server import analyze, select_deep_markets

class V37Tests(unittest.TestCase):
    def test_all_market_gainers_always_visible_in_ui(self):
        ui=Path(__file__).with_name('index.html').read_text()
        self.assertIn('renderMarketLeaders(d.market_leaders||[]',ui)
        self.assertIn('빗썸 실제 상승 TOP 40',ui)
        self.assertIn('미분석 · BUY 판정 불가',ui)
    def test_no_buy_on_missing_candles(self):
        self.assertEqual(analyze([],[],[],100)['status'],'DATA')
    def test_selection_unique_and_capped(self):
        t=[{'market':f'KRW-{i}','acc_trade_price_24h':i+1,'signed_change_rate':i/1000} for i in range(100)]
        selected,sources=select_deep_markets(t,40,0)
        self.assertEqual(len(selected),40)
        self.assertEqual(len(sources),40)
        self.assertTrue(any(v.startswith('24시간 상승 상위') for v in sources.values()))
    def test_buy_only_on_confirmed_breakout(self):
        ui=Path(__file__).with_name('index.html').read_text()
        self.assertIn('BUY는 기술 조건 충족(수익 검증 전)',ui)
        backend=Path(__file__).with_name('server.py').read_text()
        self.assertIn('confirmed_breakout and vol>=1.3',backend)
        self.assertIn('change24<=10 and not risk',backend)
if __name__=='__main__':unittest.main()
