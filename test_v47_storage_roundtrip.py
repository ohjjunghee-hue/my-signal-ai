"""V47 isolated SQLite snapshot save/restore integration tests (no production DB)."""
import hashlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import v47_storage as storage


class FakeCursor:
    def __init__(self, result=None):
        self.result = result
    def fetchone(self):
        return self.result


class FakeConnection:
    def __init__(self, state):
        self.state = state
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def execute(self, sql, args=None):
        if sql.startswith('SELECT payload'):
            return FakeCursor(self.state.get('row'))
        if sql.startswith('INSERT INTO'):
            payload = bytes(args[1])
            self.state['row'] = (payload, args[2], args[3])
        return FakeCursor()


class StorageIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'journal.db'
        self.state = {}
        self.original = dict(storage.LAST)
        self.addCleanup(lambda: (storage.LAST.clear(), storage.LAST.update(self.original)))
        self.env = patch.dict(os.environ, {'DATABASE_URL': 'postgres://test'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.conn = patch.object(storage, 'connect', side_effect=lambda: FakeConnection(self.state))
        self.conn.start()
        self.addCleanup(self.conn.stop)

    def create_db(self):
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE events (id INTEGER PRIMARY KEY, signal TEXT)')
            db.execute('INSERT INTO events(signal) VALUES (?)', ('BUY',))

    def test_save_then_restore_round_trip(self):
        self.create_db()
        self.assertTrue(storage.save(self.path))
        payload, checksum, saved = self.state['row']
        self.assertEqual(hashlib.sha256(payload).hexdigest(), checksum)
        self.path.unlink()
        self.assertTrue(storage.restore(self.path))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('SELECT signal FROM events').fetchone()[0], 'BUY')

    def test_restore_refuses_bad_checksum_without_overwriting(self):
        self.state['row'] = (b'not a database', '0'*64, 1)
        with self.assertRaises(RuntimeError):
            storage.restore(self.path)
        self.assertFalse(self.path.exists())

    def test_snapshot_rejects_corrupt_sqlite_with_matching_checksum(self):
        payload = b'not a sqlite database'
        self.state['row'] = (payload, hashlib.sha256(payload).hexdigest(), 1)
        with self.assertRaises(RuntimeError):
            storage.restore(self.path)
        self.assertFalse(self.path.exists())

    def test_valid_remote_does_not_replace_existing_local_data(self):
        self.create_db()
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO events(signal) VALUES ('LOCAL_ONLY')")
        remote = Path(self.tmp.name) / 'remote.db'
        with sqlite3.connect(remote) as db:
            db.execute('CREATE TABLE events (id INTEGER PRIMARY KEY, signal TEXT)')
            db.execute("INSERT INTO events(signal) VALUES ('REMOTE_ONLY')")
        self.assertTrue(storage.save(remote))
        self.assertFalse(storage.restore(self.path))
        with sqlite3.connect(self.path) as db:
            signals = [row[0] for row in db.execute('SELECT signal FROM events ORDER BY id')]
        self.assertEqual(signals, ['BUY', 'LOCAL_ONLY'])

    def test_failed_save_does_not_replace_last_good_snapshot(self):
        self.create_db()
        self.assertTrue(storage.save(self.path))
        previous = self.state['row']
        self.path.unlink()
        self.assertFalse(storage.save(self.path))
        self.assertEqual(self.state['row'], previous)
        self.assertEqual(storage.LAST['consecutive_failures'], 1)

    def test_restore_preserves_valid_local_database(self):
        self.create_db()
        self.state['row'] = (b'bad remote bytes', '0'*64, 1)
        with self.assertRaises(RuntimeError):
            storage.restore(self.path)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT signal FROM events').fetchone()[0], 'BUY')


if __name__ == '__main__':
    unittest.main()
