import unittest
import inspect
import server
class AuditTests(unittest.TestCase):
    def test_schema_and_query(self):
        schema=inspect.getsource(server.db_init)
        endpoint=inspect.getsource(server.Handler.do_GET)
        scan=inspect.getsource(server.scan)
        self.assertIn('CREATE TABLE IF NOT EXISTS buy_gate_audit',schema)
        self.assertIn("path=='/api/buy-gate-audit'",endpoint)
        self.assertIn("INSERT INTO buy_gate_audit",scan)
        self.assertIn("DELETE FROM buy_gate_audit",scan)
if __name__=='__main__':unittest.main()
