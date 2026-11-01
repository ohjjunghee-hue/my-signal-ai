"""Static contract checks for historical BUY endpoint, no server import or DB writes."""
import ast
import pathlib
import unittest

class BuyHistoryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=pathlib.Path("server.py").read_text(encoding="utf-8")
        ast.parse(cls.source)
        cls.section=cls.source.split("elif path=='/api/buy-history':",1)[1].split("elif path=='/api/tracked':",1)[0]
    def test_only_buy_events(self):
        self.assertIn("WHERE new_status='BUY'",self.section)
    def test_read_only_query(self):
        self.assertIn("SELECT id,market,ts,previous,new_status,price,reason",self.section)
        for forbidden in ("INSERT INTO","UPDATE setup_events","DELETE FROM","DROP TABLE"):
            self.assertNotIn(forbidden,self.section)
    def test_limit_is_bounded(self):
        self.assertIn("min(500,int(params.get('limit',['200'])[0]))",self.section)
    def test_cursor_is_stable(self):
        self.assertIn("AND id<?",self.section)
        self.assertIn("next_before_id",self.section)
        self.assertIn("limit+1",self.section)
    def test_history_not_current_signal(self):
        self.assertIn("과거 BUY 신호 기록",self.section)

if __name__=="__main__":unittest.main()
