"""V47 snapshot observability regression tests. Run: python -m unittest test_v47_storage_observability -v"""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import v47_storage as storage


class SnapshotObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.original = dict(storage.LAST)
        storage.LAST.update(mode='not_configured', last_saved=None, last_attempt=None,
                            consecutive_failures=0, worker_alive=False, in_progress=False, error=None)

    def tearDown(self):
        storage.LAST.clear()
        storage.LAST.update(self.original)

    def test_missing_database_reports_failure(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'postgres://test'}):
            with patch.object(storage, 'connect') as connect:
                self.assertFalse(storage.save('/missing/v47/test.db'))
                connect.assert_not_called()
        self.assertEqual(storage.LAST['consecutive_failures'], 1)
        self.assertIn('FileNotFoundError', storage.LAST['error'])
        self.assertIsInstance(storage.LAST['last_attempt'], int)

    def test_storage_stale_before_first_save(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'postgres://test'}):
            self.assertTrue(storage.status()['stale'])

    def test_storage_fresh_and_stale_after_save(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'postgres://test'}):
            with patch.object(storage.time, 'time', return_value=1000):
                storage.LAST['last_saved'] = 900
                self.assertFalse(storage.status()['stale'])
                storage.LAST['last_saved'] = 819
                self.assertTrue(storage.status()['stale'])

    def test_unconfigured_not_stale(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(storage.status()['stale'])

    def test_worker_stall_detection(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'postgres://test'}):
            with patch.object(storage.time, 'time', return_value=1000):
                storage.LAST.update(worker_alive=True, last_attempt=870,
                                    last_completed=860, in_progress=True)
                self.assertTrue(storage.status()['worker_stalled'])
                storage.LAST['last_completed'] = 870
                self.assertTrue(storage.status()['worker_stalled'])
                storage.LAST['in_progress'] = False
                self.assertFalse(storage.status()['worker_stalled'])
                storage.LAST['worker_alive'] = False
                self.assertFalse(storage.status()['worker_stalled'])

    def test_save_completion_timestamp_on_failure(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'postgres://test'}):
            self.assertFalse(storage.save('/missing/v47/test.db'))
        self.assertFalse(storage.LAST['in_progress'])
        self.assertIsInstance(storage.LAST['last_completed'], int)
        self.assertGreaterEqual(storage.LAST['last_duration_seconds'], 0)

    def test_repeated_failures_increment(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'postgres://test'}):
            for _ in range(3):
                self.assertFalse(storage.save('/missing/v47/test.db'))
        self.assertEqual(storage.LAST['consecutive_failures'], 3)


if __name__ == '__main__':
    unittest.main()
