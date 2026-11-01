"""Authenticated SQLite snapshot export helper.

A backup must not expose account secrets or be served without ACCESS_TOKEN.
SQLite backup API gives a consistent snapshot even with concurrent writers.
"""
import io
import hashlib
import sqlite3
import tempfile
import pathlib
import zipfile
import json
import time

def make_backup(db_path):
    db_path=pathlib.Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError("No database exists to back up")
    with tempfile.TemporaryDirectory() as directory:
        snapshot=pathlib.Path(directory)/"signals.db"
        with sqlite3.connect(str(db_path),timeout=15) as source:
            with sqlite3.connect(str(snapshot)) as target:
                source.backup(target)
        with sqlite3.connect(str(snapshot)) as check:
            result=check.execute("PRAGMA integrity_check").fetchone()[0]
            if result!="ok":raise RuntimeError("Backup integrity check failed")
            tables=[r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            counts={name:check.execute('SELECT COUNT(*) FROM "'+name.replace('"','""')+'"').fetchone()[0] for name in tables}
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot,"signals.db")
            archive.writestr("manifest.json",json.dumps({"created_utc":int(time.time()),"integrity":"ok","table_counts":counts,"sha256":hashlib.sha256(snapshot.read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
        return out.getvalue()
