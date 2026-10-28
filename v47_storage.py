"""V47 SQLite snapshot persistence through external PostgreSQL.

Requires DATABASE_URL pointing to a user-owned PostgreSQL database.
The snapshot is not a substitute for a continuously running worker.
"""
import hashlib
import os
import pathlib
import sqlite3
import tempfile
import threading
import time

LOCK = threading.RLock()
LAST = {'mode': 'not_configured', 'last_saved': None, 'last_restored': None,
        'error': None, 'snapshot_bytes': None, 'warning': '영구 저장소 미연결: 재배포 시 기록 유실 가능'}
MAX_BYTES = 100 * 1024 * 1024


def enabled():
    return bool(os.getenv('DATABASE_URL', '').strip())


def connect():
    import psycopg
    return psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=10)


def ensure_table(c):
    c.execute('''CREATE TABLE IF NOT EXISTS my_signal_sqlite_snapshots (
      snapshot_key TEXT PRIMARY KEY, payload BYTEA NOT NULL,
      sha256 TEXT NOT NULL, saved_at BIGINT NOT NULL)''')


def restore(path):
    """Restore before db_init; never overwrite a populated local DB without explicit opt-in."""
    path = pathlib.Path(path)
    if not enabled():
        return False
    with LOCK:
        try:
            with connect() as c:
                ensure_table(c)
                row = c.execute('SELECT payload,sha256,saved_at FROM my_signal_sqlite_snapshots WHERE snapshot_key=%s', ('main',)).fetchone()
            if row is None:
                LAST.update(mode='remote_empty', error=None, warning='외부 저장소 연결됨 · 최초 저장 대기')
                return False
            payload, checksum, saved = bytes(row[0]), row[1], int(row[2])
            if not payload or len(payload) > MAX_BYTES or hashlib.sha256(payload).hexdigest() != checksum:
                raise ValueError('원격 스냅샷 무결성 오류')
            # Protect existing local data if a restart reuses the filesystem.
            if path.exists() and path.stat().st_size > 0:
                try:
                    with sqlite3.connect(path) as db:
                        existing = db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                    if existing:
                        LAST.update(mode='local_preserved', error=None, warning='기존 로컬 DB 보존 · 원격 덮어쓰기 생략')
                        return False
                except sqlite3.DatabaseError:
                    pass
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix='.v47-restore-', suffix='.db', dir=path.parent)
            try:
                with os.fdopen(fd, 'wb') as f:
                    f.write(payload)
                    f.flush(); os.fsync(f.fileno())
                with sqlite3.connect(tmp) as db:
                    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise ValueError('복원 DB 무결성 오류')
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
            LAST.update(mode='remote_restored', last_restored=int(time.time()), last_saved=saved,
                        snapshot_bytes=len(payload), error=None, warning='외부 저장소에서 복원 완료')
            return True
        except Exception as e:
            LAST.update(mode='error', error=f'{type(e).__name__}: {str(e)[:160]}', warning='복원 실패 · 데이터 영속성 확인 필요')
            # Don't silently start with an empty database if restore fails.
            raise RuntimeError('V47 remote restore failed; refusing to start with empty data') from e


def save(path):
    path = pathlib.Path(path)
    if not enabled():
        LAST.update(mode='not_configured', warning='영구 저장소 미연결: 재배포 시 기록 유실 가능')
        return False
    with LOCK:
        try:
            if not path.exists(): return False
            fd, tmp = tempfile.mkstemp(prefix='.v47-backup-', suffix='.db')
            os.close(fd)
            try:
                with sqlite3.connect(path, timeout=20) as source, sqlite3.connect(tmp) as dest:
                    source.backup(dest)
                with open(tmp, 'rb') as f: payload = f.read(MAX_BYTES + 1)
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
            if len(payload) > MAX_BYTES: raise ValueError('DB exceeds 100 MB snapshot limit')
            checksum = hashlib.sha256(payload).hexdigest()
            now = int(time.time())
            with connect() as c:
                ensure_table(c)
                c.execute('''INSERT INTO my_signal_sqlite_snapshots(snapshot_key,payload,sha256,saved_at)
                  VALUES(%s,%s,%s,%s) ON CONFLICT(snapshot_key) DO UPDATE SET
                  payload=EXCLUDED.payload,sha256=EXCLUDED.sha256,saved_at=EXCLUDED.saved_at''',
                  ('main', payload, checksum, now))
            LAST.update(mode='remote_saved', last_saved=now, snapshot_bytes=len(payload),
                        error=None, warning='원격 스냅샷 저장 성공 · 최근 저장 이후 기록은 유실 가능')
            return True
        except Exception as e:
            LAST.update(mode='error', error=f'{type(e).__name__}: {str(e)[:160]}', warning='원격 저장 실패 · 확인 필요')
            return False


def run(path, interval=30):
    while True:
        save(path)
        time.sleep(interval)


def status():
    return dict(LAST, configured=enabled(), now=int(time.time()))
