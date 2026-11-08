from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from recovery import add_ticket, backup, demo, drill, SCHEMA


class RestoreTests(unittest.TestCase):
    def test_wal_recovery_point(self):
        self.assertEqual(demo(), dict(status="behind_target", recovered_sequence=2,
                                      minimum_sequence=3, missing_sequences=1))

    def test_business_invariants(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.db"
            with closing(sqlite3.connect(":memory:")) as db:
                db.executescript(SCHEMA)
                add_ticket(db, "one")
                backup(db, path)
                self.assertEqual(drill(path, 1)["status"], "recovered")
                db.execute("UPDATE ledger SET seq = 5")
                db.commit()
                backup(db, path)
                self.assertEqual(drill(path, 1)["status"], "ledger_inconsistent")
                db.execute("UPDATE ledger SET ticket_id = 99")
                db.commit()
                backup(db, path)
                self.assertEqual(drill(path, 1)["status"], "broken_reference")

    def test_corrupt_snapshot(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.db"
            path.write_bytes(b"invalid header" * 90)
            self.assertEqual(drill(path, 0)["status"], "unreadable_snapshot")
