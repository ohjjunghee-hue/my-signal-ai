"""Offline verification of a downloaded MY SIGNAL SQLite ZIP backup.

Does not restore, overwrite, or connect to production.
"""
import hashlib
import io
import json
import pathlib
import sqlite3
import tempfile
import zipfile

def verify_backup(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        names=archive.namelist()
        if len(names)!=2 or set(names)!={"signals.db","manifest.json"}:
            raise ValueError("Unexpected backup contents")
        if any(archive.getinfo(n).file_size>200_000_000 for n in names):
            raise ValueError("Backup exceeds size limit")
        manifest=json.loads(archive.read("manifest.json"))
        if manifest.get("integrity")!="ok":
            raise ValueError("Missing source integrity confirmation")
        raw=archive.read("signals.db")
    digest=hashlib.sha256(raw).hexdigest()
    if manifest.get("sha256")!=digest:
        raise ValueError("Backup SHA-256 mismatch or missing digest")
    with tempfile.TemporaryDirectory() as temp:
        db=pathlib.Path(temp)/"signals.db"
        db.write_bytes(raw)
        con=sqlite3.connect(f"file:{db}?mode=ro",uri=True)
        try:
            if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("SQLite integrity check failed")
            names=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            counts={name:con.execute('SELECT COUNT(*) FROM "'+name.replace('"','""')+'"').fetchone()[0] for name in names}
        finally:
            con.close()
    expected=manifest.get("table_counts")
    if expected!=counts:
        raise ValueError("Manifest row counts differ from SQLite snapshot")
    return {"verified":True,"tables":counts,"sha256":hashlib.sha256(raw).hexdigest(),
            "note":"Verified file integrity only; no proof of completeness versus live server."}
