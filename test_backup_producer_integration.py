"""Verify production-format backup ZIP with the actual backup producer, offline only."""
import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from backup_offline_verify import verify_backup
from v49_secure_backup import make_backup

class ProducerVerifierIntegration(unittest.TestCase):
    def test_real_producer_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"signals.db"
            with sqlite3.connect(path) as c:
                c.execute("CREATE TABLE snapshots(id INTEGER PRIMARY KEY, status TEXT)")
                c.executemany("INSERT INTO snapshots(status) VALUES(?)",[("BUY",),("STOP",)])
                c.execute("CREATE TABLE paper_trades(id INTEGER PRIMARY KEY)")
                c.execute("INSERT INTO paper_trades VALUES(1)")
            data=make_backup(path)
            verified=verify_backup(data)
            self.assertTrue(verified["verified"])
            self.assertEqual(verified["tables"],{"paper_trades":1,"snapshots":2})
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                self.assertEqual(json.loads(z.read("manifest.json"))["table_counts"],verified["tables"])
    def test_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):make_backup(Path(td)/"missing.db")

if __name__=="__main__":unittest.main()
