"""Dashboard BUY-history regression checks; no browser or production access."""
import pathlib
import unittest
class BuyHistoryUiTests(unittest.TestCase):
 def test_panel_and_api(self):
  html=pathlib.Path("index.html").read_text(encoding="utf-8")
  self.assertIn('id="buyHistoryPanel"',html)
  self.assertIn('id="buyHistoryRows"',html)
  self.assertIn("fetch('/api/buy-history?limit=200'",html)
 def test_escaping_and_not_a_live_buy(self):
  html=pathlib.Path("index.html").read_text(encoding="utf-8")
  block=html.split('id="buyHistoryPanel"',1)[1].split("</script>",1)[0]
  self.assertIn("현재 매수 신호나 실제 체결을 뜻하지 않습니다",block)
  self.assertIn("const esc=v=>",block)
  self.assertIn("esc(r.market)",block)
 def test_error_visible(self):
  html=pathlib.Path("index.html").read_text(encoding="utf-8")
  self.assertIn("BUY 이력 조회 실패",html)
if __name__=="__main__":unittest.main()
