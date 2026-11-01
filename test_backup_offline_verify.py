import io
import hashlib
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from backup_offline_verify import verify_backup

class BackupVerifyTests(unittest.TestCase):
    def make_zip(self,expected=1):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/"signals.db"
            with sqlite3.connect(db) as c:
                c.execute("CREATE TABLE demo (id INTEGER)")
                c.execute("INSERT INTO demo VALUES (1)")
            out=io.BytesIO()
            with zipfile.ZipFile(out,"w") as z:
                z.write(db,"signals.db")
                z.writestr("manifest.json",json.dumps({"integrity":"ok","table_counts":{"demo":expected},"sha256":hashlib.sha256(db.read_bytes()).hexdigest()}))
            return out.getvalue()
    def test_valid_backup(self):
        self.assertEqual(verify_backup(self.make_zip())["tables"]["demo"],1)
    def test_wrong_count_rejected(self):
        with self.assertRaises(ValueError): verify_backup(self.make_zip(2))
    def test_wrong_digest_rejected(self):
        data=self.make_zip()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            raw=z.read("signals.db")
            manifest=json.loads(z.read("manifest.json"))
        manifest["sha256"]="0"*64
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w") as z:
            z.writestr("signals.db",raw)
            z.writestr("manifest.json",json.dumps(manifest))
        with self.assertRaises(ValueError): verify_backup(out.getvalue())
    def test_missing_manifest_rejected(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w") as z: z.writestr("signals.db",b"bad")
        with self.assertRaises(ValueError): verify_backup(out.getvalue())

if __name__=="__main__": unittest.main()
