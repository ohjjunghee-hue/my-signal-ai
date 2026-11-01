import sqlite3
import tempfile
import pathlib
import io
import zipfile
import json
import unittest
from v49_secure_backup import make_backup

class BackupTests(unittest.TestCase):
    def test_snapshot_contains_rows_and_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"live.db"
            with sqlite3.connect(p) as c:
                c.execute("CREATE TABLE snapshots (id INTEGER PRIMARY KEY, market TEXT)")
                c.execute("INSERT INTO snapshots(market) VALUES('KRW-TEST')")
            blob=make_backup(p)
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                self.assertEqual(json.loads(z.read('manifest.json'))['table_counts']['snapshots'],1)
                copied=pathlib.Path(d)/'copy.db';copied.write_bytes(z.read('signals.db'))
            with sqlite3.connect(copied) as c:
                self.assertEqual(c.execute('SELECT market FROM snapshots').fetchone()[0],'KRW-TEST')
    def test_missing_db_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):make_backup(pathlib.Path(d)/'missing.db')
if __name__=='__main__':unittest.main()
