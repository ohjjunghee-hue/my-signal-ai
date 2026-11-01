"""Offline restore drill: never touches the running server or its database."""
import io
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from backup_offline_verify import verify_backup
from v49_secure_backup import make_backup

class BackupRestoreDrill(unittest.TestCase):
    def test_restore_into_new_isolated_directory(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            source=base/"original"/"signals.db"
            source.parent.mkdir()
            with sqlite3.connect(source) as c:
                c.execute("CREATE TABLE snapshots(id INTEGER PRIMARY KEY, market TEXT, status TEXT)")
                c.executemany("INSERT INTO snapshots(market,status) VALUES (?,?)",
                              [("KRW-BTC","BUY"),("KRW-ETH","STOP")])
                c.execute("CREATE TABLE paper_trades(id INTEGER PRIMARY KEY, status TEXT)")
                c.execute("INSERT INTO paper_trades VALUES (1,'OPEN')")
            blob=make_backup(source)
            checked=verify_backup(blob)
            self.assertTrue(checked["verified"])
            destination=base/"restore_drill"/"signals.db"
            destination.parent.mkdir()
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                destination.write_bytes(archive.read("signals.db"))
            with sqlite3.connect(f"file:{destination}?mode=ro",uri=True) as c:
                self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0],"ok")
                self.assertEqual(c.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0],2)
                self.assertEqual(c.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0],1)
                self.assertEqual(c.execute("SELECT market,status FROM snapshots ORDER BY id").fetchall(),
                                 [("KRW-BTC","BUY"),("KRW-ETH","STOP")])
            with sqlite3.connect(f"file:{source}?mode=ro",uri=True) as c:
                self.assertEqual(c.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0],2)

if __name__=="__main__":unittest.main()
