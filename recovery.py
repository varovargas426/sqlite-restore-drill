import argparse
from contextlib import closing
import json
from pathlib import Path
from shutil import copyfile
import sqlite3
from tempfile import TemporaryDirectory

SCHEMA = """
CREATE TABLE ticket(id INTEGER PRIMARY KEY, subject TEXT NOT NULL);
CREATE TABLE ledger(seq INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL UNIQUE REFERENCES ticket(id));
"""


def add_ticket(db, subject):
    with db:
        row = db.execute("INSERT INTO ticket(subject) VALUES (?)", (subject,)).lastrowid
        db.execute("INSERT INTO ledger(seq,ticket_id) VALUES (?,?)", (row, row))


def backup(db, path):
    with closing(sqlite3.connect(path)) as dest:
        db.backup(dest)


def drill(snapshot, target):
    if target < 0:
        raise ValueError("target must be nonnegative")
    with TemporaryDirectory() as tmp:
        restored = Path(tmp) / "restored.db"
        try:
            copyfile(snapshot, restored)
            with closing(sqlite3.connect(restored)) as db:
                if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    return {"status": "integrity_failed"}
                if db.execute("PRAGMA foreign_key_check").fetchone():
                    return {"status": "broken_reference"}
                count, first, last = db.execute(
                    "SELECT count(*), coalesce(min(seq),0), coalesce(max(seq),0) FROM ledger"
                ).fetchone()
                tickets, = db.execute("SELECT count(*) FROM ticket").fetchone()
                if count != tickets or (count and first != 1) or last != count:
                    return {"status": "ledger_inconsistent"}
                return {"status": "recovered" if last >= target else "behind_target",
                        "recovered_sequence": last, "minimum_sequence": target,
                        "missing_sequences": max(0, target - last)}
        except (sqlite3.Error, OSError) as exc:
            return {"status": "unreadable_snapshot", "reason": str(exc)}


def demo():
    with TemporaryDirectory() as tmp:
        path = Path(tmp)
        with closing(sqlite3.connect(path / "live.db")) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)
            add_ticket(db, "Certificate renewed")
            add_ticket(db, "Incident closed")
            backup(db, path / "backup.db")
            add_ticket(db, "Post-backup ticket")
            target, = db.execute("SELECT max(seq) FROM ledger").fetchone()
        return drill(path / "backup.db", target)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Exercise an isolated SQLite restore")
    sub = cli.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    check = sub.add_parser("check")
    check.add_argument("snapshot", type=Path)
    check.add_argument("--target", required=True, type=int)
    args = cli.parse_args()
    if args.command == "check" and args.target < 0:
        cli.error("target must be nonnegative")
    result = demo() if args.command == "demo" else drill(args.snapshot, args.target)
    print(json.dumps(result, indent=2))
    expected = "behind_target" if args.command == "demo" else "recovered"
    raise SystemExit(0 if result["status"] == expected else 1)
