import unittest,sqlite3,tempfile,pathlib
import paper_bridge
class PaperDeploymentTests(unittest.TestCase):
    def test_buy_record_exit_and_no_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'paper.db'
            buy=[{'market':'KRW-TEST','status':'BUY','entry':100,'stop':98,'tp_levels':[{'price':105}]}]
            ticker=[{'market':'KRW-TEST','trade_price':100}]
            self.assertEqual(paper_bridge.sync(p,buy,ticker,now=1000)['recorded'],1)
            self.assertEqual(paper_bridge.sync(p,buy,ticker,now=1001)['recorded'],0)
            self.assertEqual(paper_bridge.sync(p,[],[{'market':'KRW-TEST','trade_price':97}],now=1100)['closed'],1)
            self.assertEqual(paper_bridge.status(p)['rows'][0]['exit_reason'],'STOP')
            self.assertEqual(paper_bridge.status(p)['total'],1)
    def test_invalid_buy_is_not_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'paper.db'
            bad=[{'market':'KRW-TEST','status':'BUY','entry':100,'stop':110,'tp_levels':[{'price':105}]}]
            self.assertEqual(paper_bridge.sync(p,bad,[],now=1000)['recorded'],0)
if __name__=='__main__':unittest.main()
