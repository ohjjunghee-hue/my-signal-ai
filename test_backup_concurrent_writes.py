"""Regression checks for backup safety and concurrent SQLite writes."""
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from v49_secure_backup import make_backup
from backup_offline_verify import verify_backup

class ConcurrentBackupTests(unittest.TestCase):
    def test_snapshot_is_consistent_while_writer_runs(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"signals.db"
            with sqlite3.connect(path) as c:
                c.execute("PRAGMA journal_mode=WAL")
                c.execute("CREATE TABLE signals(id INTEGER PRIMARY KEY, status TEXT)")
                c.execute("INSERT INTO signals(status) VALUES('BUY')")
            errors=[]
            def writer():
                try:
                    with sqlite3.connect(path,timeout=10) as c:
                        for i in range(40):
                            c.execute("INSERT INTO signals(status) VALUES('WATCH')")
                            c.commit()
                except Exception as exc:
                    errors.append(str(exc))
            thread=threading.Thread(target=writer)
            thread.start()
            try:
                backup=make_backup(path)
                result=verify_backup(backup)
                self.assertTrue(result["verified"])
                self.assertGreaterEqual(result["tables"]["signals"],1)
                self.assertLessEqual(result["tables"]["signals"],41)
            finally:
                thread.join(timeout=10)
            self.assertFalse(errors)
            self.assertFalse(thread.is_alive())

if __name__=="__main__":unittest.main()
